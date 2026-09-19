#!/usr/bin/env python3
"""PreToolUse hook: gate mutating Bash commands with Jev before they run.

Two layers, on purpose:

1. A denylist of genuinely destructive / irreversible commands (rm -rf, dd,
   mkfs, force-push, drop database, ...) blocks outright, no model call. These
   are the only commands a hook should ever stop — routine mutations like
   `pip install` or `git push` must not be blocked.

2. Everything else that looks mutating gets a live Jev tool_gate call, logged as
   advisory context (exit 0) so the agent sees Jev's read but is not stopped.

Reads, non-mutating commands, and any hook error fail open (exit 0) — a hook
must never stop a safe operation or break the session.

stdin payload: {hook_event_name, cwd, tool_input:{command}}. Exit 0 allow, 2 block.
"""

from __future__ import annotations

import json
import os
import re
import sys

# The only commands a hook may block: irreversible, high-blast-radius. Narrow on
# purpose — a false positive here stops the user's work.
DESTRUCTIVE = re.compile(
    r"(rm\s+-[a-z]*r[fd]?\s+[^-]"        # rm -r/-rf on a real path
    r"|\bdd\b\s+.*\bof=/dev/"            # dd to a device
    r"|\bmkfs\b"                          # format a filesystem
    r"|\bshred\b"
    r"|\b(?:drop|truncate)\s+(?:database|table)\b"
    r"|\bgit\s+push\b[^|]*--force\b"      # force-push
    r"|\bgit\s+push\s+-f\b"
    r"|\bkill\s+-9\b.*\b1\b"              # kill init
    r"|\bsudo\s+(?:rm|dd|mkfs)\b)",
    re.IGNORECASE,
)

# Mutating commands that get an advisory Jev read (logged, not blocked).
MUTATING = re.compile(
    r"\b(rm|mv|cp|chmod|chown|tee|dd"
    r"|git\s+(push|commit|reset|rebase|merge|clean|rm)"
    r"|curl\s+[^|]*-X\s*(POST|PUT|DELETE|PATCH)|curl\s+[^|]*--data"
    r"|pip\s+install|npm\s+(install|publish|run\s+deploy)|apt|apt-get|brew"
    r"|deploy|kubectl|docker\s+(run|push|rm)|systemctl|kill|pkill|sudo)\b",
    re.IGNORECASE,
)

def _helper_root() -> str:
    """The repo the hook runs `python -m jev` from. Set JEV_HELPER_ROOT, or the
    HELPER_ROOT marker the installer writes next to the installed SKILL.md."""
    env = os.environ.get("JEV_HELPER_ROOT", "").strip()
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)  # scripts/ -> repo root


HELPER_ROOT = _helper_root()


def _allow() -> None:
    sys.exit(0)


def _block(reason: str) -> None:
    print(reason, file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        _allow()
    # kimi-code, Claude Code, Codex, and Hermes nest under tool_input; Cursor's
    # beforeShellExecution sends the command at the top level.
    command = (payload.get("tool_input") or {}).get("command") or payload.get("command") or ""
    # kimi-code and Claude Code pass a string; Codex passes an argv list.
    if isinstance(command, list):
        command = " ".join(str(part) for part in command)
    if not isinstance(command, str) or not command:
        _allow()

    # Layer 1: the denylist blocks with no model call. This is the only block.
    if DESTRUCTIVE.search(command):
        _block(
            "jev gate: blocked a destructive/irreversible command "
            "(denylist). Run it by hand if you mean it."
        )

    # Layer 2: advisory Jev read on other mutating commands. Live only — a
    # fixture verdict must never influence a real command.
    if os.environ.get("JEV_ALLOW_LIVE", "").strip() != "1" or not MUTATING.search(command):
        _allow()
    try:
        sys.path.insert(0, HELPER_ROOT)
        from jev import advise
        from jev.compress import compress_state
        from jev.client import JevClient, JevConfig
        from jev.packs import PACKS
        from jev.providers import resolve_provider

        provider = resolve_provider()
        client = JevClient(config=JevConfig(), live=True, require_auth=True)
        state = compress_state(goal=f"run this shell command: {command[:400]}", intended_tool="shell")
        response = client.decide(state, PACKS["tool_gate"], provider=provider)
        result = advise("tool_gate", response.get("answers", {}))
        # Advisory only: append Jev's read to the context, never block on it.
        print(
            f"jev advisory: {result['advice']} "
            f"(side_effect {result['signals'].get('side_effect', 0):.2f})"
        )
    except Exception as exc:
        # Fail open: unreachable API or exhausted key passes with a note.
        print(f"jev pass: unreachable ({exc}); allowing without a gate", file=sys.stderr)
    _allow()


if __name__ == "__main__":
    main()


#!/usr/bin/env bash
# Install the noulgate skill into Cursor: a SKILL.md under ~/.cursor/skills-cursor,
# plus a beforeShellExecution hook in ~/.cursor/hooks.json for enforcement.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL="${CURSOR_HOME:-$HOME/.cursor}/skills-cursor/noulgate"
mkdir -p "$SKILL"
cp "$ROOT/skills/noulgate/SKILL.md" "$SKILL/SKILL.md"
printf '%s\n' "$ROOT" > "$SKILL/HELPER_ROOT"

HOOKS="${CURSOR_HOME:-$HOME/.cursor}/hooks.json"
HOOK_CMD="python3 $ROOT/scripts/jev-gate-hook.py"
python3 - "$HOOKS" "$HOOK_CMD" <<'PY'
import json, sys
path, cmd = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(path))
except FileNotFoundError:
    d = {"version": 1, "hooks": {}}
bs = d.setdefault("hooks", {}).setdefault("beforeShellExecution", [])
if not any(h.get("command") == cmd for h in bs):
    bs.append({"command": cmd, "timeout": 20})
json.dump(d, open(path, "w"), indent=2)
print(f"hook wired in {path}")
PY
echo "Installed Cursor skill → $SKILL"
echo "Helper root → $ROOT"
echo "Hook: beforeShellExecution blocks destructive commands; others get an advisory read."
echo "Dry-run until JEV_ALLOW_LIVE=1 and --live."

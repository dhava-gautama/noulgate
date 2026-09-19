# Install noulgate in your harness

Every harness here loads the same thing: the `noulgate` skill — one
`SKILL.md` that teaches the agent to gate a costly step with Jev before it runs.
The only difference between harnesses is *where that file goes*.

There are three patterns, and every harness is one of them:

1. **Skills-dir harnesses** — the harness reads `SKILL.md` files from a directory
   you point it at (or a conventional one). Hermes, kimi-code, Claude Code,
   Codex, Pi, Oh My Pi. One command each.
2. **Slash-command harnesses** — the harness also exposes a `/command` you can
   invoke by hand. Claude Code gets one of those too.
3. **Any other** — `install-skill.sh <dir>` copies the skill wherever you say.

The skill runs `python -m jev decide …` from the repo. It needs nothing to run
offline; a live call finds the key itself (see the README's provider section).

## Prerequisites

```bash
git clone https://github.com/dhava-gautama/noulgate.git
cd noulgate
```

That's it. No package install, no build. Python 3.10+.

---

## Hermes

```bash
bash scripts/install-hermes.sh
```

Copies the skill to `~/.hermes/skills/software-development/noulgate/`.
Start a new session (`hermes` or `/reset`), then tell it:

> use noulgate before tool calls and skill_view

Hermes does progressive skill load (`skills_list` → `skill_view`), so the gate
sits in front of the fat skill bodies. See [`docs/HERMES.md`](HERMES.md).

### Enforce it with a shell hook

Hermes shell hooks block with exit 2 (Claude Code compatible), so the same
`jev-gate-hook.py` works. Add to `~/.hermes/config.yaml`:

```yaml
hooks:
  pre_tool_call:
    - matcher: "^(terminal|bash|shell)$"
      command: "python3 /path/to/noulgate/scripts/jev-gate-hook.py"
      timeout: 20
hooks_auto_accept: true
```

Destructive commands block; other mutations get an advisory Jev read (with
`JEV_ALLOW_LIVE=1`). Reads and any hook error fail open. `hooks_auto_accept:
true` skips the first-use consent prompt for this `(event, command)` pair.

## kimi-code

```bash
bash scripts/install-kimi.sh
```

Copies the skill to `~/.agents/skills/noulgate/`. kimi-code discovers
`~/.agents/skills` automatically on the next session. The direct key is read from
`providers.explabs.api_key` in `~/.kimi-code/config.toml`, so a configured
kimi-code needs no extra export.

### Enforce it with a hook

The skill is advisory; the agent chooses to call it. To gate shell commands
unconditionally, add a blocking `PreToolUse` hook to `~/.kimi-code/config.toml`:

```toml
[[hooks]]
event = "PreToolUse"
matcher = "Bash"
command = "python3 /path/to/noulgate/scripts/jev-gate-hook.py"
timeout = 20
```

Destructive commands (`rm -rf`, `dd` to a device, `mkfs`, force-push, `drop
database`) block with exit 2 and no model call. Other mutating commands get a
live Jev advisory appended to context (with `JEV_ALLOW_LIVE=1`). Reads and any
hook error fail open. Hooks are lightweight interception, not the sole security
barrier — keep permission approvals for genuinely high-risk operations.

## Claude Code

```bash
bash scripts/install-claude.sh
```

Copies the skill to `~/.claude/skills/noulgate/` **and** drops a
`/jev` slash command into `~/.claude/commands/jev.md`, so you can gate by hand:

```
/jev tool_gate search the web for the current forecast
```

Claude Code discovers `~/.claude/skills` on the next session. The `/jev` command
works immediately.

## Codex

```bash
bash scripts/install-codex.sh
```

Copies the skill to `~/.codex/skills/noulgate/` and appends a
`noulgate` block to your global `~/.codex/AGENTS.md` (created if absent), so the
agent knows the gate exists and when to call it. Idempotent — re-running updates
the block instead of duplicating it.

## Pi

```bash
bash scripts/install-pi.sh
```

Copies the skill to `~/.pi/agent/skills/noulgate/`. Pi discovers its
skills tree on the next session.

### Enforce it (extension)

Pi and OMP use an in-process TypeScript extension, not the exit-2 shell
contract. `scripts/jev-gate-hook.ts` is that extension — it hooks `tool_call`,
blocks a denylist of destructive bash commands, and logs an advisory Jev read
for other mutations (with `JEV_ALLOW_LIVE=1`). Install it:

```bash
mkdir -p ~/.pi/agent/extensions
cp scripts/jev-gate-hook.ts ~/.pi/agent/extensions/jev-gate.ts
```

Pi auto-discovers `~/.pi/agent/extensions/*.ts` (hot-reload with `/reload`), or
test once with `pi -e ./scripts/jev-gate-hook.ts`.

## Oh My Pi

```bash
bash scripts/install-omp.sh
```

Copies the skill to `~/.omp/agent/skills/noulgate/`. Oh My Pi loads
skills at launch; pass `--skills jev-*` to filter, or `--no-skills` to disable.

### Enforce it (hook)

OMP discovers hook factories from `~/.omp/agent/hooks/pre/*.ts`:

```bash
mkdir -p ~/.omp/agent/hooks/pre
cp scripts/jev-gate-hook.ts ~/.omp/agent/hooks/pre/jev-gate.ts
```

> Pi and Oh My Pi share the Pi-lineage extension host, so one `.ts` file serves
> both; only the directory differs. The extension runs `python -m jev decide`
> via `pi.exec` for the advisory read.

## Cursor

```bash
bash scripts/install-cursor.sh
```

Copies the skill to `~/.cursor/skills-cursor/noulgate/` and wires a
`beforeShellExecution` hook into `~/.cursor/hooks.json`. Cursor reads the command
from stdin's top-level `command` field (the hook accepts that and the nested
`tool_input.command` shape the other harnesses use). Destructive commands block
(exit 2); other mutations get an advisory read (with `JEV_ALLOW_LIVE=1`). Reads
and errors fail open.

## Anything else

If your harness reads `SKILL.md` files from a directory:

```bash
bash scripts/install-skill.sh /path/to/its/skills
```

If it doesn't, point the agent at the repo and the CLI directly — the skill is
just a convenience wrapper around `python -m jev decide`.

---

## After installing

Whichever harness, the flow is the same. Dry-run first (offline, no key):

```bash
cd /path/to/noulgate
python -m jev decide --pack tool_gate --state-file fixtures/sample_state.json
```

Then a live call when you're ready — needs `--live`, `JEV_ALLOW_LIVE=1`, and a
key. The key is found from `EXPERIENTIAL_API_KEY`, `EXPLABS_API_KEY`,
`TYPESAFE_API_KEY`, `OPENROUTER_API_KEY`, or kimi-code's `providers.explabs` —
whichever you already have.

## Uninstall

```bash
rm -rf <skills-dir>/noulgate        # any harness
rm -f  ~/.claude/commands/jev.md               # Claude Code slash command
# Codex: remove the "noulgate" block from ~/.codex/AGENTS.md
```

The helper never writes outside the skill dir and the one `AGENTS.md` block.

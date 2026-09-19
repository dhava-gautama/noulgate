#!/usr/bin/env bash
# Install the noulgate skill into Claude Code, plus a /jev command.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS="${CLAUDE_HOME:-$HOME/.claude}/skills/noulgate"
COMMANDS="${CLAUDE_HOME:-$HOME/.claude}/commands"
mkdir -p "$SKILLS" "$COMMANDS"
cp "$ROOT/skills/noulgate/SKILL.md" "$SKILLS/SKILL.md"
printf '%s\n' "$ROOT" > "$SKILLS/HELPER_ROOT"
cat > "$COMMANDS/jev.md" <<EOF
---
description: Gate an expensive step with Jev (noulgate). Usage: /jev <pack> <state text>. Packs: tool_gate, skill_gate, model_route, review_gate.
---

# /jev

Gate the next step with Jev before running it. Read the helper root from
\`$SKILLS/HELPER_ROOT\` (or \`\$JEV_HELPER_ROOT\`), cd there, and run:

\`\`\`bash
python -m jev decide --pack "\$1" --state-text "\$2"
\`\`\`

Dry-run by default. For a live call the operator sets \`JEV_ALLOW_LIVE=1\` and
adds \`--live\`. Show \`advice\`, \`reasons\`, and \`usage\`. Never act on a Jev
word alone — \`consider_*\` justifies the family, not the call, and
\`apply_advice_only\` never means apply.
EOF
echo "Installed Claude Code skill → $SKILLS"
echo "Installed /jev command      → $COMMANDS/jev.md"
echo "Helper root → $ROOT"
echo "Skill loads next session; /jev works now. Dry-run until JEV_ALLOW_LIVE=1 and --live."

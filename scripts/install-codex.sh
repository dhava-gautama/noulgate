#!/usr/bin/env bash
# Install the noulgate skill into Codex, and register the gate in the
# global AGENTS.md so the agent knows it exists. Idempotent.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS="${CODEX_HOME:-$HOME/.codex}/skills/noulgate"
AGENTS="${CODEX_HOME:-$HOME/.codex}/AGENTS.md"
mkdir -p "$SKILLS"
cp "$ROOT/skills/noulgate/SKILL.md" "$SKILLS/SKILL.md"
printf '%s\n' "$ROOT" > "$SKILLS/HELPER_ROOT"

BEGIN="<!-- noulgate:begin -->"
END="<!-- noulgate:end -->"
touch "$AGENTS"
# Drop any previous noulgate block, then append the current one.
if grep -qF "$BEGIN" "$AGENTS"; then
  sed -i "/$(printf '%s' "$BEGIN" | sed 's/[][\.*^$/]/\\&/g')/,/$(printf '%s' "$END" | sed 's/[][\.*^$/]/\\&/g')/d" "$AGENTS"
fi
cat >> "$AGENTS" <<EOF
$BEGIN
## noulgate — gate expensive steps with Jev

Before a costly tool call, a large skill load, or an apply, gate it:

\`\`\`bash
cd $ROOT && python -m jev decide --pack tool_gate --state-text "<the step>"
\`\`\`

Packs: tool_gate, skill_gate, model_route, review_gate. Dry-run by default.
Live needs \`JEV_ALLOW_LIVE=1\` and \`--live\`; the key is found from the
environment or kimi-code's providers.explabs. Treat the output as advice —
\`consider_*\` justifies the family, not the call; \`apply_advice_only\` never
means apply.
$END
EOF
echo "Installed Codex skill → $SKILLS"
echo "Registered gate in    → $AGENTS"
echo "Helper root → $ROOT"
echo "Dry-run until JEV_ALLOW_LIVE=1 and --live."

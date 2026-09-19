#!/usr/bin/env bash
# Install the noulgate skill into a kimi-code user skills dir.
# Copies (not symlinks) so the skill survives a repo move; re-run to update.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${KIMI_SKILLS_DIR:-$HOME/.agents/skills}/noulgate"
mkdir -p "$DEST"
cp "$ROOT/skills/noulgate/SKILL.md" "$DEST/SKILL.md"
printf '%s\n' "$ROOT" > "$DEST/HELPER_ROOT"
echo "Installed kimi-code skill → $DEST"
echo "Helper root → $ROOT"
echo
echo "kimi-code discovers ~/.agents/skills automatically on the next session."
echo "The helper reads its key from providers.explabs in ~/.kimi-code/config.toml"
echo "when EXPERIENTIAL_API_KEY / EXPLABS_API_KEY are not exported."
echo "Still dry-run until JEV_ALLOW_LIVE=1 and --live."

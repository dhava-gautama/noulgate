#!/usr/bin/env bash
# Install the noulgate skill into a harness that reads
# SKILL.md files from a directory you name. Works for any harness that
# follows the "one dir per skill, SKILL.md inside" convention (Claude Code,
# Cursor, OpenAI Codex, custom loops, ...).
#
#   bash scripts/install-skill.sh /path/to/skills-dir
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ $# -ne 1 ]; then
  echo "usage: $0 <skills-dir>" >&2
  echo "example: $0 ~/.config/my-agent/skills" >&2
  exit 2
fi
DEST="$1/noulgate"
mkdir -p "$DEST"
cp "$ROOT/skills/noulgate/SKILL.md" "$DEST/SKILL.md"
printf '%s\n' "$ROOT" > "$DEST/HELPER_ROOT"
echo "Installed skill → $DEST"
echo "Helper root → $ROOT"
echo "Still dry-run until JEV_ALLOW_LIVE=1 and --live."

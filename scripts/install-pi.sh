#!/usr/bin/env bash
# Install the noulgate skill into Pi's skills tree.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${PI_HOME:-$HOME/.pi}/agent/skills/noulgate"
mkdir -p "$DEST"
cp "$ROOT/skills/noulgate/SKILL.md" "$DEST/SKILL.md"
printf '%s\n' "$ROOT" > "$DEST/HELPER_ROOT"
echo "Installed Pi skill → $DEST"
echo "Helper root → $ROOT"
echo "Dry-run until JEV_ALLOW_LIVE=1 and --live."

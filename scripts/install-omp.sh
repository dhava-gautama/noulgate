#!/usr/bin/env bash
# Install the noulgate skill into Oh My Pi's skills tree.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${OMP_HOME:-$HOME/.omp}/agent/skills/noulgate"
mkdir -p "$DEST"
cp "$ROOT/skills/noulgate/SKILL.md" "$DEST/SKILL.md"
printf '%s\n' "$ROOT" > "$DEST/HELPER_ROOT"
echo "Installed Oh My Pi skill → $DEST"
echo "Helper root → $ROOT"
echo "Loaded at launch; filter with --skills jev-*, disable with --no-skills."
echo "Dry-run until JEV_ALLOW_LIVE=1 and --live."

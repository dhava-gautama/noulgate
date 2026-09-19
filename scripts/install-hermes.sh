#!/usr/bin/env bash
# Copy this skill into the local Hermes skills tree. Does not call Jev live.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${HERMES_HOME:-$HOME/.hermes}/skills/software-development/noulgate"
mkdir -p "$DEST"
cp "$ROOT/skills/noulgate/SKILL.md" "$DEST/SKILL.md"
printf '%s\n' "$ROOT" > "$DEST/HELPER_ROOT"
echo "Installed Hermes skill → $DEST"
echo "Helper root → $ROOT"
echo "New Hermes sessions will see it in skills_list."
echo "In an existing session: /reset  (or hermes skills … --now)"
echo "Still dry-run until JEV_ALLOW_LIVE=1 and --live."
echo "Key: EXPERIENTIAL_API_KEY, or EXPLABS_API_KEY, or the explabs provider"
echo "in ~/.kimi-code/config.toml — the helper checks all three."

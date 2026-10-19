#!/usr/bin/env bash
# auto-apply installer. Idempotent; safe to re-run.
#
# What it does:
#   1. Symlinks skills/auto-apply -> ~/.claude/skills/auto-apply and ~/.codex/skills/auto-apply
#      (creates parent dirs; backs up any existing non-symlink target and tells you).
#   2. Creates the data directory (default ~/auto-apply-data, override with AUTO_APPLY_DATA_DIR), mode 700.
#   3. Checks python3 is 3.9+ and warns if not.
#
# What it does NOT do:
#   - install any Python package (stdlib only, no pip)
#   - create, read or touch secrets.env
#   - run git commands

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$REPO_DIR/skills/auto-apply"
DATA_DIR="${AUTO_APPLY_DATA_DIR:-$HOME/auto-apply-data}"
DATA_DIR="${DATA_DIR/#\~/$HOME}"
TARGETS=(
  "$HOME/.claude/skills/auto-apply"
  "$HOME/.codex/skills/auto-apply"
)
STAMP="$(date +%Y%m%d-%H%M%S)"
WARNINGS=0

log()  { printf '%s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*" >&2; WARNINGS=$((WARNINGS + 1)); }
die()  { printf 'ERROR %s\n' "$*" >&2; exit 2; }

# --- 0. sanity -----------------------------------------------------------------
[ -d "$SKILL_SRC" ] || die "skill source not found: $SKILL_SRC (run this script from the repo checkout)"
[ -f "$SKILL_SRC/SKILL.md" ] || warn "SKILL.md not present yet in $SKILL_SRC (Phase 1 skeleton); the symlink is created anyway"

# --- 1. symlinks ---------------------------------------------------------------
link_one() {
  local target="$1"
  local parent
  parent="$(dirname "$target")"
  mkdir -p "$parent"

  if [ -L "$target" ]; then
    local current
    current="$(readlink "$target")"
    if [ "$current" = "$SKILL_SRC" ]; then
      log "OK    already linked: $target -> $SKILL_SRC"
      return 0
    fi
    local bak="$target.bak-$STAMP"
    mv "$target" "$bak"
    warn "$target was a symlink to $current; moved to $bak"
  elif [ -e "$target" ]; then
    local bak="$target.bak-$STAMP"
    mv "$target" "$bak"
    warn "$target existed and was not a symlink; backed up to $bak (inspect, then delete it yourself)"
  fi

  ln -s "$SKILL_SRC" "$target"
  log "LINK  $target -> $SKILL_SRC"
}

for t in "${TARGETS[@]}"; do
  link_one "$t"
done

# --- 2. data directory ---------------------------------------------------------
if [ -d "$DATA_DIR" ]; then
  log "OK    data dir exists: $DATA_DIR"
else
  mkdir -p "$DATA_DIR"
  log "MKDIR $DATA_DIR"
fi
chmod 700 "$DATA_DIR" 2>/dev/null || warn "could not chmod 700 $DATA_DIR"

case "$DATA_DIR" in
  "$REPO_DIR"/*|"$REPO_DIR")
    warn "data dir is inside the repository; personal data could end up in git. Set AUTO_APPLY_DATA_DIR elsewhere."
    ;;
esac

# --- 3. python check -----------------------------------------------------------
PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  warn "python3 not found on PATH; the skill's scripts need Python 3.9+"
else
  PY_VER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "?")"
  if "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    log "OK    python3 $PY_VER ($PY)"
  else
    warn "python3 is $PY_VER at $PY; this project needs 3.9+ and its scripts will refuse to run. macOS: brew install python3 (or python@3.9+)"
  fi
fi

# --- 4. summary ----------------------------------------------------------------
log ""
log "Done. Warnings: $WARNINGS"
log "Next: open Claude Code (or Codex) and type /auto-apply, or read README.md."
log "This script installed no Python packages and did not create or read secrets.env."

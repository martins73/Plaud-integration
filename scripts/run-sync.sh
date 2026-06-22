#!/usr/bin/env bash
# Wrapper that runs `plaud-brain sync` for the scheduler (launchd/cron).
# Activates the project's virtualenv, logs output, and pops a desktop
# notification if the sync fails (e.g. the PLAUD token expired).
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${HOME}/Library/Logs/plaud-brain"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/sync.log"

cd "$PROJECT_DIR" || { echo "cannot cd to $PROJECT_DIR" >>"$LOG"; exit 1; }

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') sync start ====="
  if plaud-brain sync; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') sync OK"
  else
    code=$?
    echo "$(date '+%Y-%m-%d %H:%M:%S') sync FAILED (exit $code)"
    osascript -e 'display notification "sync failed — your PLAUD token may have expired. Run: plaud-brain auth" with title "plaud-brain"' 2>/dev/null || true
  fi
  echo
} >>"$LOG" 2>&1

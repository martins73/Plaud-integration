#!/usr/bin/env bash
# Install a macOS launchd agent that runs `plaud-brain sync` on a schedule.
#
# Usage:
#   scripts/install-scheduler.sh 20:00      # every day at 8:00 PM (recommended)
#   scripts/install-scheduler.sh            # every 30 minutes (default)
#   scripts/install-scheduler.sh 3600       # every hour
#   scripts/install-scheduler.sh 86400      # every 24 hours from load
#
# The argument is either HH:MM (24-hour clock, daily) or a number of seconds.
# Re-run any time to change it. Use uninstall-scheduler.sh to stop.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARG="${1:-1800}"
LABEL="com.plaud-brain.sync"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
PLIST="${AGENTS_DIR}/${LABEL}.plist"
LOG_DIR="${HOME}/Library/Logs/plaud-brain"

mkdir -p "$AGENTS_DIR" "$LOG_DIR"
chmod +x "$SCRIPT_DIR/run-sync.sh"

# Build the schedule stanza: HH:MM -> daily calendar; otherwise -> interval.
if [[ "$ARG" =~ ^([0-9]{1,2}):([0-9]{2})$ ]]; then
  HOUR="$((10#${BASH_REMATCH[1]}))"
  MIN="$((10#${BASH_REMATCH[2]}))"
  SCHEDULE="  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>${HOUR}</integer>
    <key>Minute</key><integer>${MIN}</integer>
  </dict>"
  DESC="every day at ${ARG}"
else
  SCHEDULE="  <key>StartInterval</key><integer>${ARG}</integer>"
  DESC="every ${ARG} seconds"
fi

cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${SCRIPT_DIR}/run-sync.sh</string>
  </array>
${SCHEDULE}
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>${LOG_DIR}/launchd.out.log</string>
  <key>StandardErrorPath</key><string>${LOG_DIR}/launchd.err.log</string>
</dict>
</plist>
EOF

# (Re)load the agent.
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "Installed launchd agent '${LABEL}' — runs ${DESC}."
echo "It also runs once now (RunAtLoad) so you can confirm it works."
echo
echo "Watch it work:   tail -f \"${LOG_DIR}/sync.log\""
echo "Stop it:         ${SCRIPT_DIR}/uninstall-scheduler.sh"

#!/usr/bin/env bash
# Install a macOS launchd agent that runs `plaud-brain sync` on a schedule.
#
# Usage:
#   scripts/install-scheduler.sh            # every 30 minutes (default)
#   scripts/install-scheduler.sh 3600       # every hour
#   scripts/install-scheduler.sh 86400      # once a day
#
# Re-run any time to change the interval. Use uninstall-scheduler.sh to stop.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTERVAL="${1:-1800}"   # seconds between runs; default 30 minutes
LABEL="com.plaud-brain.sync"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
PLIST="${AGENTS_DIR}/${LABEL}.plist"
LOG_DIR="${HOME}/Library/Logs/plaud-brain"

mkdir -p "$AGENTS_DIR" "$LOG_DIR"
chmod +x "$SCRIPT_DIR/run-sync.sh"

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
  <key>StartInterval</key><integer>${INTERVAL}</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>${LOG_DIR}/launchd.out.log</string>
  <key>StandardErrorPath</key><string>${LOG_DIR}/launchd.err.log</string>
</dict>
</plist>
EOF

# (Re)load the agent.
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "Installed launchd agent '${LABEL}' — runs every ${INTERVAL} seconds."
echo "It also runs once now (RunAtLoad)."
echo
echo "Watch it work:   tail -f \"${LOG_DIR}/sync.log\""
echo "Stop it:         ${SCRIPT_DIR}/uninstall-scheduler.sh"

#!/usr/bin/env bash
# Stop and remove the macOS launchd agent installed by install-scheduler.sh.
set -euo pipefail

LABEL="com.plaud-brain.sync"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "Removed launchd agent '${LABEL}'. Scheduled syncs are stopped."

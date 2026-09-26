#!/bin/bash
# Install the iPod guard: copy script + LaunchAgent, then load it.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DST="$HOME/Library/Application Support/ipod-modern-sync"
mkdir -p "$DST"
cp "$SRC/ipod_guard.sh" "$DST/ipod_guard.sh"
chmod +x "$DST/ipod_guard.sh"
sed "s|@HOME@|$HOME|g" "$SRC/com.ipod-sync.guard.plist" \
  > "$HOME/Library/LaunchAgents/com.ipod-sync.guard.plist"
launchctl unload "$HOME/Library/LaunchAgents/com.ipod-sync.guard.plist" 2>/dev/null || true
launchctl load -w "$HOME/Library/LaunchAgents/com.ipod-sync.guard.plist"
echo "✅ iPod guard installed and running (starts automatically at login)."

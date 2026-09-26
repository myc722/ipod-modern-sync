#!/bin/bash
# Keep macOS device-management agents away from the iPod while it is connected.
# AMPDevicesAgent (Finder) validates and rewrites the iPod database on connect,
# which wipes artwork and triggers "cannot read iPod" dialogs. This guard kills
# the agents for as long as an iPod is plugged in. Other USB devices (iPhone…)
# are left alone — the kill only happens when an iPod is present.
while true; do
  if ioreg -p IOUSB -l 2>/dev/null | grep -qi "ipod"; then
    killall -9 AMPDeviceDiscoveryAgent AMPDevicesAgent 2>/dev/null
  fi
  sleep 5
done

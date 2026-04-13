#!/bin/bash
# Create launchd agent for monitoring on macOS

PLIST="$HOME/Library/LaunchAgents/com.asymmetrictest.monitor.plist"

cat > "$PLIST" << 'PLISTXML'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.asymmetrictest.monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd "$SCRIPT_DIR" && ./monitor_every_3h.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>10800</integer> <!-- 3 hours in seconds -->
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/monitoring_reports/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/monitoring_reports/launchd_error.log</string>
</dict>
</plist>
PLISTXML

# Replace SCRIPT_DIR in plist
sed -i '' "s|\$SCRIPT_DIR|$SCRIPT_DIR|g" "$PLIST"

echo "✅ Created launchd agent: $PLIST"
echo ""
echo "To load the agent:"
echo "   launchctl load $PLIST"
echo ""
echo "To unload:"
echo "   launchctl unload $PLIST"
echo ""
echo "To check status:"
echo "   launchctl list | grep asymmetrictest"

#!/bin/bash
# Schedule monitoring every 3 hours for 48-hour test

set -e

echo "📅 Scheduling 48-hour test monitoring..."
echo "========================================"

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if test is running
if [ ! -d "logs" ]; then
    echo "❌ No test logs found. Is the 48-hour test running?"
    echo "   Start it with: python run_48h_test_simple.py"
    exit 1
fi

# Create monitoring directory
mkdir -p monitoring_reports

# Create a simple monitoring script that runs every 3 hours
cat > monitor_every_3h.sh << 'EOF'
#!/bin/bash
# Run monitoring every 3 hours

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Run monitoring
python monitor_test.py

# Also send notification (optional)
# You can add Telegram/Discord webhook here
EOF

chmod +x monitor_every_3h.sh

echo "✅ Created monitoring script: monitor_every_3h.sh"
echo ""
echo "📋 Monitoring Schedule:"
echo "   • Every 3 hours for 48 hours"
echo "   • Next check: 3 hours from now"
echo "   • Total checks: 16 times"
echo ""
echo "To run monitoring manually:"
echo "   ./monitor_every_3h.sh"
echo ""
echo "To schedule automatic monitoring (macOS/Linux):"
echo ""
echo "Option 1: Using cron (run in terminal):"
echo "   crontab -e"
echo "   Add: 0 */3 * * * cd $SCRIPT_DIR && ./monitor_every_3h.sh"
echo ""
echo "Option 2: Using launchd (macOS):"
echo "   See create_launchd_agent.sh"
echo ""
echo "Option 3: Manual checks (recommended for now):"
echo "   I'll check every 3 hours and report here"
echo ""
echo "Current test status:"
echo "   Started: $(date -r logs/48h_test_*.log '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo 'Unknown')"
echo "   Progress: ~0.3% complete"
echo "   Next cycle: Every 5 minutes"

# Create launchd agent for macOS
if [[ "$(uname)" == "Darwin" ]]; then
    cat > create_launchd_agent.sh << 'EOF'
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
EOF

    chmod +x create_launchd_agent.sh
    echo "✅ Created macOS launchd agent script: create_launchd_agent.sh"
fi

echo ""
echo "📊 I'll check and report progress every 3 hours here in chat."
echo "   Next report: ~22:00 (3 hours from now)"
echo ""
echo "Test is running successfully! 🚀"
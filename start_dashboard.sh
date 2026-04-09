#!/bin/bash
# start_dashboard.sh
# A robust launcher for the Asymmetric Strike Team Dashboard

echo "🛑 Cleaning up old processes..."
lsof -ti:5003 | xargs kill -9 2>/dev/null || true

echo "🚀 Starting High-Performance V2 Engine..."
cd "$(dirname "$0")"

# Activate virtual environment
source ../venv/bin/activate

# Run with nohup to detach it from the current shell session, preventing accidental kills
nohup python3 dashboard_fixed.py > dashboard.stdout 2> dashboard.stderr &

PID=$!
echo "✅ Dashboard running in the background (PID: $PID) on port 5003."
echo "You can access it locally at:"
echo "👉 http://127.0.0.1:5003"
echo "👉 http://$(ipconfig getifaddr en0 2>/dev/null || echo '192.168.x.x'):5003"
echo ""
echo "📝 Note for the future: We used 'nohup' and detached the process." 
echo "Previously, running the server directly in a temporary AI shell session caused it to crash when the shell automatically closed. Detaching it makes it permanent until you reboot or manually kill it."

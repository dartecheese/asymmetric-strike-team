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

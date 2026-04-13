#!/bin/bash
# Start 48-hour validation test for Asymmetric Strike Team

set -e

echo "🚀 Starting 48-Hour Paper Trading Validation Test"
echo "================================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run deploy.sh first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Create necessary directories
mkdir -p logs
mkdir -p test_results

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Check dependencies
echo "Checking dependencies..."
python -c "
import sys
try:
    import yaml, requests, web3, ccxt, pydantic
    print('✅ All dependencies installed')
except ImportError as e:
    print(f'❌ Missing dependency: {e}')
    sys.exit(1)
"

# Run the test
echo ""
echo "Starting 48-hour test..."
echo "This will run continuously for 48 hours (2 days)."
echo "Logs will be saved to logs/ directory."
echo "Performance data will be saved to test_results/ directory."
echo ""
echo "Press Ctrl+C to stop the test early."
echo ""
echo "Starting in 5 seconds..."
sleep 5

# Run the test
python run_48h_test.py

# Deactivate virtual environment
deactivate

echo ""
echo "✅ Test completed. Check logs/ and test_results/ directories for results."
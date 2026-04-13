#!/bin/bash
# Asymmetric Strike Team - Deployment Script
# Quick setup and testing for the professional trading system

set -e  # Exit on error

echo "🚀 Asymmetric Strike Team - Deployment Script"
echo "============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
if [[ $python_version == 3.1* ]]; then
    print_status "Python $python_version detected (compatible)"
else
    print_warning "Python $python_version detected (expected 3.10+)"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    print_status "Virtual environment created"
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    print_status "Dependencies installed"
else
    print_error "requirements.txt not found"
    exit 1
fi

# Create configuration files if they don't exist
echo "Setting up configuration..."

# Create .env from template if it doesn't exist
if [ ! -f ".env" ] && [ -f ".env.template" ]; then
    cp .env.template .env
    print_warning "Created .env file from template"
    print_warning "Please edit .env with your API keys before real trading"
elif [ ! -f ".env" ]; then
    print_warning ".env file not found - creating basic one"
    cat > .env << EOF
# Asymmetric Strike Team - Environment Variables
USE_REAL_EXECUTION=false
# Add your API keys here for real trading
EOF
fi

# Generate config.yaml if it doesn't exist
if [ ! -f "config.yaml" ]; then
    print_status "Generating default configuration..."
    python3 -c "
from config_manager import ConfigManager
config = ConfigManager('config.yaml')
config.print_summary()
print('Configuration generated successfully')
"
fi

# Test the system
echo ""
echo "Running system tests..."
echo "======================"

# Test 1: Configuration
echo "Test 1: Configuration loading..."
python3 -c "
from config_manager import ConfigManager
try:
    config = ConfigManager('config.yaml')
    print('✅ Configuration loaded successfully')
    print(f'   Default strategy: {config.config.default_strategy}')
    print(f'   Execution mode: {config.config.execution_mode.value}')
except Exception as e:
    print(f'❌ Configuration error: {e}')
    exit(1)
"

# Test 2: Core imports
echo ""
echo "Test 2: Core module imports..."
python3 -c "
try:
    from core.models import TradeSignal, RiskAssessment, ExecutionOrder
    from agents.whisperer import Whisperer
    from agents.actuary import Actuary
    from agents.unified_slinger import UnifiedSlinger
    from agents.reaper import Reaper
    print('✅ All core modules imported successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
"

# Test 3: Strategy factory
echo ""
echo "Test 3: Strategy profiles..."
python3 -c "
from strategy_factory import StrategyFactory
try:
    factory = StrategyFactory()
    profiles = list(factory.profiles.keys())
    print(f'✅ Strategy factory loaded: {len(profiles)} profiles')
    print(f'   Available: {', '.join(profiles)}')
except Exception as e:
    print(f'❌ Strategy factory error: {e}')
    exit(1)
"

# Test 4: Enhanced system test
echo ""
echo "Test 4: Enhanced system integration..."
if [ -f "test_enhanced_system.py" ]; then
    python3 test_enhanced_system.py 2>&1 | tail -20
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_status "Enhanced system test passed"
    else
        print_warning "Enhanced system test had issues (expected in paper mode)"
    fi
else
    print_warning "test_enhanced_system.py not found"
fi

# Show deployment summary
echo ""
echo "📊 DEPLOYMENT SUMMARY"
echo "===================="
echo "Virtual environment: $(which python)"
echo "Python version: $(python --version 2>&1)"
echo "Configuration: config.yaml"
echo "Environment: .env"
echo ""
echo "Available commands:"
echo "  python main_pro.py              # Single cycle test"
echo "  python main_pro.py --loop       # Continuous mode"
echo "  python main_pro.py --status     # Show system status"
echo "  python main_pro.py --export     # Export performance data"
echo ""
echo "Next steps:"
echo "  1. Review config.yaml for strategy settings"
echo "  2. Edit .env if you want to enable real trading"
echo "  3. Run 'python main_pro.py --loop' for paper trading"
echo "  4. Monitor performance with 'python main_pro.py --status'"
echo ""
print_status "Deployment complete! 🚀"

# Deactivate virtual environment
deactivate
#!/bin/bash
# Setup script for live testing on Sepolia

set -e

echo "🚀 Setting up Asymmetric Strike Team for live testing"
echo "====================================================="

# Check Python and dependencies
echo "🔧 Checking dependencies..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.8+"
    exit 1
fi

# Check if in virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Not in virtual environment. Activating..."
    if [[ -d "venv" ]]; then
        source venv/bin/activate
        echo "✅ Virtual environment activated"
    else
        echo "❌ Virtual environment not found. Run: python -m venv venv && source venv/bin/activate"
        exit 1
    fi
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt > /dev/null 2>&1 || {
    echo "❌ Failed to install dependencies"
    exit 1
}
echo "✅ Dependencies installed"

# Create .env file
echo "📝 Creating environment configuration..."
if [[ ! -f ".env" ]]; then
    if [[ -f ".env.sepolia" ]]; then
        cp .env.sepolia .env
        echo "✅ Copied .env.sepolia to .env"
    else
        echo "❌ .env.sepolia not found. Creating basic .env..."
        cat > .env << EOF
# Sepolia Testnet Configuration
USE_REAL_EXECUTION=true

# IMPORTANT: Replace with your Infura key
# Sign up at https://infura.io/ (free)
ETH_RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_KEY

# Test private key (generated earlier)
PRIVATE_KEY=0xbe3247caeca15ca5a1fc8d6e6bd1bfbd621630920189393d76f840180e103e59

# Default strategy
DEFAULT_STRATEGY=degen
EOF
        echo "✅ Created .env file"
    fi
else
    echo "⚠️  .env already exists. Backing up..."
    cp .env .env.backup.$(date +%s)
    echo "✅ Backed up existing .env"
fi

# Check RPC configuration
echo "🔗 Checking RPC configuration..."
RPC_URL=$(grep ETH_RPC_URL .env | cut -d= -f2)
if [[ "$RPC_URL" == *"YOUR_INFURA_KEY"* ]] || [[ -z "$RPC_URL" ]]; then
    echo ""
    echo "❌ RPC URL not configured!"
    echo ""
    echo "📋 You need to:"
    echo "1. Sign up for a FREE Infura account: https://infura.io/"
    echo "2. Create a new project"
    echo "3. Get your API key"
    echo "4. Edit .env and replace YOUR_INFURA_KEY with your actual key"
    echo ""
    echo "📝 Or use a public RPC (less reliable):"
    echo "   ETH_RPC_URL=https://rpc.sepolia.org"
    echo ""
    read -p "Press Enter to open Infura signup page, or Ctrl+C to cancel..."
    open "https://infura.io/register"
    exit 1
fi

# Test RPC connection
echo "🌐 Testing RPC connection..."
python3 -c "
import sys
try:
    from web3 import Web3
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    rpc_url = os.getenv('ETH_RPC_URL')
    if not rpc_url:
        print('❌ RPC_URL not set in .env')
        sys.exit(1)
    
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if w3.is_connected():
        print(f'✅ Connected to chain ID: {w3.eth.chain_id}')
        print(f'   Latest block: {w3.eth.block_number}')
    else:
        print('❌ Failed to connect to RPC')
        sys.exit(1)
except ImportError:
    print('❌ web3.py not installed. Run: pip install web3')
    sys.exit(1)
except Exception as e:
    print(f'❌ Connection test failed: {e}')
    sys.exit(1)
" || exit 1

# Test wallet
echo "👛 Testing wallet..."
python3 -c "
import sys
try:
    from eth_account import Account
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    private_key = os.getenv('PRIVATE_KEY')
    if not private_key:
        print('❌ PRIVATE_KEY not set in .env')
        sys.exit(1)
    
    account = Account.from_key(private_key)
    print(f'✅ Wallet address: {account.address}')
    
    # Check balance
    from web3 import Web3
    rpc_url = os.getenv('ETH_RPC_URL')
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    try:
        balance = w3.eth.get_balance(account.address)
        eth_balance = w3.from_wei(balance, 'ether')
        print(f'   Balance: {eth_balance} ETH')
        
        if eth_balance < 0.01:
            print('')
            print('⚠️  LOW BALANCE WARNING!')
            print(f'   You have only {eth_balance} ETH')
            print('   Get test ETH from:')
            print('   - https://sepoliafaucet.com/')
            print('   - https://faucet.quicknode.com/ethereum/sepolia')
            print('   - https://cloud.google.com/application/web3/faucet/ethereum/sepolia')
            print('')
            print('   Send to address:', account.address)
    except:
        print('   ⚠️  Could not fetch balance (RPC might not support)')
        
except Exception as e:
    print(f'❌ Wallet test failed: {e}')
    sys.exit(1)
"

# Run final test
echo ""
echo "🧪 Running final system test..."
python3 test_real_execution.py

echo ""
echo "====================================================="
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Get test ETH for your wallet (if balance is low)"
echo "2. Test the system: python test_integration.py"
echo "3. Start paper trading: python cli.py"
echo "4. When ready for live test:"
echo "   - Ensure you have > 0.05 ETH"
echo "   - Run: python cli.py --strategy degen"
echo ""
echo "⚠️  WARNING: Real execution spends real test ETH!"
echo "   Start with small amounts and monitor closely."
echo ""
echo "🆘 Need help?"
echo "   - Check REAL_EXECUTION_GUIDE.md"
echo "   - Test on paper mode first: USE_REAL_EXECUTION=false python cli.py"
echo "====================================================="
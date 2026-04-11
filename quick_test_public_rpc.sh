#!/bin/bash
# Quick test with public RPC (no Infura account needed)

set -e

echo "⚡ Quick Test with Public RPC"
echo "=============================="

# Use public Sepolia RPC
PUBLIC_RPC="https://rpc.sepolia.org"

# Create test .env
cat > .env.test_public << EOF
USE_REAL_EXECUTION=true
ETH_RPC_URL=$PUBLIC_RPC
PRIVATE_KEY=0xbe3247caeca15ca5a1fc8d6e6bd1bfbd621630920189393d76f840180e103e59
DEFAULT_STRATEGY=degen
EOF

echo "📝 Using public RPC: $PUBLIC_RPC"
echo "👛 Test wallet: 0xD5f2660578Fa6dfB7f0D2Ae96536C17D42a2988a"
echo ""

# Test connection
echo "🔗 Testing connection to public RPC..."
python3 -c "
import sys
try:
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider('$PUBLIC_RPC'))
    if w3.is_connected():
        print(f'✅ Connected to chain ID: {w3.eth.chain_id}')
        print(f'   Network: {w3.net.version}')
        print(f'   Latest block: {w3.eth.block_number}')
    else:
        print('❌ Failed to connect to public RPC')
        print('   Try a different public RPC:')
        print('   - https://ethereum-sepolia.publicnode.com')
        print('   - https://rpc2.sepolia.org')
        sys.exit(1)
except Exception as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
"

echo ""
echo "💰 Get test ETH for: 0xD5f2660578Fa6dfB7f0D2Ae96536C17D42a2988a"
echo "   Faucets:"
echo "   1. https://sepoliafaucet.com/ (needs Alchemy)"
echo "   2. https://faucet.quicknode.com/ethereum/sepolia (needs QuickNode)"
echo "   3. https://cloud.google.com/application/web3/faucet/ethereum/sepolia (Google Cloud)"
echo ""

# Check balance
echo "👛 Checking balance..."
python3 -c "
import sys
try:
    from web3 import Web3
    from eth_account import Account
    
    w3 = Web3(Web3.HTTPProvider('$PUBLIC_RPC'))
    account = Account.from_key('0xbe3247caeca15ca5a1fc8d6e6bd1bfbd621630920189393d76f840180e103e59')
    address = account.address
    
    try:
        balance = w3.eth.get_balance(address)
        eth_balance = w3.from_wei(balance, 'ether')
        print(f'Address: {address}')
        print(f'Balance: {eth_balance} ETH')
        
        if eth_balance > 0.01:
            print('✅ Sufficient balance for testing!')
            print('')
            print('🚀 Ready for live test!')
            print('Run: DOTENV_PATH=.env.test_public python cli.py --strategy degen')
        else:
            print('❌ Insufficient balance. Get test ETH first.')
            print('')
            print('📝 After getting ETH, run:')
            print('   DOTENV_PATH=.env.test_public python cli.py --strategy degen')
    except Exception as e:
        print(f'⚠️  Could not fetch balance: {e}')
        print('   (Public RPC might be rate-limited)')
        
except Exception as e:
    print(f'❌ Error: {e}')
"

echo ""
echo "📝 Alternative: Test with paper trading first"
echo "   USE_REAL_EXECUTION=false python cli.py"
echo ""
echo "🔧 For better reliability, get an Infura key:"
echo "   https://infura.io/register (free)"
echo "=============================="
#!/bin/bash
# MCP Integration Demo Script

echo "🚀 Asymmetric Strike Team - MCP Integration Demo"
echo "================================================"
echo ""

# Set Python path
export PYTHONPATH=.:$PYTHONPATH

echo "1. Testing imports..."
python3 -c "
import sys
try:
    from main_mcp_integrated import convert_signal_to_mcp_format
    print('✅ main_mcp_integrated imports work')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"

echo ""
echo "2. Listing available strategies..."
python3 main_mcp_integrated.py --list 2>/dev/null | head -20

echo ""
echo "3. Running single cycle in hybrid mode..."
echo "   (This will simulate both DEX and CEX execution)"
echo ""
python3 main_mcp_integrated.py --strategy degen --mcp-mode hybrid 2>&1 | tail -50

echo ""
echo "4. Running single cycle in MCP-only mode..."
echo "   (This will simulate only CEX execution via PHANTOM)"
echo ""
python3 main_mcp_integrated.py --strategy sniper --mcp-mode mcp-only 2>&1 | tail -30

echo ""
echo "5. Checking logs..."
if [ -d "logs" ]; then
    echo "📁 Log directory exists"
    ls -la logs/*.json 2>/dev/null | head -5
else
    echo "📁 No logs directory yet"
fi

if [ -d "data" ]; then
    echo "📁 Data directory exists"
    ls -la data/*.json 2>/dev/null | head -5
else
    echo "📁 No data directory yet"
fi

echo ""
echo "✅ Demo completed!"
echo ""
echo "Next steps:"
echo "1. Run continuous scanning: python3 main_mcp_integrated.py --loop --interval 300"
echo "2. Try different strategies: --strategy sniper, shadow_clone, etc."
echo "3. Enable live mode: export USE_REAL_EXECUTION=true"
echo ""
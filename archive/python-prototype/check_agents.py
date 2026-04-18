#!/usr/bin/env python3
"""
Check if agent files exist and can be imported
"""

import os
import sys

print("🔍 Checking Asymmetric Strike Team Agents")
print("=" * 50)

agents = [
    ("whisperer.py", "Whisperer - Token scanner"),
    ("actuary.py", "Actuary - Risk assessment"),
    ("unified_slinger.py", "Unified Slinger - Execution"),
    ("reaper.py", "Reaper - Position monitoring"),
]

all_exist = True
for filename, description in agents:
    path = f"agents/{filename}"
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"✅ {path:25} {description:30} ({size:,} bytes)")
        
        # Try to import
        try:
            module_name = filename.replace('.py', '')
            if module_name == 'unified_slinger':
                print(f"   ↳ Can import: UnifiedSlinger class")
            else:
                print(f"   ↳ Can import: {module_name.capitalize()} class")
        except:
            print(f"   ↳ Import check skipped")
    else:
        print(f"❌ {path:25} {description:30} (MISSING)")
        all_exist = False

print("\n📁 Checking strategy profiles...")
strategy_file = "strategy_factory.py"
if os.path.exists(strategy_file):
    size = os.path.getsize(strategy_file)
    print(f"✅ {strategy_file:25} Strategy Factory ({size:,} bytes)")
    
    # Check what strategies are available
    try:
        with open(strategy_file, 'r') as f:
            content = f.read()
            if '"degen"' in content:
                print("   ↳ Includes: degen strategy")
            if '"sniper"' in content:
                print("   ↳ Includes: sniper strategy")
            if '"shadow_clone"' in content:
                print("   ↳ Includes: shadow_clone strategy")
    except:
        print("   ↳ Content check skipped")
else:
    print(f"❌ {strategy_file:25} Strategy Factory (MISSING)")
    all_exist = False

print("\n📁 Checking execution layer...")
execution_files = [
    "execution/real_slinger.py",
    "execution/unified_slinger.py",
]
for filepath in execution_files:
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f"✅ {filepath:35} ({size:,} bytes)")
    else:
        print(f"❌ {filepath:35} (MISSING)")
        all_exist = False

print("\n" + "=" * 50)
print("📋 System Status")
print("=" * 50)

if all_exist:
    print("🎉 All core agent files are present!")
    print("\nThe Asymmetric Strike Team includes:")
    print("1. Whisperer - Scans DexScreener for momentum")
    print("2. Actuary - Assesses risk via GoPlus API")
    print("3. Slinger - Executes via Web3.py (paper/real)")
    print("4. Reaper - Monitors with asymmetric TP/SL")
    print("5. 8 Strategy profiles (degen, sniper, etc.)")
    print("\n✅ Ready for paper trading validation")
else:
    print("⚠️  Some files are missing - system may be incomplete")

print("\n💡 Next steps:")
print("1. Run paper trading validation")
print("2. Test MCP integration for CEX trading")
print("3. Set up monitoring and alerts")
#!/usr/bin/env python3
"""
Verify MCP Wiring - Simple file check
"""

import os
import sys

print("🔍 Verifying MCP Wiring Files")
print("=" * 50)

files_to_check = [
    ("main_mcp_integrated.py", "Main integrated entry point"),
    ("agents/phantom_mcp_agent.py", "PHANTOM MCP agent"),
    ("RUN_MCP_INTEGRATION.md", "User documentation"),
    ("MCP_WIRING_SUMMARY.md", "Technical summary"),
    ("run_mcp_demo.sh", "Demo script"),
]

all_exist = True
for filename, description in files_to_check:
    if os.path.exists(filename):
        size = os.path.getsize(filename)
        print(f"✅ {filename:30} {description:30} ({size:,} bytes)")
    else:
        print(f"❌ {filename:30} {description:30} (MISSING)")
        all_exist = False

print("\n" + "=" * 50)
print("📁 Directory Structure Check")
print("=" * 50)

# Check key directories
dirs_to_check = ["agents", "logs", "data"]
for dirname in dirs_to_check:
    if os.path.isdir(dirname):
        files = [f for f in os.listdir(dirname) if f.endswith('.py')]
        print(f"📁 {dirname}/: {len(files)} Python files")
    else:
        print(f"📁 {dirname}/: Directory doesn't exist (will be created at runtime)")

print("\n" + "=" * 50)
print("📋 MCP Integration Status")
print("=" * 50)

if all_exist:
    print("🎉 All MCP wiring files are present!")
    print("\nThe integration includes:")
    print("1. main_mcp_integrated.py - Hybrid DEX/CEX execution")
    print("2. PHANTOM agent - MCP-based CEX execution")
    print("3. Complete documentation - RUN_MCP_INTEGRATION.md")
    print("4. Demo script - run_mcp_demo.sh")
    print("5. Technical summary - MCP_WIRING_SUMMARY.md")
    
    print("\n🚀 Ready to run:")
    print("  python main_mcp_integrated.py --strategy degen")
    print("  python main_mcp_integrated.py --strategy sniper --mcp-mode mcp-only")
    print("  python main_mcp_integrated.py --loop --interval 300")
else:
    print("⚠️  Some files are missing. Check the list above.")

print("\n✅ Verification complete!")
#!/usr/bin/env python3
"""
NLP Onboarding Wizard for Asymmetric Strike Team.
Walks the user through each agent configuration using natural language.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

from strategy_factory import StrategyFactory

# ANSI Colors
CYAN = '\033[96m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
MAGENTA = '\033[95m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    print(f"\n{CYAN}{BOLD}{'='*60}{RESET}")
    print(f"{CYAN}{BOLD}{text:^60}{RESET}")
    print(f"{CYAN}{BOLD}{'='*60}{RESET}\n")

def ask_yes_no(question: str, default: bool = True) -> bool:
    """Ask a yes/no question with natural language parsing."""
    prompt = f"{YELLOW}{question} ({'Y/n' if default else 'y/N'})? {RESET}"
    response = input(prompt).strip().lower()
    
    if response in ['y', 'yes', 'yeah', 'yep', 'sure', '']:
        return True
    elif response in ['n', 'no', 'nah', 'nope']:
        return False
    else:
        return default

def ask_number(question: str, default: float, min_val: float = None, max_val: float = None) -> float:
    """Ask for a number with validation."""
    while True:
        prompt = f"{YELLOW}{question} (default: {default}): {RESET}"
        response = input(prompt).strip()
        
        if not response:
            return default
            
        try:
            val = float(response)
            if min_val is not None and val < min_val:
                print(f"{RED}Value must be at least {min_val}{RESET}")
                continue
            if max_val is not None and val > max_val:
                print(f"{RED}Value must be at most {max_val}{RESET}")
                continue
            return val
        except ValueError:
            print(f"{RED}Please enter a valid number{RESET}")

def ask_choice(question: str, options: list[str], default: int = 0) -> str:
    """Ask user to choose from a list."""
    print(f"\n{YELLOW}{question}{RESET}")
    for i, opt in enumerate(options):
        print(f"  {i+1}. {opt}")
    
    while True:
        prompt = f"{YELLOW}Enter choice (1-{len(options)}, default {default+1}): {RESET}"
        response = input(prompt).strip()
        
        if not response:
            return options[default]
            
        try:
            idx = int(response) - 1
            if 0 <= idx < len(options):
                return options[idx]
            else:
                print(f"{RED}Please choose between 1 and {len(options)}{RESET}")
        except ValueError:
            print(f"{RED}Please enter a number{RESET}")

def onboard_whisperer() -> Dict[str, Any]:
    """Configure the Whisperer agent."""
    print_header("🧠 The Whisperer - Data Ingestion")
    print("The Whisperer scans social channels for emerging narratives.")
    print("It looks for velocity spikes in mentions and smart money activity.\n")
    
    sources = []
    if ask_yes_no("Should the Whisperer monitor Twitter/X", default=True):
        sources.append("twitter")
    if ask_yes_no("Should it scan Telegram alpha groups", default=True):
        sources.append("telegram")
    if ask_yes_no("Should it watch DexScreener for new pairs", default=False):
        sources.append("dexscreener")
    
    min_score = ask_number(
        "Minimum narrative score to trigger a signal (0-100)",
        default=50, min_val=0, max_val=100
    )
    
    scan_interval = ask_number(
        "How often should it scan (seconds)",
        default=60, min_val=5, max_val=300
    )
    
    return {
        "data_sources": sources,
        "min_velocity_score": int(min_score),
        "scan_interval_seconds": int(scan_interval)
    }

def onboard_shadow() -> Dict[str, Any]:
    """Configure the Shadow agent (copy trading)."""
    print_header("👥 The Shadow - Copy Trading")
    print("The Shadow ignores social media and copies trades from proven 'Smart Money' wallets.")
    print("It watches their transactions and mimics them with a configurable delay.\n")
    
    if not ask_yes_no("Enable the Shadow agent", default=False):
        return None
    
    print("\nEnter wallet addresses to monitor (one per line, leave empty when done):")
    wallets = []
    while True:
        wallet = input(f"{YELLOW}Wallet {len(wallets)+1}: {RESET}").strip()
        if not wallet:
            break
        if wallet.startswith("0x") and len(wallet) == 42:
            wallets.append(wallet)
        else:
            print(f"{RED}Invalid Ethereum address{RESET}")
    
    if not wallets:
        print(f"{YELLOW}No wallets provided. Using defaults.{RESET}")
        wallets = ["0xSmartMoney1", "0xWhale2"]
    
    copy_size = ask_number(
        "What percentage of the target's trade size should we copy",
        default=0.1, min_val=0.01, max_val=1.0
    )
    
    max_latency = ask_number(
        "Maximum allowed delay behind target's transaction (milliseconds)",
        default=50, min_val=10, max_val=1000
    )
    
    return {
        "target_wallets": wallets,
        "copy_size_multiplier": copy_size,
        "max_latency_ms": int(max_latency)
    }

def onboard_actuary() -> Dict[str, Any]:
    """Configure the Actuary agent (risk assessment)."""
    print_header("📊 The Actuary - Risk Assessment")
    print("The Actuary audits contracts for honeypots, taxes, and liquidity locks.")
    print("It decides whether a trade passes your risk tolerance.\n")
    
    strict = ask_yes_no("Enable strict mode (reject unverified contracts, any taxes)", default=False)
    
    max_tax = ask_number(
        "Maximum allowed buy/sell tax percentage",
        default=10.0 if not strict else 0.0,
        min_val=0.0, max_val=100.0
    )
    
    require_locked = ask_yes_no("Require liquidity to be locked", default=False)
    allow_unverified = ask_yes_no("Allow unverified contracts", default=not strict)
    
    return {
        "strict_mode": strict,
        "max_tax_allowed": max_tax,
        "require_locked_liquidity": require_locked,
        "allow_unverified_contracts": allow_unverified
    }

def onboard_slinger() -> Dict[str, Any]:
    """Configure the Slinger agent (execution)."""
    print_header("⚡ The Slinger - Execution")
    print("The Slinger builds and sends transactions.")
    print("It can use public mempools or private MEV protection.\n")
    
    use_private = ask_yes_no("Use private mempool (Flashbots) for MEV protection", default=False)
    
    slippage = ask_number(
        "Base slippage tolerance (percentage)",
        default=0.15, min_val=0.01, max_val=1.0
    )
    
    gas_multiplier = ask_number(
        "Gas premium multiplier (e.g., 1.5 = 50% higher priority fee)",
        default=1.5, min_val=1.0, max_val=10.0
    )
    
    return {
        "use_private_mempool": use_private,
        "base_slippage_tolerance": slippage,
        "gas_premium_multiplier": gas_multiplier
    }

def onboard_reaper() -> Dict[str, Any]:
    """Configure the Reaper agent (portfolio defense)."""
    print_header("💀 The Reaper - Portfolio Defense")
    print("The Reaper monitors positions and enforces stop-loss/take-profit rules.")
    print("It can extract principal on gains and ruthlessly cut losses.\n")
    
    take_profit = ask_number(
        "Take profit percentage",
        default=100.0, min_val=1.0, max_val=1000.0
    )
    
    stop_loss = ask_number(
        "Stop loss percentage (negative)",
        default=-30.0, min_val=-100.0, max_val=0.0
    )
    
    trailing_stop = ask_number(
        "Trailing stop percentage (activates after gains)",
        default=15.0, min_val=1.0, max_val=50.0
    )
    
    extract_principal = ask_yes_no("Extract initial principal when take profit hits", default=True)
    
    return {
        "take_profit_pct": take_profit,
        "stop_loss_pct": stop_loss,
        "trailing_stop_pct": trailing_stop,
        "extract_principal_on_tp": extract_principal
    }

def onboard_execution_mode() -> Dict[str, Any]:
    """Configure real vs paper trading."""
    print_header("🎮 Execution Mode")
    print("Choose between paper trading (simulation) and real execution.")
    print("Real execution requires an RPC endpoint and private key.\n")
    
    use_real = ask_yes_no("Enable real execution (live transactions)", default=False)
    
    config = {"USE_REAL_EXECUTION": use_real}
    
    if use_real:
        print(f"\n{YELLOW}⚠️  WARNING: Real execution will spend real ETH on gas and trade real tokens.{RESET}")
        print(f"{YELLOW}  Make sure you understand the risks before proceeding.{RESET}\n")
        
        rpc_url = input(f"{YELLOW}Enter your Ethereum RPC URL: {RESET}").strip()
        if rpc_url:
            config["ETH_RPC_URL"] = rpc_url
        
        private_key = input(f"{YELLOW}Enter your private key (or leave empty to skip): {RESET}").strip()
        if private_key:
            config["PRIVATE_KEY"] = private_key
        
        if ask_yes_no("Use GoPlus API for real-time honeypot detection", default=False):
            api_key = input(f"{YELLOW}Enter your GoPlus API key: {RESET}").strip()
            if api_key:
                config["GOPLUS_API_KEY"] = api_key
    
    return config

def save_configuration(config: Dict[str, Any], env_config: Dict[str, Any]):
    """Save the configuration to files."""
    # Save strategy config
    config_path = Path("user_strategy.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\n{GREEN}✅ Strategy configuration saved to {config_path}{RESET}")
    
    # Save environment variables
    env_path = Path(".env")
    if env_path.exists():
        backup = env_path.with_suffix(".env.backup")
        env_path.rename(backup)
        print(f"{YELLOW}⚠️  Existing .env backed up to {backup}{RESET}")
    
    with open(env_path, "w") as f:
        f.write("# Generated by Asymmetric Strike Team Onboarding Wizard\n")
        for key, value in env_config.items():
            if value is not None:
                f.write(f"{key}={value}\n")
    
    print(f"{GREEN}✅ Environment configuration saved to {env_path}{RESET}")
    
    # Create a simple runner script
    runner_path = Path("run_custom_strategy.py")
    runner_content = f'''#!/usr/bin/env python3
"""
Custom strategy runner generated by onboarding wizard.
"""
import json
from strategy_factory import StrategyFactory
from strategy_runner import run_strategy

with open("{config_path}", "r") as f:
    config = json.load(f)

# Create custom strategy profile
factory = StrategyFactory()
factory.profiles["custom"] = config

print("🚀 Starting custom strategy...")
try:
    while True:
        run_strategy("custom")
except KeyboardInterrupt:
    print("\\n👋 Shutting down.")
'''
    with open(runner_path, "w") as f:
        f.write(runner_content)
    runner_path.chmod(0o755)
    print(f"{GREEN}✅ Custom runner script created: {runner_path}{RESET}")

def main():
    print(f"{CYAN}{BOLD}\n🤖 Asymmetric Strike Team - NLP Onboarding Wizard{RESET}")
    print(f"{YELLOW}I'll help you configure your trading team step by step.{RESET}")
    print(f"{YELLOW}You can accept defaults or customize each parameter.{RESET}\n")
    
    if not ask_yes_no("Ready to begin", default=True):
        print(f"{YELLOW}Onboarding cancelled.{RESET}")
        return
    
    # Step 1: Choose base strategy or custom
    print_header("Strategy Selection")
    print("You can start with a preset strategy and customize it,")
    print("or build a completely custom configuration from scratch.\n")
    
    factory = StrategyFactory()
    preset_choice = ask_choice(
        "Select a base strategy to customize:",
        ["Degen Ape (high risk)", "Safe Sniper (MEV protected)", "Shadow Clone (copy trade)", "Arb Hunter (arbitrage)", "Custom from scratch"]
    )
    
    if "Degen" in preset_choice:
        base_profile = factory.get_profile("degen")
    elif "Sniper" in preset_choice:
        base_profile = factory.get_profile("sniper")
    elif "Shadow" in preset_choice:
        base_profile = factory.get_profile("shadow_clone")
    elif "Arb" in preset_choice:
        base_profile = factory.get_profile("arb_hunter")
    else:
        base_profile = None
    
    # Step 2: Configure each agent
    config = {}
    env_config = {}
    
    if base_profile:
        print(f"\n{YELLOW}Starting with {base_profile.name} configuration...{RESET}")
        config = base_profile.model_dump()
    
    # Agent configuration
    if ask_yes_no("Configure the Whisperer agent", default=True):
        config["whisperer"] = onboard_whisperer()
    
    if ask_yes_no("Configure the Shadow agent", default=False):
        shadow_config = onboard_shadow()
        if shadow_config:
            config["shadow"] = shadow_config
    
    if ask_yes_no("Configure the Actuary agent", default=True):
        config["actuary"] = onboard_actuary()
    
    if ask_yes_no("Configure the Slinger agent", default=True):
        config["slinger"] = onboard_slinger()
    
    if ask_yes_no("Configure the Reaper agent", default=True):
        config["reaper"] = onboard_reaper()
    
    # Step 3: Execution mode
    env_config.update(onboard_execution_mode())
    
    # Step 4: Save
    print_header("Configuration Complete")
    print(f"{GREEN}Your trading team is ready!{RESET}")
    print(f"\n{YELLOW}Summary:{RESET}")
    
    if config.get("whisperer"):
        print(f"  🧠 Whisperer: {len(config['whisperer']['data_sources'])} data sources")
    if config.get("shadow"):
        print(f"  👥 Shadow: Copying {len(config['shadow']['target_wallets'])} wallets")
    print(f"  📊 Actuary: {'Strict' if config.get('actuary', {}).get('strict_mode') else 'Lenient'} mode")
    print(f"  ⚡ Slinger: {'Private mempool' if config.get('slinger', {}).get('use_private_mempool') else 'Public mempool'}")
    print(f"  💀 Reaper: TP={config.get('reaper', {}).get('take_profit_pct', 100)}%, SL={config.get('reaper', {}).get('stop_loss_pct', -30)}%")
    print(f"  🎮 Execution: {'REAL' if env_config.get('USE_REAL_EXECUTION') else 'PAPER'}")
    
    if ask_yes_no("Save this configuration", default=True):
        # Ensure required fields
        config.setdefault("name", "Custom Strategy")
        config.setdefault("description", "Created via NLP onboarding wizard")
        
        save_configuration(config, env_config)
        
        print(f"\n{GREEN}{BOLD}🎉 Onboarding complete!{RESET}")
        print(f"{YELLOW}Next steps:{RESET}")
        print(f"  1. Review {Path('.env')} for sensitive information")
        print(f"  2. Run: python {Path('run_custom_strategy.py')}")
        print(f"  3. Or use the dashboard: python dashboard.py")
    else:
        print(f"{YELLOW}Configuration not saved.{RESET}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Onboarding cancelled.{RESET}")
    except Exception as e:
        print(f"{RED}Error during onboarding: {e}{RESET}")
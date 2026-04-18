import sys
import time
import argparse
from strategy_factory import StrategyFactory
from strategy_runner import run_strategy

# ANSI Color Codes
CYAN = '\033[96m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
MAGENTA = '\033[95m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_banner():
    banner = rf"""
{CYAN}{BOLD}
    ___                                __       _      
   /   |  _______  ______ ___  ____   / /______(_)____ 
  / /| | / ___/ / / / __ `__ \/ __ \ / __/ ___/ / ___/ 
 / ___ |(__  ) /_/ / / / / / / / / // /_/ /  / / /__   
/_/  |_/____/\__,_/_/ /_/ /_/_/ /_(_)__/_/  /_/\___/   
                                                       
    S T R I K E   T E A M   C O M M A N D   C L I
{RESET}
"""
    print(banner)

def list_strategies(factory):
    print(f"\n{YELLOW}{BOLD}AVAILABLE STRATEGIES:{RESET}")
    print("-" * 50)
    for key, profile in factory.profiles.items():
        print(f"{GREEN}▶ {key}{RESET} : {BOLD}{profile.name}{RESET}")
        print(f"  {profile.description}")
        
        # Print Team Composition
        team = []
        if profile.whisperer: team.append("Whisperer")
        if profile.shadow: team.append("Shadow")
        if profile.sleuth: team.append("Sleuth")
        if profile.pathfinder: team.append("Pathfinder")
        team.append("Actuary")
        team.append("Slinger")
        team.append("Reaper")
        
        print(f"  {MAGENTA}Team:{RESET} {' -> '.join(team)}")
        print("-" * 50)

def interactive_menu(factory):
    print_banner()
    list_strategies(factory)
    
    while True:
        try:
            print(f"\n{CYAN}Select a strategy to launch (or 'q' to quit):{RESET}")
            choice = input(f"{BOLD}> {RESET}").strip().lower()
            
            if choice in ['q', 'quit', 'exit']:
                print("Exiting.")
                sys.exit(0)
                
            if choice in factory.profiles:
                print(f"\n{GREEN}[+] Booting Strategy: {choice}...{RESET}\n")
                time.sleep(1)
                
                # Infinite loop running the strategy cycle
                try:
                    while True:
                        run_strategy(choice)
                        print(f"{YELLOW}[*] Cycle complete. Sleeping before next iteration...{RESET}")
                        time.sleep(3)
                except KeyboardInterrupt:
                    print(f"\n\n{RED}[!] Strategy execution paused by user.{RESET}")
                    # Return to menu
                    continue
            else:
                print(f"{RED}[!] Invalid selection. Please type the key of the strategy.{RESET}")
        except KeyboardInterrupt:
            print("\nExiting.")
            sys.exit(0)

if __name__ == "__main__":
    factory = StrategyFactory()
    
    parser = argparse.ArgumentParser(description="Asymmetric Strike Team CLI")
    parser.add_argument("--strategy", type=str, help="Name of the strategy to run directly without menu.")
    parser.add_argument("--list", action="store_true", help="List available strategies and exit.")
    
    args = parser.parse_args()
    
    if args.list:
        print_banner()
        list_strategies(factory)
        sys.exit(0)
        
    if args.strategy:
        if args.strategy in factory.profiles:
            print_banner()
            print(f"{GREEN}[+] Booting Strategy: {args.strategy}...{RESET}\n")
            try:
                while True:
                    run_strategy(args.strategy)
                    time.sleep(3)
            except KeyboardInterrupt:
                print(f"\n{RED}[!] Shutting down.{RESET}")
                sys.exit(0)
        else:
            print(f"{RED}[!] Strategy '{args.strategy}' not found.{RESET}")
            sys.exit(1)
            
    # Default to interactive menu if no args provided
    interactive_menu(factory)

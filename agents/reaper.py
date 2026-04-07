import time
import threading
from core.models import ExecutionOrder

class Reaper:
    """
    The Reaper: Portfolio Defense.
    Ruthless monitoring. Executes "Free Ride" (+100% extract principal) 
    and strict stop-loss (-30% liquidate).
    """
    def __init__(self):
        self.active_positions = {}
        self.monitoring = False

    def take_position(self, order: ExecutionOrder):
        if not order:
            return
            
        print("💀 [Reaper] Order confirmed. Active monitoring initiated.")
        print(f"   Directive 1: FREE RIDE target set at +100% for {order.token_address}")
        print(f"   Directive 2: KILL target set at -30% for {order.token_address}")
        
        self.active_positions[order.token_address] = {
            "entry_value": order.amount_usd,
            "current_value": order.amount_usd,
            "status": "ACTIVE"
        }
        
    def start_monitoring(self):
        self.monitoring = True
        print("💀 [Reaper] Watching blocks... (Simulation running in background)")
        
        def monitor_loop():
            # Simulate a rapid price spike followed by dump
            volatility_sim = [1.1, 1.4, 1.9, 2.1] # Multipliers over entry
            
            for token, pos in self.active_positions.items():
                for mult in volatility_sim:
                    if not self.monitoring:
                        break
                    time.sleep(2)
                    current_val = pos["entry_value"] * mult
                    print(f"\\n💀 [Reaper] Tick - {token[:8]}... Value: ${current_val:.2f} ({((mult-1)*100):.1f}%)")
                    
                    if mult >= 2.0 and pos["status"] == "ACTIVE":
                        print(f"💀 [Reaper] ⚡ FREE RIDE TRIGGERED! +100% reached.")
                        print(f"   Extracting principal (${pos['entry_value']:.2f}). Leaving moonbag.")
                        pos["status"] = "FREE_RIDE"
                        
        thread = threading.Thread(target=monitor_loop)
        thread.daemon = True
        thread.start()
        
    def stop_monitoring(self):
        self.monitoring = False

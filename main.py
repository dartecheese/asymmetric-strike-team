import time
from dotenv import load_dotenv

from agents.whisperer import Whisperer
from agents.actuary import Actuary
from agents.slinger import Slinger
from agents.reaper import Reaper

def main():
    load_dotenv()
    
    print("\\n" + "="*60)
    print("🚀 ASYMMETRIC STRIKE TEAM: INITIALIZING DEGEN PROTOCOL")
    print("="*60 + "\\n")
    
    # Initialize Team
    whisperer = Whisperer()
    actuary = Actuary(max_allowed_tax=0.25) # Give it 25% tolerance for degen plays
    slinger = Slinger()
    reaper = Reaper()
    
    # Execution Flow
    signal = whisperer.scan_firehose()
    print("-" * 60)
    
    assessment = actuary.assess_risk(signal)
    print("-" * 60)
    
    order = slinger.execute_order(assessment, chain_id=signal.chain)
    print("-" * 60)
    
    if order:
        reaper.take_position(order)
        reaper.start_monitoring()
        
        # Let simulation run for a bit
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            print("Shutting down...")
            
        reaper.stop_monitoring()
        print("\\n💀 [Reaper] Monitoring offline. Session closed.")

if __name__ == '__main__':
    main()
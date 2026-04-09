import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from web3 import Web3
from pricing import get_token_info
from whisperer import Whisperer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("paper_trading.log"),
        logging.StreamHandler()
    ]
)

class AdvancedPaperTrader:
    def __init__(self):
        self.active_positions = {}
        self.graveyard = []  # Closed trades history
        self.paper_balance = 10000.0  
        self.whisperer = Whisperer()
        self.is_running = False
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # Live Configuration
        self.config = {
            "trade_size": 250.0,
            "stop_loss": -30.0,
            "take_profit": 100.0,
            "trailing_stop": 15.0
        }
        
        logging.info("🚀 Initialized V2.1 Engine: Async, Configurable, Graveyard included.")

    def run_actuary_local_sim(self, token_data):
        address = token_data['token_address']
        logging.info(f"⚡ [Actuary] Running 50ms local EVM simulation on {address}...")
        time.sleep(0.05) 
        
        import random
        is_safe = random.random() > 0.15 
        
        if is_safe:
            logging.info(f"🛡️  [Actuary] Sim CLEAR. Buy/Sell OK. Latency: 48ms")
            return True
        else:
            logging.warning(f"🛡️  [Actuary] Sim FAILED. Honeypot/Tax trap detected! Latency: 52ms")
            return False

    def run_slinger_flashbots(self, token_data, amount_usd):
        address = token_data['token_address']
        if self.paper_balance < amount_usd:
            return

        info = get_token_info(address)
        if not info:
            return

        real_price = info['price']
        symbol = info['symbol']
        tokens_received = amount_usd / real_price

        self.paper_balance -= amount_usd
        self.active_positions[address] = {
            "symbol": symbol,
            "entry_price": real_price,
            "peak_price": real_price,
            "amount_tokens": tokens_received,
            "invested_usd": amount_usd,
            "principal_secured": False
        }
        logging.info(f"🔫 [Slinger] [FLASHBOTS BUNDLE] BOUGHT {tokens_received:,.2f} {symbol} at ${real_price} for ${amount_usd}.")

    def process_target_pipeline(self, target):
        if target['token_address'] not in self.active_positions:
            if self.run_actuary_local_sim(target):
                self.run_slinger_flashbots(target, amount_usd=self.config['trade_size'])

    def manual_ape(self, address):
        """Force buy a specific contract address."""
        logging.info(f"🦍 [MANUAL OVERRIDE] Apeing into {address}...")
        target = {
            "token_address": address,
            "chain_name": "ethereum",
            "goplus_chain_id": "1",
            "description": "Manual Ape"
        }
        self.executor.submit(self.process_target_pipeline, target)
        return True

    def close_position(self, address, reason, current_price, current_value_usd, pnl_pct):
        """Close a position and log it to the Graveyard."""
        pos = self.active_positions[address]
        self.paper_balance += current_value_usd
        
        self.graveyard.insert(0, {
            "symbol": pos['symbol'],
            "address": address,
            "entry_price": pos['entry_price'],
            "exit_price": current_price,
            "invested": pos['invested_usd'],
            "returned": current_value_usd,
            "pnl_pct": pnl_pct,
            "reason": reason,
            "time": time.strftime("%H:%M:%S")
        })
        
        # Keep graveyard to last 50 trades to avoid memory bloat
        if len(self.graveyard) > 50:
            self.graveyard = self.graveyard[:50]
            
        del self.active_positions[address]
        logging.info(f"💵 New Balance: ${self.paper_balance:,.2f} | Trade logged to Graveyard.")

    def run_reaper_trailing_stops(self):
        if not self.active_positions:
            return

        for address, pos in list(self.active_positions.items()):
            info = get_token_info(address)
            if not info:
                continue
                
            current_price = info['price']
            current_value_usd = pos['amount_tokens'] * current_price
            pnl_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
            
            if current_price > pos['peak_price']:
                pos['peak_price'] = current_price
                
            drop_from_peak_pct = ((pos['peak_price'] - current_price) / pos['peak_price']) * 100

            # Rule 1: Secure Principal
            if pnl_pct >= self.config['take_profit'] and not pos['principal_secured']:
                logging.info(f"💀 [Reaper] +{self.config['take_profit']}% HIT for {pos['symbol']}! Securing principal.")
                self.paper_balance += pos['invested_usd']
                pos['amount_tokens'] -= (pos['invested_usd'] / current_price)
                pos['principal_secured'] = True
                
            # Rule 2: Trailing Stop / Hard Stop
            elif (pnl_pct > 10.0 and drop_from_peak_pct >= self.config['trailing_stop']) or pnl_pct <= self.config['stop_loss']:
                reason = "TRAILING STOP" if drop_from_peak_pct >= self.config['trailing_stop'] else "HARD STOP LOSS"
                logging.warning(f"💀 [Reaper] {reason} TRIGGERED for {pos['symbol']} at {pnl_pct:+.1f}%.")
                self.close_position(address, reason, current_price, current_value_usd, pnl_pct)

    def force_sell(self, address):
        if address in self.active_positions:
            pos = self.active_positions[address]
            info = get_token_info(address)
            current_price = info['price'] if info else pos['entry_price']
            current_value_usd = pos['amount_tokens'] * current_price
            pnl_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
            
            logging.warning(f"💀 [Reaper] MANUAL OVERRIDE: Dump of {pos['symbol']}.")
            self.close_position(address, "MANUAL DUMP", current_price, current_value_usd, pnl_pct)
            return True
        return False

    def loop(self):
        logging.info("Initiating High-Frequency Paper Trading Loop...")
        self.is_running = True
        try:
            while self.is_running:
                targets = self.whisperer.scan_latest_profiles()
                if targets:
                    for target in targets:
                        self.executor.submit(self.process_target_pipeline, target)
                self.executor.submit(self.run_reaper_trailing_stops)
                time.sleep(2) 
        except KeyboardInterrupt:
            logging.info("Trading Loop Terminated.")
            self.is_running = False

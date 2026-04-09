import time
import logging
from web3 import Web3
from actuary import check_token_security
from pricing import get_token_info
from whisperer import Whisperer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("paper_trading.log"),
        logging.StreamHandler()
    ]
)

RPC_URL = "https://cloudflare-eth.com"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

class PaperTrader:
    def __init__(self):
        self.active_positions = {}
        self.paper_balance = 10000.0  # $10,000 USD mock balance
        self.whisperer = Whisperer()
        logging.info(f"🚀 Initialized Paper Trader. Connected to ETH RPC: {w3.is_connected()}")
        logging.info(f"💵 Starting Mock Balance: ${self.paper_balance:,.2f}")

    def run_actuary(self, token_data):
        """Actuary assesses real risk via GoPlus API."""
        address = token_data['token_address']
        chain_id = token_data['goplus_chain_id']
        chain_name = token_data['chain_name']
        
        logging.info(f"🛡️  [Actuary] Assessing real on-chain risk for {address} on {chain_name}...")
        report = check_token_security(chain_id, address)
        
        if report and report['safe']:
            logging.info(f"🛡️  [Actuary] Risk Assessment: CLEAR. Buy Tax: {report['buy_tax']}% | Sell Tax: {report['sell_tax']}%")
            return True
        elif report:
            logging.warning(f"🛡️  [Actuary] Risk Assessment: REJECTED. Honeypot: {report['is_honeypot']}, Taxes: Buy {report['buy_tax']}% / Sell {report['sell_tax']}%")
            return False
        else:
            logging.warning("🛡️  [Actuary] Risk Assessment: FAILED to fetch data. Rejecting to be safe.")
            return False

    def run_slinger(self, token_data, amount_usd=100.0):
        """Slinger builds the TX but DOES NOT broadcast."""
        address = token_data['token_address']
        logging.info(f"🔫 [Slinger] Preparing attack vector for {address}...")
        
        if self.paper_balance < amount_usd:
            logging.error("🔫 [Slinger] INSUFFICIENT PAPER FUNDS.")
            return

        info = get_token_info(address)
        if not info:
            logging.error(f"🔫 [Slinger] Failed to get real price/symbol for {address}. Aborting trade.")
            return

        real_price = info['price']
        symbol = info['symbol']
        tokens_received = amount_usd / real_price

        # Update paper state
        self.paper_balance -= amount_usd
        self.active_positions[address] = {
            "symbol": symbol,
            "entry_price": real_price,
            "amount_tokens": tokens_received,
            "invested_usd": amount_usd
        }

        logging.info(f"🔫 [Slinger] [PAPER TX] BOUGHT {tokens_received:,.2f} {symbol} at ${real_price} for ${amount_usd}.")
        logging.info(f"💵 Remaining Paper Balance: ${self.paper_balance:,.2f}")

    def force_sell(self, address):
        """Allows manual intervention to dump a token via the dashboard."""
        if address in self.active_positions:
            pos = self.active_positions[address]
            from pricing import get_token_info
            info = get_token_info(address)
            
            # Use live price if available, else fallback to entry to clear it
            current_price = info['price'] if info else pos['entry_price']
            current_value_usd = pos['amount_tokens'] * current_price
            
            logging.warning(f"💀 [Reaper] MANUAL OVERRIDE: Executing emergency dump of {pos['symbol']}.")
            self.paper_balance += current_value_usd
            del self.active_positions[address]
            logging.info(f"💵 New Paper Balance: ${self.paper_balance:,.2f}")
            return True
        return False

    def run_reaper(self):
        """Reaper monitors active positions for take-profit/stop-loss using live prices."""
        if not self.active_positions:
            return

        logging.info("💀 [Reaper] Checking vital signs of active positions...")

        for address, pos in list(self.active_positions.items()):
            # Get real current price
            info = get_token_info(address)
            if not info:
                continue
                
            current_price = info['price']
            current_value_usd = pos['amount_tokens'] * current_price
            pnl_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100

            logging.info(f"💀 [Reaper] Tick - {pos['symbol']} Value: ${current_value_usd:,.2f} ({pnl_pct:+.1f}%)")

            # Reaper Rules: Cut at -30%, Take Principal at +100%
            if pnl_pct <= -30.0:
                logging.warning(f"💀 [Reaper] STOP LOSS TRIGGERED for {pos['symbol']}. Executing paper dump.")
                self.paper_balance += current_value_usd
                del self.active_positions[address]
                logging.info(f"💵 New Paper Balance: ${self.paper_balance:,.2f}")
            elif pnl_pct >= 100.0:
                logging.info(f"💀 [Reaper] TAKE PROFIT TRIGGERED for {pos['symbol']}. Securing the bag.")
                self.paper_balance += current_value_usd
                del self.active_positions[address]
                logging.info(f"💵 New Paper Balance: ${self.paper_balance:,.2f}")

    def loop(self):
        logging.info("Initiating Live Paper Trading Loop...")
        self.is_running = True
        try:
            while self.is_running:
                print("-" * 60)
                
                # 1. Whisperer polls DexScreener for newly marketed tokens
                targets = self.whisperer.scan_latest_profiles()
                
                for target in targets:
                    if target['token_address'] not in self.active_positions:
                        # 2. Actuary checks the token against GoPlus
                        if self.run_actuary(target):
                            # 3. Slinger buys it
                            self.run_slinger(target, amount_usd=250.0)
                            time.sleep(1) # small delay to respect API limits
                
                # 4. Reaper manages existing positions
                self.run_reaper()
                
                # Sleep before next cycle
                time.sleep(10) 
        except KeyboardInterrupt:
            logging.info("Paper Trading Loop Terminated by User.")
            self.is_running = False

if __name__ == "__main__":
    trader = PaperTrader()
    trader.loop()

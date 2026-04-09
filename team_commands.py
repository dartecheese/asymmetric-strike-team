import time
import random

class TeamCommands:
    def __init__(self, trader):
        self.trader = trader
        self.commands = {
            "panic": self.panic_mode,
            "nuke": self.nuke_all_positions,
            "yolo": self.yolo_mode,
            "stealth": self.stealth_mode,
            "stats": self.show_stats,
            "help": self.show_help
        }
    
    def panic_mode(self):
        """Emergency: Dump everything, lock down trading, and go to cash."""
        if not self.trader.active_positions:
            return "💀 [Reaper] PANIC MODE: No positions to dump. Already in cash."
        
        count = len(self.trader.active_positions)
        total_dumped = 0
        
        for address in list(self.trader.active_positions.keys()):
            pos = self.trader.active_positions[address]
            # Simulate panic dump at market price
            from pricing import get_token_info
            info = get_token_info(address)
            current_price = info['price'] if info else pos['entry_price']
            current_value = pos['amount_tokens'] * current_price
            total_dumped += current_value
            self.trader.paper_balance += current_value
            del self.trader.active_positions[address]
        
        # Lock down trading by setting trade size to 0
        self.trader.config['trade_size'] = 0.0
        
        return f"🚨 [SYSTEM] PANIC MODE ACTIVATED! Dumped {count} positions for ${total_dumped:,.2f}. Trading locked (size=0)."
    
    def nuke_all_positions(self):
        """Aggressive: Force sell everything immediately, but keep trading active."""
        if not self.trader.active_positions:
            return "💣 [Slinger] NUKE: No active targets. Standing by."
        
        count = len(self.trader.active_positions)
        for address in list(self.trader.active_positions.keys()):
            self.trader.force_sell(address)
        
        return f"💣 [Slinger] NUKE COMPLETE. Obliterated {count} positions. Trading remains active."
    
    def yolo_mode(self):
        """Maximum risk: Double trade size, widen stop loss, disable trailing stops."""
        old_size = self.trader.config['trade_size']
        self.trader.config.update({
            'trade_size': old_size * 2.0,
            'stop_loss': -50.0,  # Wider stop loss
            'trailing_stop': 999.0  # Effectively disable trailing stops
        })
        return f"🤑 [SYSTEM] YOLO MODE ENGAGED! Trade size: ${old_size} → ${self.trader.config['trade_size']}. Stop loss: -30% → -50%. Let it ride!"
    
    def stealth_mode(self):
        """Reduce footprint: Halve trade size, tighten stops, increase scanning interval."""
        old_size = self.trader.config['trade_size']
        self.trader.config.update({
            'trade_size': max(50.0, old_size / 2.0),
            'stop_loss': -15.0,  # Tighter stop loss
            'trailing_stop': 8.0  # Tighter trailing stop
        })
        return f"🕵️ [SYSTEM] STEALTH MODE ACTIVATED. Trade size: ${old_size} → ${self.trader.config['trade_size']}. Stops tightened. Scanning reduced."
    
    def show_stats(self):
        """Display comprehensive team statistics."""
        total_invested = sum(pos['invested_usd'] for pos in self.trader.active_positions.values())
        avg_position_size = total_invested / len(self.trader.active_positions) if self.trader.active_positions else 0
        
        # Calculate win rate from graveyard
        wins = sum(1 for trade in self.trader.graveyard if trade['pnl_pct'] > 0)
        total_trades = len(self.trader.graveyard)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        stats = f"""
📊 [SYSTEM] TEAM STATS:
• Active Positions: {len(self.trader.active_positions)}
• Total Invested: ${total_invested:,.2f}
• Avg Position Size: ${avg_position_size:,.2f}
• Paper Balance: ${self.trader.paper_balance:,.2f}
• Graveyard Trades: {total_trades}
• Win Rate: {win_rate:.1f}% ({wins}/{total_trades})
• Config: Size=${self.trader.config['trade_size']}, TP={self.trader.config['take_profit']}%, SL={self.trader.config['stop_loss']}%
        """
        return stats.strip()
    
    def show_help(self):
        """Display all available team commands."""
        help_text = """
🎮 [SYSTEM] TEAM COMMANDS:
• "panic" - Emergency dump all positions, lock trading, go to cash
• "nuke" - Aggressively sell all positions but keep trading active
• "yolo" - Double trade size, widen stops, disable trailing stops
• "stealth" - Halve trade size, tighten stops, reduce footprint
• "stats" - Show comprehensive team statistics and performance
• "help" - Display this command list

Type these in the chat or use via API.
        """
        return help_text.strip()
    
    def execute(self, command):
        """Execute a team command."""
        cmd = command.lower().strip()
        if cmd in self.commands:
            return self.commands[cmd]()
        else:
            return f"❌ [SYSTEM] Unknown command: '{command}'. Type 'help' for available commands."

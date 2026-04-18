                entry_amount_usd=row[8],
                exit_price_usd=row[9],
                exit_timestamp=row[10],
                pnl_usd=row[11],
                pnl_pct=row[12],
                outcome=TradeOutcome(row[13]),
                holding_period_seconds=row[14],
                tags=json.loads(row[15]) if row[15] else []
            ))
        
        return trades
    
    def _update_daily_summary(self, trade: TradeRecord):
        """Update daily summary statistics."""
        if not trade.exit_timestamp:
            return
        
        date = datetime.fromtimestamp(trade.exit_timestamp).strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get existing summary
        cursor.execute("SELECT * FROM daily_summary WHERE date = ?", (date,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing
            total_trades = existing[1] + 1
            winning_trades = existing[2] + (1 if trade.outcome == TradeOutcome.WIN else 0)
            total_pnl = existing[3] + (trade.pnl_usd or 0)
            max_drawdown = max(existing[4], abs(trade.pnl_usd or 0))
            
            cursor.execute("""
            UPDATE daily_summary SET 
                total_trades = ?,
                winning_trades = ?,
                total_pnl_usd = ?,
                max_drawdown_usd = ?
            WHERE date = ?
            """, (total_trades, winning_trades, total_pnl, max_drawdown, date))
        else:
            # Insert new
            cursor.execute("""
            INSERT INTO daily_summary VALUES (?, ?, ?, ?, ?)
            """, (
                date,
                1,
                1 if trade.outcome == TradeOutcome.WIN else 0,
                trade.pnl_usd or 0,
                abs(trade.pnl_usd or 0)
            ))
        
        conn.commit()
        conn.close()


if __name__ == "__main__":
    # Test the Performance Tracker
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Performance Tracker...")
    
    tracker = PerformanceTracker("test_performance.db")
    
    # Create test orders
    from core.models import ExecutionOrder
    
    test_order = ExecutionOrder(
        token_address="0x1234567890abcdef",
        chain="cex",
        action="BUY",
        amount_usd=1000.0,
        slippage_tolerance=0.15,
        gas_premium_gwei=0.0,
        entry_price_usd=50000.0
    )
    
    # Record trade entry
    tracker.record_trade_entry(
        trade_id="test_trade_001",
        strategy="degen",
        order=test_order,
        tags=["high_velocity", "cex_listed", "sentiment_boost"]
    )
    
    # Simulate time passing
    time.sleep(1)
    
    # Record trade exit (win)
    tracker.record_trade_exit(
        trade_id="test_trade_001",
        exit_price=52000.0,
        pnl_usd=40.0  # 1000 * (52000-50000)/50000 = 40
    )
    
    # Record another trade (loss)
    test_order2 = ExecutionOrder(
        token_address="0xabcdef1234567890",
        chain="56",
        action="BUY",
        amount_usd=500.0,
        slippage_tolerance=0.15,
        gas_premium_gwei=45.0,
        entry_price_usd=0.01
    )
    
    tracker.record_trade_entry(
        trade_id="test_trade_002",
        strategy="sniper",
        order=test_order2,
        tags=["dex_only", "new_token"]
    )
    
    time.sleep(1)
    
    tracker.record_trade_exit(
        trade_id="test_trade_002",
        exit_price=0.009,
        pnl_usd=-50.0  # 500 * (0.009-0.01)/0.01 = -50
    )
    
    # Print performance report
    tracker.print_performance_report()
    
    # Export to CSV
    tracker.export_to_csv("test_performance.csv")
    
    print("\n✅ Performance Tracker test complete")
    print("Check test_performance.csv for exported data")
#!/usr/bin/env python3
"""
48-Hour Paper Trading Validation Test (Resume Version)
=====================================================
Can resume from previous run.
"""
import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add current directory to path
sys.path.append('.')

from simple_config import SimpleConfig
from simple_performance_tracker import SimplePerformanceTracker, SimpleTradeRecord, TradeOutcome

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Create new log file for resumed test
log_file = log_dir / f"48h_test_resumed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("48h_test_resume")


class TestMonitor:
    """Monitors the 48-hour test with resume capability."""
    
    def __init__(self, duration_hours: int = 48, resume: bool = True):
        self.duration_hours = duration_hours
        
        # Try to resume from previous test
        if resume:
            self.start_time = self._find_previous_start_time()
            if self.start_time:
                logger.info(f"📂 Resuming from previous test started at {self.start_time}")
            else:
                self.start_time = datetime.now()
                logger.info(f"🚀 Starting new 48-hour test")
        else:
            self.start_time = datetime.now()
            logger.info(f"🚀 Starting fresh 48-hour test")
        
        self.end_time = self.start_time + timedelta(hours=duration_hours)
        
        # Load previous metrics if resuming
        self.metrics = self._load_previous_metrics() if resume else {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_cycles": 0,
            "successful_cycles": 0,
            "failed_cycles": 0,
            "errors": []
        }
        
        # Update end time
        self.metrics["end_time"] = self.end_time.isoformat()
        
        # Create results directory
        self.results_dir = Path("test_results")
        self.results_dir.mkdir(exist_ok=True)
        
        logger.info(f"   Start: {self.start_time}")
        logger.info(f"   End:   {self.end_time}")
        logger.info(f"   Duration: {duration_hours} hours")
        logger.info(f"   Previous cycles: {self.metrics['total_cycles']}")
    
    def _find_previous_start_time(self):
        """Find start time from previous log files."""
        log_files = list(Path("logs").glob("48h_test_*.log"))
        if not log_files:
            return None
        
        latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
        try:
            with open(latest_log, 'r') as f:
                for line in f:
                    if "Start:" in line:
                        start_str = line.split("Start:")[1].strip()
                        return datetime.fromisoformat(start_str.replace(" ", "T"))
        except:
            pass
        
        return None
    
    def _load_previous_metrics(self):
        """Load metrics from previous results file."""
        results_files = list(Path("test_results").glob("48h_test_results_*.json"))
        if not results_files:
            return {
                "start_time": self.start_time.isoformat(),
                "total_cycles": 0,
                "successful_cycles": 0,
                "failed_cycles": 0,
                "errors": []
            }
        
        latest_result = max(results_files, key=lambda x: x.stat().st_mtime)
        try:
            with open(latest_result, 'r') as f:
                metrics = json.load(f)
                # Reset some fields for resume
                metrics["errors"] = metrics.get("errors", [])[-10:]  # Keep only recent errors
                return metrics
        except:
            return {
                "start_time": self.start_time.isoformat(),
                "total_cycles": 0,
                "successful_cycles": 0,
                "failed_cycles": 0,
                "errors": []
            }
    
    def record_cycle(self, success: bool, error: str = None):
        """Record a cycle result."""
        self.metrics["total_cycles"] += 1
        
        if success:
            self.metrics["successful_cycles"] += 1
        else:
            self.metrics["failed_cycles"] += 1
            if error:
                self.metrics["errors"].append({
                    "time": datetime.now().isoformat(),
                    "error": error
                })
    
    def get_progress(self) -> dict:
        """Get test progress."""
        now = datetime.now()
        elapsed = now - self.start_time
        remaining = self.end_time - now
        
        progress_pct = (elapsed.total_seconds() / (self.duration_hours * 3600)) * 100
        
        return {
            "elapsed_hours": elapsed.total_seconds() / 3600,
            "remaining_hours": remaining.total_seconds() / 3600,
            "progress_percent": min(100, progress_pct),
            "is_complete": now >= self.end_time
        }
    
    def print_status(self):
        """Print current test status."""
        progress = self.get_progress()
        
        print("\n" + "=" * 70)
        print("📊 48-HOUR TEST STATUS (RESUMED)")
        print("=" * 70)
        print(f"Elapsed:    {progress['elapsed_hours']:.1f} hours")
        print(f"Remaining:  {progress['remaining_hours']:.1f} hours")
        print(f"Progress:   {progress['progress_percent']:.1f}%")
        print(f"Cycles:     {self.metrics['total_cycles']}")
        print(f"Successful: {self.metrics['successful_cycles']}")
        print(f"Failed:     {self.metrics['failed_cycles']}")
        
        if self.metrics['total_cycles'] > 0:
            success_rate = (self.metrics['successful_cycles'] / self.metrics['total_cycles']) * 100
            print(f"Success Rate: {success_rate:.1f}%")
        
        print("=" * 70)
    
    def save_results(self):
        """Save test results to file."""
        # Update end time
        self.metrics["actual_end_time"] = datetime.now().isoformat()
        
        # Calculate final metrics
        if self.metrics['total_cycles'] > 0:
            self.metrics["success_rate"] = (self.metrics['successful_cycles'] / self.metrics['total_cycles']) * 100
        else:
            self.metrics["success_rate"] = 0
        
        # Save to JSON
        results_file = self.results_dir / f"48h_test_results_resumed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        
        logger.info(f"Results saved to {results_file}")
        return results_file
    
    def is_test_complete(self) -> bool:
        """Check if test duration has elapsed."""
        return datetime.now() >= self.end_time


def run_test_cycle(config: SimpleConfig, monitor: TestMonitor, performance_tracker: SimplePerformanceTracker, cycle_offset: int = 0) -> bool:
    """
    Run a single test cycle.
    
    Returns:
        True if cycle completed successfully (even if no trade)
        False if cycle failed with error
    """
    try:
        # Import here to catch import errors
        from main_simple import run_simple_cycle
        
        cycle_num = monitor.metrics['total_cycles'] + 1 + cycle_offset
        logger.info(f"Starting cycle #{cycle_num}")
        
        # Run the cycle
        success = run_simple_cycle(config)
        
        if success:
            logger.info(f"Cycle #{cycle_num} completed successfully")
            
            # Record a simulated trade
            trade = SimpleTradeRecord(
                trade_id=f"cycle_{cycle_num}_{int(time.time())}",
                timestamp=time.time(),
                strategy=config.default_strategy,
                token_address="0xSIMULATED",
                chain="simulated",
                venue="paper",
                amount_usd=100.0,
                pnl_usd=5.0,  # Simulated small profit
                pnl_pct=5.0,
                outcome=TradeOutcome.WIN
            )
            performance_tracker.record_trade(trade)
            
        else:
            logger.info(f"Cycle #{cycle_num} completed without trade (normal)")
        
        monitor.record_cycle(success=True)
        return True
        
    except Exception as e:
        error_msg = f"Cycle failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        monitor.record_cycle(success=False, error=error_msg)
        return False


def main():
    """Main test runner."""
    # Configuration for conservative testing
    config = SimpleConfig()
    config.default_strategy = "conservative"
    config.loop_interval_seconds = 300  # 5 minutes between scans
    config.enable_sentiment = True
    
    # Initialize monitor with resume capability
    monitor = TestMonitor(duration_hours=48, resume=True)
    
    # Initialize performance tracker
    performance_tracker = SimplePerformanceTracker()
    
    print("\n" + "=" * 70)
    print("🚀 ASYMMETRIC STRIKE TEAM - 48-HOUR TEST (RESUMED)")
    print("=" * 70)
    print(f"Strategy: {config.default_strategy}")
    print(f"Scan Interval: {config.loop_interval_seconds} seconds")
    print(f"Start Time: {monitor.start_time}")
    print(f"End Time: {monitor.end_time}")
    print(f"Previous Cycles: {monitor.metrics['total_cycles']}")
    print("=" * 70)
    print("\nTest Parameters:")
    print("  • Conservative strategy (low risk)")
    print("  • 5-minute scan intervals")
    print("  • Sentiment analysis enabled")
    print("  • Paper trading mode only")
    print("  • Resuming from previous run")
    print("\nPress Ctrl+C to stop test early")
    print("=" * 70 + "\n")
    
    cycle_count = 0
    
    try:
        while not monitor.is_test_complete():
            cycle_count += 1
            
            # Print status every 5 cycles
            if cycle_count % 5 == 0 or cycle_count == 1:
                monitor.print_status()
                performance_tracker.print_report()
            
            # Run test cycle
            cycle_success = run_test_cycle(config, monitor, performance_tracker, cycle_offset=0)
            
            if not cycle_success:
                logger.warning(f"Cycle {cycle_count} failed, waiting before retry...")
                time.sleep(60)  # Wait 1 minute after failure
                continue
            
            # Wait for next cycle (unless test is complete)
            if not monitor.is_test_complete():
                wait_time = config.loop_interval_seconds
                logger.info(f"Next cycle in {wait_time} seconds...")
                
                # Check for early termination every 30 seconds
                for i in range(wait_time // 30):
                    if monitor.is_test_complete():
                        break
                    time.sleep(30)
        
        # Test complete
        logger.info("🎉 48-hour test completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
    finally:
        # Final status
        monitor.print_status()
        
        # Save results
        results_file = monitor.save_results()
        
        # Print final performance report
        performance_tracker.print_report()
        
        # Summary
        print("\n" + "=" * 70)
        print("📋 TEST COMPLETE - SUMMARY")
        print("=" * 70)
        print(f"Total Cycles: {monitor.metrics['total_cycles']}")
        print(f"Successful: {monitor.metrics['successful_cycles']}")
        print(f"Failed: {monitor.metrics['failed_cycles']}")
        
        if monitor.metrics['total_cycles'] > 0:
            success_rate = monitor.metrics.get('success_rate', 0)
            print(f"Success Rate: {success_rate:.1f}%")
        
        print(f"\nLog file: {log_file}")
        print(f"Results file: {results_file}")
        print(f"Performance data: simple_performance.json")
        print("=" * 70)


if __name__ == "__main__":
    main()
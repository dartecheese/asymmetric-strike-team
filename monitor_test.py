#!/usr/bin/env python3
"""
Monitor 48-Hour Test Progress
=============================
Checks progress and reports status every 3 hours.
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add current directory to path
sys.path.append('.')

from simple_performance_tracker import SimplePerformanceTracker


def get_test_progress():
    """Get current test progress from log files."""
    log_dir = Path("logs")
    results_dir = Path("test_results")
    
    if not log_dir.exists():
        return {"status": "Test not started or logs not found"}
    
    # Find latest log file
    log_files = list(log_dir.glob("48h_test_*.log"))
    if not log_files:
        return {"status": "No test log files found"}
    
    latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
    
    # Read last few lines of log
    try:
        with open(latest_log, 'r') as f:
            lines = f.readlines()[-20:]  # Last 20 lines
    except:
        lines = ["Could not read log file"]
    
    # Find test start time from log
    start_time = None
    for line in lines:
        if "Start:" in line:
            try:
                start_str = line.split("Start:")[1].strip()
                start_time = datetime.fromisoformat(start_str.replace(" ", "T"))
                break
            except:
                pass
    
    # Calculate progress
    progress = {}
    if start_time:
        now = datetime.now()
        elapsed = now - start_time
        total_duration = timedelta(hours=48)
        remaining = total_duration - elapsed
        
        progress = {
            "start_time": start_time.isoformat(),
            "current_time": now.isoformat(),
            "elapsed_hours": elapsed.total_seconds() / 3600,
            "remaining_hours": max(0, remaining.total_seconds() / 3600),
            "progress_percent": min(100, (elapsed.total_seconds() / (48 * 3600)) * 100),
            "is_complete": elapsed >= total_duration
        }
    
    # Get performance metrics
    performance = {}
    try:
        tracker = SimplePerformanceTracker()
        metrics = tracker.get_metrics()
        performance = metrics
    except:
        performance = {"error": "Could not load performance data"}
    
    # Find latest results file
    result_files = list(results_dir.glob("48h_test_results_*.json"))
    if result_files:
        latest_result = max(result_files, key=lambda x: x.stat().st_mtime)
        try:
            with open(latest_result, 'r') as f:
                results = json.load(f)
        except:
            results = {"error": "Could not read results file"}
    else:
        results = {}
    
    return {
        "log_file": str(latest_log),
        "log_tail": "".join(lines[-10:]),  # Last 10 lines
        "progress": progress,
        "performance": performance,
        "results": results
    }


def print_progress_report(progress_data):
    """Print a formatted progress report."""
    print("\n" + "=" * 80)
    print("📊 48-HOUR TEST PROGRESS REPORT")
    print("=" * 80)
    
    progress = progress_data.get("progress", {})
    performance = progress_data.get("performance", {})
    
    if progress:
        print(f"Test Start:  {progress.get('start_time', 'Unknown')}")
        print(f"Current Time: {progress.get('current_time', 'Unknown')}")
        print(f"Elapsed:     {progress.get('elapsed_hours', 0):.1f} hours")
        print(f"Remaining:   {progress.get('remaining_hours', 0):.1f} hours")
        print(f"Progress:    {progress.get('progress_percent', 0):.1f}%")
        
        if progress.get("is_complete"):
            print("\n✅ TEST COMPLETE!")
        else:
            print(f"\n⏳ Test is {progress.get('progress_percent', 0):.1f}% complete")
    
    if performance and not isinstance(performance, str):
        print("\n📈 PERFORMANCE METRICS:")
        print(f"  Total Trades: {performance.get('total_trades', 0)}")
        print(f"  Winning Trades: {performance.get('winning_trades', 0)}")
        print(f"  Losing Trades: {performance.get('losing_trades', 0)}")
        print(f"  Win Rate: {performance.get('win_rate', 0):.1f}%")
        print(f"  Total P&L: ${performance.get('total_pnl_usd', 0):+.2f}")
    
    # Show recent log activity
    log_tail = progress_data.get("log_tail", "")
    if log_tail:
        print("\n📝 RECENT ACTIVITY:")
        print(log_tail)
    
    print("=" * 80)


def main():
    """Main monitoring function."""
    print(f"🔍 Checking test progress at {datetime.now().isoformat()}")
    
    try:
        progress_data = get_test_progress()
        print_progress_report(progress_data)
        
        # Save report to file
        report_dir = Path("monitoring_reports")
        report_dir.mkdir(exist_ok=True)
        
        report_file = report_dir / f"progress_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
        
        print(f"\n📄 Report saved to: {report_file}")
        
    except Exception as e:
        print(f"❌ Error getting progress: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
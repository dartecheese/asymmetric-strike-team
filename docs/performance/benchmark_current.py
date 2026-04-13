#!/usr/bin/env python3
"""
Benchmark Current Performance
Measures execution time of each component in the pipeline.
"""

import time
import cProfile
import pstats
import io
from datetime import datetime

def benchmark_imports():
    """Benchmark import times."""
    print("📦 Benchmarking Import Times")
    print("=" * 50)
    
    modules = [
        ("whisperer", "agents.whisperer"),
        ("actuary", "agents.actuary"),
        ("unified_slinger", "agents.unified_slinger"),
        ("reaper", "agents.reaper"),
        ("strategy_factory", "strategy_factory"),
        ("web3", "web3"),
        ("pydantic", "pydantic"),
    ]
    
    for name, module_path in modules:
        start = time.time()
        try:
            __import__(module_path)
            elapsed = time.time() - start
            print(f"{name:20} {elapsed:.3f}s")
        except ImportError as e:
            print(f"{name:20} ❌ Not installed: {e}")

def benchmark_whisperer():
    """Benchmark Whisperer performance."""
    print("\n🔍 Benchmarking Whisperer")
    print("=" * 50)
    
    try:
        from agents.whisperer import Whisperer
        
        whisperer = Whisperer(min_velocity_score=50)
        
        # Warm up
        print("Warming up...")
        for _ in range(2):
            try:
                signal = whisperer.scan_firehose()
                if signal:
                    print(f"  Found: {signal.token_symbol}")
            except:
                pass
        
        # Actual benchmark
        print("\nRunning benchmark (3 iterations):")
        times = []
        for i in range(3):
            start = time.time()
            try:
                signal = whisperer.scan_firehose()
                elapsed = time.time() - start
                times.append(elapsed)
                status = f"✓ {signal.token_symbol}" if signal else "✗ No signal"
                print(f"  Run {i+1}: {elapsed:.2f}s {status}")
            except Exception as e:
                elapsed = time.time() - start
                times.append(elapsed)
                print(f"  Run {i+1}: {elapsed:.2f}s ✗ Error: {e}")
        
        if times:
            avg = sum(times) / len(times)
            print(f"\n📊 Average: {avg:.2f}s")
            print(f"   Min: {min(times):.2f}s")
            print(f"   Max: {max(times):.2f}s")
            
    except ImportError as e:
        print(f"❌ Could not import Whisperer: {e}")

def benchmark_actuary():
    """Benchmark Actuary performance."""
    print("\n🛡️ Benchmarking Actuary")
    print("=" * 50)
    
    try:
        from agents.actuary import Actuary
        from agents.whisperer import Whisperer
        from core.models import TradeSignal
        
        actuary = Actuary(max_allowed_tax=0.05)
        whisperer = Whisperer(min_velocity_score=50)
        
        # Get a test signal
        print("Getting test signal...")
        signal = whisperer.scan_firehose()
        if not signal:
            print("❌ No signal found to test Actuary")
            return
        
        print(f"Testing with: {signal.token_symbol} on {signal.chain}")
        
        # Warm up
        print("Warming up...")
        for _ in range(2):
            try:
                assessment = actuary.assess_risk(signal)
            except:
                pass
        
        # Actual benchmark
        print("\nRunning benchmark (3 iterations):")
        times = []
        for i in range(3):
            start = time.time()
            try:
                assessment = actuary.assess_risk(signal)
                elapsed = time.time() - start
                times.append(elapsed)
                print(f"  Run {i+1}: {elapsed:.2f}s Risk: {assessment.risk_level.name}")
            except Exception as e:
                elapsed = time.time() - start
                times.append(elapsed)
                print(f"  Run {i+1}: {elapsed:.2f}s ✗ Error: {e}")
        
        if times:
            avg = sum(times) / len(times)
            print(f"\n📊 Average: {avg:.2f}s")
            
    except ImportError as e:
        print(f"❌ Could not import Actuary: {e}")

def benchmark_full_cycle():
    """Benchmark a full trading cycle."""
    print("\n🚀 Benchmarking Full Cycle")
    print("=" * 50)
    
    try:
        import main
        
        # Monkey-patch to capture timing
        original_run_cycle = main.run_cycle
        cycle_times = []
        
        def timed_run_cycle(*args, **kwargs):
            start = time.time()
            result = original_run_cycle(*args, **kwargs)
            elapsed = time.time() - start
            cycle_times.append(elapsed)
            return result
        
        main.run_cycle = timed_run_cycle
        
        print("Running 3 full cycles (this will take a while)...")
        
        for i in range(3):
            print(f"\n--- Cycle {i+1} ---")
            try:
                # Run in paper mode
                result = main.run_cycle(strategy="degen", paper_mode=True)
                print(f"  Result: {'Trade placed' if result else 'No trade'}")
                print(f"  Time: {cycle_times[-1]:.2f}s")
            except Exception as e:
                print(f"  ✗ Error: {e}")
        
        if cycle_times:
            avg = sum(cycle_times) / len(cycle_times)
            print(f"\n📊 Full cycle average: {avg:.2f}s")
            print(f"   Total for 3 cycles: {sum(cycle_times):.2f}s")
            
    except ImportError as e:
        print(f"❌ Could not run full cycle: {e}")

def profile_hotspots():
    """Profile the code to find bottlenecks."""
    print("\n🔥 Profiling for Hotspots")
    print("=" * 50)
    
    try:
        import main
        
        print("Running profiler on one cycle...")
        pr = cProfile.Profile()
        pr.enable()
        
        try:
            main.run_cycle(strategy="degen", paper_mode=True)
        except:
            pass
        
        pr.disable()
        
        # Print top 20 time-consuming functions
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats(20)
        
        print("Top 20 time-consuming functions:")
        print(s.getvalue()[:1000])  # First 1000 chars
        
    except Exception as e:
        print(f"❌ Profiling failed: {e}")

def main():
    """Run all benchmarks."""
    print(f"📊 Asymmetric Strike Team Performance Benchmark")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Python: {sys.version.split()[0]}")
    print()
    
    # Run benchmarks
    benchmark_imports()
    benchmark_whisperer()
    benchmark_actuary()
    
    # Full cycle takes longer, ask user
    print("\n" + "=" * 60)
    response = input("Run full cycle benchmark? (takes 1-2 minutes) [y/N]: ")
    if response.lower() == 'y':
        benchmark_full_cycle()
    
    print("\n" + "=" * 60)
    response = input("Run profiler to find hotspots? [y/N]: ")
    if response.lower() == 'y':
        profile_hotspots()
    
    print("\n✅ Benchmark complete!")
    print("\n📈 Next steps:")
    print("1. Review the timings above")
    print("2. Check which components are slowest")
    print("3. Refer to OPTIMIZATION_PLAN.md for improvement strategies")

if __name__ == "__main__":
    import sys
    main()
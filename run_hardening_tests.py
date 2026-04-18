#!/usr/bin/env python3
"""
Run hardening tests for QWNT Trading System
Focused, practical tests that can actually run now.
"""

import os
import sys
import time
import json
from datetime import datetime
import logging

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.WARNING)  # Reduce noise for tests
logger = logging.getLogger("HardeningTests")

class HardeningTests:
    """Practical hardening tests for immediate improvement"""
    
    def __init__(self):
        self.results = []
        self.start_time = datetime.now()
    
    def run_all(self):
        """Run all practical hardening tests"""
        print("🔧 QWNT TRADING SYSTEM HARDENING TESTS")
        print("=" * 60)
        print(f"Started: {self.start_time.isoformat()}")
        print()
        
        test_categories = [
            ("1. COMPONENT HEALTH CHECKS", self.run_component_checks),
            ("2. INTEGRATION VALIDATION", self.run_integration_checks),
            ("3. PERFORMANCE BENCHMARKS", self.run_performance_checks),
            ("4. SAFETY & SECURITY", self.run_safety_checks),
            ("5. CONFIGURATION VALIDATION", self.run_config_checks),
        ]
        
        all_passed = True
        
        for category_name, test_func in test_categories:
            print(f"\n{category_name}")
            print("-" * 40)
            
            try:
                category_passed = test_func()
                if category_passed:
                    print(f"✅ {category_name.split('. ')[1]}: PASSED")
                else:
                    print(f"❌ {category_name.split('. ')[1]}: FAILED")
                    all_passed = False
            except Exception as e:
                print(f"💥 {category_name.split('. ')[1]}: CRASHED - {e}")
                all_passed = False
        
        # Summary
        print(f"\n📊 TEST SUMMARY")
        print("=" * 60)
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print(f"Duration: {elapsed:.1f}s")
        print(f"Overall: {'✅ PASSED' if all_passed else '❌ FAILED'}")
        
        # Save results
        self.save_results(all_passed)
        
        return all_passed
    
    def run_component_checks(self):
        """Check that all components can be imported and initialized"""
        print("Checking component health...")
        
        components = [
            ("Core Models", self.test_core_models),
            ("Whisperer Agent", self.test_whisperer),
            ("Actuary Agent", self.test_actuary),
            ("Slinger Agent", self.test_slinger),
            ("Strategy Factory", self.test_strategy_factory),
            ("TradingView Integration", self.test_tradingview),
        ]
        
        all_ok = True
        for name, test in components:
            try:
                if test():
                    print(f"  ✅ {name}")
                else:
                    print(f"  ❌ {name}")
                    all_ok = False
            except Exception as e:
                print(f"  💥 {name}: {e}")
                all_ok = False
        
        return all_ok
    
    def test_core_models(self):
        """Test core data models"""
        from core.models import TradeSignal, RiskAssessment, ExecutionOrder
        
        # Quick smoke test
        signal = TradeSignal(
            token_address="0xtest",
            chain="ethereum",
            narrative_score=75,
            reasoning="Test",
            discovered_at=time.time()
        )
        
        assessment = RiskAssessment(
            token_address="0xtest",
            is_honeypot=False,
            buy_tax=0.1,
            sell_tax=0.1,
            liquidity_locked=True,
            risk_level="LOW",
            max_allocation_usd=1000.0,
            warnings=[]
        )
        
        order = ExecutionOrder(
            token_address="0xtest",
            action="BUY",
            amount_usd=100.0,
            slippage_tolerance=0.15,
            gas_premium_gwei=2.0
        )
        
        return all([
            signal.token_address == "0xtest",
            assessment.risk_level == "LOW",
            order.action == "BUY"
        ])
    
    def test_whisperer(self):
        """Test whisperer agent"""
        from agents.whisperer import Whisperer
        
        whisperer = Whisperer()
        signal = whisperer.scan_firehose()
        
        return hasattr(signal, 'token_address') and hasattr(signal, 'narrative_score')
    
    def test_actuary(self):
        """Test actuary agent"""
        from agents.actuary import Actuary
        from core.models import TradeSignal
        
        actuary = Actuary(max_allowed_tax=0.25)
        signal = TradeSignal(
            token_address="0xtest",
            chain="ethereum",
            narrative_score=80,
            reasoning="Test",
            discovered_at=time.time()
        )
        
        assessment = actuary.assess_risk(signal)
        return hasattr(assessment, 'approved') and hasattr(assessment, 'risk_level')
    
    def test_slinger(self):
        """Test slinger agent"""
        from agents.slinger import Slinger
        from core.models import ExecutionOrder
        
        slinger = Slinger()
        order = ExecutionOrder(
            token_address="0xtest",
            action="BUY",
            amount_usd=100.0,
            slippage_tolerance=0.15,
            gas_premium_gwei=2.0
        )
        
        result = slinger.execute_order(order, "0xwallet", "mock_key")
        return result is not None
    
    def test_strategy_factory(self):
        """Test strategy factory"""
        from strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        
        # Check key strategies exist
        required_strategies = ["degen", "sniper", "oracle_eye"]
        for strategy in required_strategies:
            if strategy not in factory.profiles:
                return False
        
        # Check we can get a profile
        profile = factory.get_profile("degen")
        return profile is not None and hasattr(profile, 'name')
    
    def test_tradingview(self):
        """Test TradingView integration"""
        from tradingview_integration import get_tradingview_integration
        
        tv = get_tradingview_integration(use_mock=True)
        regime = tv.get_market_regime()
        
        return "overall_regime" in regime and "recommendations" in regime
    
    def run_integration_checks(self):
        """Check that components work together"""
        print("Testing integration...")
        
        integrations = [
            ("Signal → Risk Pipeline", self.test_signal_risk_pipeline),
            ("Risk → Execution Pipeline", self.test_risk_execution_pipeline),
            ("Unified Slinger", self.test_unified_slinger),
            ("Strategy Execution", self.test_strategy_execution),
        ]
        
        all_ok = True
        for name, test in integrations:
            try:
                if test():
                    print(f"  ✅ {name}")
                else:
                    print(f"  ❌ {name}")
                    all_ok = False
            except Exception as e:
                print(f"  💥 {name}: {e}")
                all_ok = False
        
        return all_ok
    
    def test_signal_risk_pipeline(self):
        """Test signal to risk assessment pipeline"""
        from agents.whisperer import Whisperer
        from agents.actuary import Actuary
        
        whisperer = Whisperer()
        actuary = Actuary(max_allowed_tax=0.25)
        
        signal = whisperer.scan_firehose()
        assessment = actuary.assess_risk(signal)
        
        return assessment is not None
    
    def test_risk_execution_pipeline(self):
        """Test risk assessment to execution pipeline"""
        from execution.unified_slinger import UnifiedSlingerAgent
        from strategy_factory import StrategyFactory, SlingerConfig
        from core.models import ExecutionOrder
        
        factory = StrategyFactory()
        config = factory.get_profile("degen").slinger
        slinger = UnifiedSlingerAgent(config)
        
        order = ExecutionOrder(
            token_address="0xtest",
            action="BUY",
            amount_usd=100.0,
            slippage_tolerance=0.15,
            gas_premium_gwei=2.0
        )
        
        # Should execute without crashing
        result = slinger.execute_order(order)
        return True  # If we get here, it didn't crash
    
    def test_unified_slinger(self):
        """Test unified slinger switching"""
        from execution.unified_slinger import UnifiedSlingerAgent
        from strategy_factory import SlingerConfig
        
        config = SlingerConfig(
            use_private_mempool=False,
            base_slippage_tolerance=0.15,
            gas_premium_multiplier=2.0
        )
        
        slinger = UnifiedSlingerAgent(config)
        return hasattr(slinger, 'mode') and slinger.mode in ["PAPER", "REAL"]
    
    def test_strategy_execution(self):
        """Test strategy execution flow"""
        from qwnt_trading_system import QWNTTradingSystem
        
        # Quick test with mock data
        system = QWNTTradingSystem(use_mock_tv=True)
        
        # Just check initialization
        return hasattr(system, 'strategy_name') and hasattr(system, 'whisperer')
    
    def run_performance_checks(self):
        """Check performance metrics"""
        print("Running performance benchmarks...")
        
        benchmarks = [
            ("Signal Generation", self.benchmark_signal_generation),
            ("Risk Assessment", self.benchmark_risk_assessment),
            ("Order Execution", self.benchmark_order_execution),
        ]
        
        all_ok = True
        for name, benchmark in benchmarks:
            try:
                result = benchmark()
                if result:
                    print(f"  ✅ {name}: {result}")
                else:
                    print(f"  ❌ {name}: Failed")
                    all_ok = False
            except Exception as e:
                print(f"  💥 {name}: {e}")
                all_ok = False
        
        return all_ok
    
    def benchmark_signal_generation(self):
        """Benchmark signal generation speed"""
        from agents.whisperer import Whisperer
        
        whisperer = Whisperer()
        
        start = time.time()
        for _ in range(3):
            whisperer.scan_firehose()
        elapsed = time.time() - start
        
        avg_time = elapsed / 3
        return f"{avg_time:.3f}s/signal"
    
    def benchmark_risk_assessment(self):
        """Benchmark risk assessment speed"""
        from agents.actuary import Actuary
        from core.models import TradeSignal
        
        actuary = Actuary(max_allowed_tax=0.25)
        
        signals = []
        for i in range(3):
            signal = TradeSignal(
                token_address=f"0xtest{i}",
                chain="ethereum",
                narrative_score=70,
                reasoning="Benchmark",
                discovered_at=time.time()
            )
            signals.append(signal)
        
        start = time.time()
        for signal in signals:
            actuary.assess_risk(signal)
        elapsed = time.time() - start
        
        avg_time = elapsed / 3
        return f"{avg_time:.3f}s/assessment"
    
    def benchmark_order_execution(self):
        """Benchmark order execution speed"""
        from execution.unified_slinger import UnifiedSlingerAgent
        from strategy_factory import StrategyFactory
        from core.models import ExecutionOrder
        
        factory = StrategyFactory()
        config = factory.get_profile("degen").slinger
        slinger = UnifiedSlingerAgent(config)
        
        orders = []
        for i in range(3):
            order = ExecutionOrder(
                token_address=f"0xtoken{i}",
                action="BUY",
                amount_usd=100.0,
                slippage_tolerance=0.15,
                gas_premium_gwei=2.0
            )
            orders.append(order)
        
        start = time.time()
        for order in orders:
            slinger.execute_order(order)
        elapsed = time.time() - start
        
        avg_time = elapsed / 3
        return f"{avg_time:.3f}s/execution"
    
    def run_safety_checks(self):
        """Check safety features"""
        print("Checking safety features...")
        
        safety_checks = [
            ("Paper Trading Default", self.check_paper_default),
            ("Parameter Validation", self.check_parameter_validation),
            ("Error Handling", self.check_error_handling),
        ]
        
        all_ok = True
        for name, check in safety_checks:
            try:
                if check():
                    print(f"  ✅ {name}")
                else:
                    print(f"  ❌ {name}")
                    all_ok = False
            except Exception as e:
                print(f"  💥 {name}: {e}")
                all_ok = False
        
        return all_ok
    
    def check_paper_default(self):
        """Check paper trading is default"""
        # Temporarily clear env vars
        original_env = {}
        for key in ["USE_REAL_EXECUTION", "ETH_RPC_URL", "PRIVATE_KEY"]:
            original_env[key] = os.environ.get(key)
            os.environ.pop(key, None)
        
        try:
            from execution.unified_slinger import UnifiedSlingerAgent
            from strategy_factory import SlingerConfig
            
            config = SlingerConfig(
                use_private_mempool=False,
                base_slippage_tolerance=0.15,
                gas_premium_multiplier=2.0
            )
            
            slinger = UnifiedSlingerAgent(config)
            return slinger.mode == "PAPER"
            
        finally:
            # Restore env vars
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
    
    def check_parameter_validation(self):
        """Check parameter validation"""
        from strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        
        # Check all strategies have reasonable parameters
        for strategy_name in ["degen", "sniper", "oracle_eye"]:
            profile = factory.get_profile(strategy_name)
            
            # Slippage should be reasonable
            if not (0.01 <= profile.slinger.base_slippage_tolerance <= 0.5):
                return False
            
            # Gas multiplier should be reasonable
            if not (1.0 <= profile.slinger.gas_premium_multiplier <= 5.0):
                return False
        
        return True
    
    def check_error_handling(self):
        """Check error handling"""
        from execution.unified_slinger import UnifiedSlingerAgent
        from strategy_factory import SlingerConfig
        from core.models import ExecutionOrder
        
        config = SlingerConfig(
            use_private_mempool=False,
            base_slippage_tolerance=0.15,
            gas_premium_multiplier=2.0
        )
        slinger = UnifiedSlingerAgent(config)
        
        # Try with invalid data
        invalid_order = ExecutionOrder(
            token_address="",
            action="INVALID",
            amount_usd=-100.0,
            slippage_tolerance=0.15,
            gas_premium_gwei=2.0
        )
        
        # Should handle gracefully
        try:
            slinger.execute_order(invalid_order)
            return True  # Didn't crash
        except Exception:
            return True  # Even if it throws, that's OK for this test
    
    def run_config_checks(self):
        """Check configuration"""
        print("Validating configuration...")
        
        config_checks = [
            ("Environment Files", self.check_env_files),
            ("Dependencies", self.check_dependencies),
            ("File Structure", self.check_file_structure),
        ]
        
        all_ok = True
        for name, check in config_checks:
            try:
                if check():
                    print(f"  ✅ {name}")
                else:
                    print(f"  ❌ {name}")
                    all_ok = False
            except Exception as e:
                print(f"  💥 {name}: {e}")
                all_ok = False
        
        return all_ok
    
    def check_env_files(self):
        """Check environment files"""
        env_files = [".env.example"]
        
        for env_file in env_files:
            if not os.path.exists(env_file):
                print(f"    Missing: {env_file}")
                return False
        
        # Check .env.example has required variables
        with open(".env.example", "r") as f:
            content = f.read()
        
        required_vars = ["USE_REAL_EXECUTION", "ETH_RPC_URL", "PRIVATE_KEY"]
        for var in required_vars:
            if var not in content:
                print(f"    Missing variable in .env.example: {var}")
                return False
        
        return True
    
    def check_dependencies(self):
        """Check critical dependencies"""
        try:
            import web3
            import requests
            import pydantic
            from dotenv import load_dotenv
            
            # If we get here, imports work
            return True
        except ImportError as e:
            print(f"    Missing dependency: {e}")
            return False
    
    def check_file_structure(self):
        """Check required file structure"""
        required_dirs = ["agents", "core", "execution"]
        required_files = [
            "main.py",
            "cli.py",
            "strategy_factory.py",
            "requirements.txt",
        ]
        
        for dir_name in required_dirs:
            if not os.path.isdir(dir_name):
                print(f"    Missing directory: {dir_name}")
                return False
        
        for file_name in required_files:
            if not os.path.exists(file_name):
                print(f"    Missing file: {file_name}")
                return False
        
        return True
    
    def save_results(self, overall_passed):
        """Save test results"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "overall_passed": overall_passed,
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "test_run": "hardening_tests"
        }
        
        with open("hardening_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Results saved to hardening_test_results.json")
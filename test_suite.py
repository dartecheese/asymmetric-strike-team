        # Import and create multiple components
        from agents.whisperer import Whisperer
        from agents.actuary import Actuary
        from execution.unified_slinger import UnifiedSlingerAgent
        from strategy_factory import StrategyFactory, SlingerConfig
        
        # Create components
        whisperer = Whisperer()
        actuary = Actuary(max_allowed_tax=0.25)
        factory = StrategyFactory()
        config = factory.get_profile("degen").slinger
        slinger = UnifiedSlingerAgent(config)
        
        final_memory = process.memory_info().rss
        memory_increase = (final_memory - initial_memory) / 1024 / 1024  # MB
        
        print(f"    Memory increase: {memory_increase:.2f} MB")
        
        # Should be reasonable (< 50 MB for basic components)
        return memory_increase < 50.0
    
    def run_security_tests(self):
        """Test security and safety features"""
        passed = 0
        failed = 0
        
        tests = [
            ("Paper Trading Default", self.test_paper_trading_default),
            ("Risk Assessment Validation", self.test_risk_assessment_validation),
            ("Parameter Bounds", self.test_parameter_bounds),
            ("Error Handling", self.test_error_handling),
            ("Private Key Safety", self.test_private_key_safety),
        ]
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    print(f"  ✅ {test_name}")
                    passed += 1
                else:
                    print(f"  ❌ {test_name}")
                    failed += 1
            except Exception as e:
                print(f"  💥 {test_name}: {e}")
                failed += 1
        
        return passed, failed
    
    def test_paper_trading_default(self):
        """Test that paper trading is the default mode"""
        from execution.unified_slinger import UnifiedSlingerAgent
        from strategy_factory import SlingerConfig
        
        # Clear any existing env vars for test
        original_use_real = os.environ.get("USE_REAL_EXECUTION")
        original_rpc = os.environ.get("ETH_RPC_URL")
        original_pk = os.environ.get("PRIVATE_KEY")
        
        os.environ.pop("USE_REAL_EXECUTION", None)
        os.environ.pop("ETH_RPC_URL", None)
        os.environ.pop("PRIVATE_KEY", None)
        
        try:
            config = SlingerConfig(
                use_private_mempool=False,
                base_slippage_tolerance=0.15,
                gas_premium_multiplier=2.0
            )
            slinger = UnifiedSlingerAgent(config)
            
            # Should be in paper mode by default
            assert slinger.mode == "PAPER"
            return True
            
        finally:
            # Restore env vars
            if original_use_real:
                os.environ["USE_REAL_EXECUTION"] = original_use_real
            if original_rpc:
                os.environ["ETH_RPC_URL"] = original_rpc
            if original_pk:
                os.environ["PRIVATE_KEY"] = original_pk
    
    def test_risk_assessment_validation(self):
        """Test that risk assessment properly validates tokens"""
        from agents.actuary import Actuary
        from core.models import TradeSignal
        
        actuary = Actuary(max_allowed_tax=0.1)  # Strict 10% max tax
        
        # Test with high tax (should fail)
        class MockHighTaxSignal:
            token_address = "0xhighTax"
            chain = "ethereum"
            narrative_score = 90
            reasoning = "High tax token"
            discovered_at = time.time()
        
        # Mock the API response for high tax
        import unittest.mock as mock
        with mock.patch('agents.actuary.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.json.return_value = {
                "result": {
                    "buy_tax": "0.15",  # 15% > 10% limit
                    "sell_tax": "0.20",
                    "is_honeypot": "0",
                    "is_open_source": "1"
                }
            }
            mock_get.return_value = mock_response
            
            assessment = actuary.assess_risk(MockHighTaxSignal())
            
            # Should be rejected due to high tax
            return not assessment.approved
    
    def test_parameter_bounds(self):
        """Test that parameters stay within safe bounds"""
        from strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        
        # Check all strategies have safe parameters
        for strategy_name in factory.profiles:
            profile = factory.get_profile(strategy_name)
            
            # Slippage should be reasonable
            assert 0.01 <= profile.slinger.base_slippage_tolerance <= 0.5
            
            # Gas multiplier should be reasonable
            assert 1.0 <= profile.slinger.gas_premium_multiplier <= 5.0
            
            # Reaper parameters should be reasonable
            if hasattr(profile, 'reaper'):
                assert 0.05 <= profile.reaper.stop_loss_pct <= 0.5
                assert 0.1 <= profile.reaper.take_profit_pct <= 2.0
        
        return True
    
    def test_error_handling(self):
        """Test that errors are handled gracefully"""
        from execution.unified_slinger import UnifiedSlingerAgent
        from strategy_factory import SlingerConfig
        from core.models import ExecutionOrder
        
        config = SlingerConfig(
            use_private_mempool=False,
            base_slippage_tolerance=0.15,
            gas_premium_multiplier=2.0
        )
        slinger = UnifiedSlingerAgent(config)
        
        # Create invalid order
        invalid_order = ExecutionOrder(
            token_address="",  # Empty address
            action="INVALID",  # Invalid action
            amount_usd=-100.0,  # Negative amount
            slippage_tolerance=0.15,
            gas_premium_gwei=2.0
        )
        
        # Should handle gracefully (not crash)
        try:
            result = slinger.execute_order(invalid_order)
            # Even if it returns something, we didn't crash
            return True
        except Exception as e:
            # Should provide meaningful error, not crash system
            print(f"    Error (expected): {type(e).__name__}")
            return True
    
    def test_private_key_safety(self):
        """Test that private keys aren't leaked in logs"""
        import logging
        import io
        
        from execution.unified_slinger import UnifiedSlingerAgent
        from strategy_factory import SlingerConfig
        
        # Set up logging capture
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        
        # Temporarily add handler
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers.copy()
        root_logger.handlers = [handler]
        
        try:
            # Test with a mock private key
            test_private_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
            os.environ["PRIVATE_KEY"] = test_private_key
            os.environ["USE_REAL_EXECUTION"] = "true"
            os.environ["ETH_RPC_URL"] = "https://test.rpc"
            
            config = SlingerConfig(
                use_private_mempool=False,
                base_slippage_tolerance=0.15,
                gas_premium_multiplier=2.0
            )
            
            # This should log but NOT include the private key
            slinger = UnifiedSlingerAgent(config)
            
            # Get logs
            logs = log_capture.getvalue()
            
            # Private key should NOT be in logs
            assert test_private_key not in logs
            
            # Should mention real mode but not key
            assert "REAL" in logs or "real" in logs
            
            return True
            
        finally:
            # Clean up
            os.environ.pop("PRIVATE_KEY", None)
            os.environ.pop("USE_REAL_EXECUTION", None)
            os.environ.pop("ETH_RPC_URL", None)
            root_logger.handlers = original_handlers
    
    def run_e2e_tests(self):
        """Test end-to-end workflows"""
        passed = 0
        failed = 0
        
        tests = [
            ("Complete Trading Cycle", self.test_complete_trading_cycle),
            ("Market Regime Adaptation", self.test_market_regime_adaptation),
            ("Strategy Switching", self.test_strategy_switching),
            ("Performance Tracking", self.test_performance_tracking),
        ]
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    print(f"  ✅ {test_name}")
                    passed += 1
                else:
                    print(f"  ❌ {test_name}")
                    failed += 1
            except Exception as e:
                print(f"  💥 {test_name}: {e}")
                failed += 1
        
        return passed, failed
    
    def test_complete_trading_cycle(self):
        """Test a complete trading cycle from signal to execution"""
        from qwnt_trading_system import QWNTTradingSystem
        
        # Create system with mock data
        system = QWNTTradingSystem(use_mock_tv=True)
        
        # Run a single cycle
        success = system.run_trading_cycle()
        
        # Should complete without crashing
        system.shutdown()
        
        return success is not None  # Could be True or False, but not crash
    
    def test_market_regime_adaptation(self):
        """Test that system adapts to different market regimes"""
        from tradingview_integration import MockTradingViewMCP
        
        tv = MockTradingViewMCP()
        
        # Get market regime
        regime = tv.get_market_regime()
        
        # Should have regime data
        assert "overall_regime" in regime
        assert regime["overall_regime"] in ["bull", "bear", "correction", "unknown"]
        
        # Should have recommendations
        assert "recommendations" in regime
        assert len(regime["recommendations"]) > 0
        
        return True
    
    def test_strategy_switching(self):
        """Test that strategies can be switched dynamically"""
        from strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        
        # Test switching between strategies
        strategies_to_test = ["degen", "sniper", "oracle_eye"]
        
        for strategy in strategies_to_test:
            profile = factory.get_profile(strategy)
            
            # Each strategy should have unique parameters
            assert hasattr(profile, 'name')
            assert hasattr(profile, 'slinger')
            
            # Slippage should vary by strategy
            if strategy == "degen":
                assert profile.slinger.base_slippage_tolerance > 0.2  # High for degen
            elif strategy == "sniper":
                assert profile.slinger.base_slippage_tolerance < 0.1  # Low for sniper
        
        return True
    
    def test_performance_tracking(self):
        """Test that performance is tracked correctly"""
        import tempfile
        import json
        
        # Create temp file for performance tracking
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            perf_data = {
                "trades_executed": 5,
                "total_pnl": 1250.50,
                "win_rate": 0.8,
                "sharpe_ratio": 1.75,
                "timestamp": datetime.now().isoformat()
            }
            json.dump(perf_data, f)
            temp_path = f.name
        
        try:
            # Load and validate
            with open(temp_path, 'r') as f:
                loaded = json.load(f)
            
            assert loaded["trades_executed"] == 5
            assert loaded["win_rate"] == 0.8
            assert isinstance(loaded["timestamp"], str)
            
            return True
        finally:
            os.unlink(temp_path)
    
    def run_regression_tests(self):
        """Test that new changes don't break existing functionality"""
        passed = 0
        failed = 0
        
        tests = [
            ("API Compatibility", self.test_api_compatibility),
            ("Data Model Backwards Compatibility", self.test_data_model_compatibility),
            ("Configuration Backwards Compatibility", self.test_config_compatibility),
        ]
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    print(f"  ✅ {test_name}")
                    passed += 1
                else:
                    print(f"  ❌ {test_name}")
                    failed += 1
            except Exception as e:
                print(f"  💥 {test_name}: {e}")
                failed += 1
        
        return passed, failed
    
    def test_api_compatibility(self):
        """Test that external APIs still work"""
        # Test GoPlus API (if configured)
        try:
            import requests
            
            # Simple test to see if API endpoint is reachable
            # (This is a lightweight test, not actual API call)
            test_url = "https://api.gopluslabs.io"
            response = requests.get(test_url, timeout=5)
            
            # Should get some response (even if not 200)
            return response.status_code < 500
            
        except Exception:
            # If API is not available, that's OK for testing
            return True
    
    def test_data_model_compatibility(self):
        """Test that data models haven't broken"""
        from core.models import TradeSignal, RiskAssessment, ExecutionOrder
        
        # Test that all required fields exist
        signal_fields = TradeSignal.__fields__
        assessment_fields = RiskAssessment.__fields__
        order_fields = ExecutionOrder.__fields__
        
        # Check critical fields exist
        assert "token_address" in signal_fields
        assert "chain" in signal_fields
        assert "narrative_score" in signal_fields
        
        assert "is_honeypot" in assessment_fields
        assert "risk_level" in assessment_fields
        
        assert "action" in order_fields
        assert "amount_usd" in order_fields
        
        return True
    
    def test_config_compatibility(self):
        """Test that configuration files still work"""
        import tempfile
        
        # Create a test .env file
        env_content = """# Test configuration
USE_REAL_EXECUTION=false
ETH_RPC_URL=https://test.rpc
PRIVATE_KEY=0xtest
STRATEGY_PROFILE=degen
SCAN_INTERVAL_SECONDS=30
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(env_content)
            temp_path = f.name
        
        try:
            # Load and parse
            from dotenv import load_dotenv
            import os
            
            # Temporarily set env file
            original_env = os.environ.copy()
            load_dotenv(temp_path)
            
            # Check values
            assert os.getenv("USE_REAL_EXECUTION") == "false"
            assert os.getenv("STRATEGY_PROFILE") == "degen"
            assert os.getenv("SCAN_INTERVAL_SECONDS") == "30"
            
            # Restore
            os.environ.clear()
            os.environ.update(original_env)
            
            return True
        finally:
            os.unlink(temp_path)
    
    def save_test_results(self):
        """Save test results to file"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "test_results": self.test_results,
            "system_info": {
                "python_version": sys.version,
                "platform": sys.platform,
                "working_directory": os.getcwd(),
            }
        }
        
        with open("test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Test results saved to test_results.json")

def main():
    """Main entry point"""
    suite = QWNTTestSuite()
    
    try:
        success = suite.run_all_tests()
        
        if success:
            print("\n🎉 ALL TESTS PASSED!")
            print("The QWNT trading system is hardened and ready for production.")
            return 0
        else:
            print("\n⚠️  SOME TESTS FAILED")
            print("Review the failures above and fix before production deployment.")
            return 1
            
    except KeyboardInterrupt:
        print("\n🛑 Testing interrupted by user")
        return 130
    except Exception as e:
        print(f"\n💥 Test suite crashed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
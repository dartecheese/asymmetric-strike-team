# Changelog

All notable changes to the Asymmetric Strike Team project will be documented in this file.

## [Unreleased]

## [1.1.0] - 2026-04-11

### Added
- **Real Web3.py Execution Layer**: Integrated actual blockchain transaction execution
- **Unified Slinger**: `execution/unified_slinger.py` for automatic paper/real mode switching
- **8 Strategy Profiles**: degen, sniper, shadow_clone, arb_hunter, oracle_eye, liquidity_sentinel, yield_alchemist, forensic_sniper
- **Comprehensive Test Suite**: `test_real_execution.py`, `test_integration.py`
- **Setup Scripts**: `setup_live_test.sh`, `quick_test_public_rpc.sh`
- **Documentation**: `REAL_EXECUTION_GUIDE.md` with detailed setup instructions
- **Multi-Chain Support**: Ethereum and Base ready, extensible to any EVM chain
- **Enhanced Main Pipeline**: `main.py` updated with real execution support
- **Git Integration**: Added `.gitignore` for proper version control

### Changed
- **Updated README.md**: Complete rewrite with new features and safety warnings
- **Enhanced Strategy Runner**: `strategy_runner_real.py` with real execution support
- **Execution Architecture**: Separated paper and real execution layers

### Fixed
- **Import Paths**: Fixed module imports for proper package structure
- **Environment Handling**: Improved dotenv integration
- **Safety Defaults**: Paper trading remains default mode

### Security
- **Explicit Warnings**: Added critical safety warnings throughout documentation
- **Testnet Emphasis**: Strong recommendation to test on Sepolia first
- **Environment Security**: `.env` files excluded from git by default

## [1.0.0] - 2026-04-08

### Added
- **Initial Release**: Core 4-agent trading system
- **Basic Architecture**: Whisperer, Actuary, Slinger, Reaper agents
- **Paper Trading**: Mock execution layer for testing
- **Dashboard**: Web interface for monitoring
- **CLI Interface**: Command-line control system
- **Strategy Factory**: Configurable trading profiles

### Features
- Social signal scanning (mock)
- Risk assessment with GoPlus API integration
- Transaction calldata generation
- Position monitoring with stop-loss/take-profit
- Paper trading simulation
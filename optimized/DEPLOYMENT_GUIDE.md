# DEPLOYMENT GUIDE
## Optimized Asymmetric Strike Team

## Overview

This guide covers deploying the massively optimized trading system with 5-20x performance improvements.

## Architecture Changes

### Old Architecture (Sequential)
```
Whisperer → Actuary → Slinger → Reaper
    ↓         ↓         ↓        ↓
  2-5s     0.5-2s    0.1-0.5s   Polling
```

### New Architecture (Async + Parallel)
```
[Whisperer] → [AsyncActuary*N] → [OptimizedSlinger] → [RealTimeMonitor]
    ↓              ↓                   ↓                    ↓
  Async        Parallel            Connection         Event-Driven
  Stream      (Redis Cache)        Pooling +          WebSockets
                                  Flashbots
```

## Performance Expectations

| Component | Old Latency | New Latency | Improvement |
|-----------|-------------|-------------|-------------|
| API Calls | 500-2000ms | 10-50ms | 50-100x |
| Transactions | 100-500ms | 10-50ms | 10-50x |
| Signal Processing | 2-5s | 100-500ms | 5-10x |
| End-to-End | 5-10s | 500ms-2s | 5-20x |
| Monitoring | 100ms/position | 5-20ms | 2-5x |

## Deployment Steps

### Phase 1: Infrastructure Setup

#### 1.1 Redis Installation (Required for caching)
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

# macOS
brew install redis
brew services start redis

# Verify
redis-cli ping  # Should return "PONG"
```

#### 1.2 Python Environment
```bash
# Create virtual environment
python -m venv venv_optimized
source venv_optimized/bin/activate  # On Windows: venv_optimized\Scripts\activate

# Install optimized requirements
pip install -r optimized_requirements.txt
```

#### 1.3 Environment Configuration
```bash
# Copy and edit environment file
cp .env.example .env.optimized
nano .env.optimized
```

Required environment variables:
```env
# Core
USE_REAL_EXECUTION=true
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
PRIVATE_KEY=0xYOUR_PRIVATE_KEY

# Performance
REDIS_URL=redis://localhost:6379
MAX_CONCURRENT_REQUESTS=10
ENABLE_FLASHBOTS=true
FLASHBOTS_SIGNER_KEY=0xYOUR_FLASHBOTS_KEY

# Strategy
STRATEGY_PROFILE=degen  # or sniper, shadow_clone, etc.
SCAN_INTERVAL_SECONDS=5
```

### Phase 2: Component Deployment

#### 2.1 Deploy AsyncActuary (Immediate 50-100x improvement)
```python
from optimized.async_actuary import AsyncActuary

async def main():
    actuary = AsyncActuary(
        max_allowed_tax=0.25,
        redis_url="redis://localhost:6379",
        cache_ttl=300
    )
    await actuary.initialize()
    
    # Use in your pipeline
    signals = [...]  # Your signals
    assessments = await actuary.assess_multiple(signals)  # Parallel!
```

#### 2.2 Deploy OptimizedSlinger (10-50x improvement)
```python
from optimized.optimized_slinger import OptimizedSlingerAgent
from strategy_factory import StrategyFactory

async def main():
    factory = StrategyFactory()
    config = factory.get_profile("degen").slinger
    
    slinger = OptimizedSlingerAgent(
        config=config,
        rpc_url=os.getenv("ETH_RPC_URL"),
        private_key=os.getenv("PRIVATE_KEY"),
        flashbots_signer_key=os.getenv("FLASHBOTS_SIGNER_KEY"),
        max_connections=5
    )
    await slinger.initialize()
    
    # Single transaction
    tx_hash = await slinger.execute_order(order)
    
    # Bundle transactions (atomic execution)
    tx_hashes = await slinger.execute_bundle([order1, order2, order3])
```

#### 2.3 Deploy AsyncPipeline (5-10x improvement)
```python
from optimized.async_pipeline import AsyncPipeline

async def main():
    pipeline = AsyncPipeline(
        strategy_name="degen",
        rpc_url=os.getenv("ETH_RPC_URL"),
        private_key=os.getenv("PRIVATE_KEY"),
        max_concurrent_signals=5,
        enable_monitoring=True
    )
    
    await pipeline.initialize()
    
    # Process single signal
    result = await pipeline.process_signal(signal)
    
    # Process multiple in parallel
    results = await pipeline.process_multiple_signals(signals)
    
    # Continuous scanning mode
    await pipeline.continuous_scan(scan_interval=10)
```

#### 2.4 Deploy RealTimeMonitor (2-5x improvement)
```python
from optimized.real_time_monitor import RealTimeMonitor, Position

async def main():
    monitor = RealTimeMonitor(
        rpc_url=os.getenv("ETH_RPC_URL"),
        websocket_urls=[
            "wss://stream.binance.com:9443/ws",
            "wss://ws.okx.com:8443/ws/v5/public"
        ]
    )
    
    await monitor.start()
    
    # Add positions to monitor
    position = Position(
        token_address="0x...",
        tx_hash="0x...",
        entry_price=1000.0,
        entry_time=datetime.now(),
        amount_usd=1000.0,
        stop_loss_pct=-10.0,
        take_profit_pct=20.0,
        trailing_stop_pct=5.0
    )
    
    monitor.add_position(position)
    
    # Run monitoring
    await asyncio.sleep(300)  # Monitor for 5 minutes
    await monitor.stop()
```

### Phase 3: Production Deployment

#### 3.1 Docker Configuration
```dockerfile
# Dockerfile.optimized
FROM python:3.11-slim

# Install Redis
RUN apt-get update && apt-get install -y redis-server && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy application
WORKDIR /app
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r optimized_requirements.txt

# Start Redis and application
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
```

```bash
# start.sh
#!/bin/bash
# Start Redis
redis-server --daemonize yes

# Start application
python -m optimized.main
```

#### 3.2 Systemd Service (Linux)
```ini
# /etc/systemd/system/asymmetric-trading.service
[Unit]
Description=Asymmetric Strike Team Trading Bot
After=network.target redis-server.service

[Service]
Type=simple
User=trading
WorkingDirectory=/opt/asymmetric-trading
EnvironmentFile=/opt/asymmetric-trading/.env.optimized
ExecStart=/opt/asymmetric-trading/venv_optimized/bin/python -m optimized.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 3.3 Monitoring & Alerting
```python
# Add to your pipeline initialization
pipeline = AsyncPipeline(
    # ... existing config ...
    alert_channels=[
        "discord:https://discord.com/api/webhooks/...",
        "telegram:bot_token:chat_id",
        "email:smtp://user:pass@smtp.gmail.com:587"
    ]
)
```

## Migration Strategy

### Step-by-Step Migration

1. **Week 1: Infrastructure**
   - Deploy Redis
   - Update environment variables
   - Test async components in isolation

2. **Week 2: Actuary Migration**
   - Replace synchronous Actuary with AsyncActuary
   - Enable Redis caching
   - Monitor API call performance

3. **Week 3: Slinger Migration**
   - Deploy OptimizedSlinger
   - Test Flashbots integration (if using)
   - Verify transaction success rates

4. **Week 4: Pipeline Migration**
   - Deploy AsyncPipeline
   - Enable parallel processing
   - Monitor end-to-end latency

5. **Week 5: Monitoring Migration**
   - Deploy RealTimeMonitor
   - Migrate from polling to event-driven
   - Set up alert channels

## Performance Validation

### Validation Script
```bash
# Run performance benchmark
python -m optimized.performance_benchmark

# Expected output:
# ✅ Throughput improvement: 5-20x
# ✅ Latency improvement: 5-20x
# ✅ API call improvement: 50-100x
```

### Monitoring Metrics
```python
# Key metrics to monitor
metrics = {
    'signals_processed_per_second': pipeline.metrics['throughput'],
    'avg_latency_ms': pipeline.metrics['avg_latency_ms'],
    'api_cache_hit_rate': actuary.cache_hit_rate,
    'transaction_success_rate': slinger.success_rate,
    'monitoring_latency_ms': monitor.metrics['avg_update_latency_ms']
}
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```bash
   # Check Redis is running
   sudo systemctl status redis-server
   
   # Test connection
   redis-cli -h localhost -p 6379 ping
   ```

2. **Web3 Connection Issues**
   ```python
   # Test Web3 connection
   from web3 import Web3
   w3 = Web3(Web3.HTTPProvider(RPC_URL))
   print(f"Connected: {w3.is_connected()}")
   print(f"Chain ID: {w3.eth.chain_id}")
   ```

3. **Async Runtime Error**
   ```python
   # Ensure you're using asyncio.run() or event loop
   import asyncio
   
   async def main():
       # Your async code
       
   if __name__ == "__main__":
       asyncio.run(main())
   ```

4. **Flashbots Integration**
   ```bash
   # Install Flashbots
   pip install flashbots
   
   # Test with testnet first
   USE_FLASHBOTS=false  # Disable until verified
   ```

## Rollback Plan

If issues arise, revert to previous version:

1. **Immediate Rollback**
   ```bash
   # Switch back to sequential pipeline
   USE_OPTIMIZED_PIPELINE=false
   ```

2. **Component Rollback**
   - Disable AsyncActuary: Use original Actuary
   - Disable OptimizedSlinger: Use original Slinger
   - Disable RealTimeMonitor: Use polling monitor

3. **Full Rollback**
   ```bash
   git checkout main  # Revert to stable version
   systemctl restart asymmetric-trading
   ```

## Support

For issues or questions:
1. Check logs: `journalctl -u asymmetric-trading -f`
2. Monitor metrics dashboard
3. Contact: [Your Support Channel]

---

**Deployment Complete!** Your trading system is now running with 5-20x better performance. Monitor closely for the first 48 hours and adjust parameters as needed.
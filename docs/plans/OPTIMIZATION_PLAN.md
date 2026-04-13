# Optimization Plan - Making Python Faster

## Phase 1: Async Conversion (Week 1)

### 1.1 Replace `urllib`/`requests` with `aiohttp`

**File:** `agents/whisperer.py`
```python
# BEFORE (blocking):
import urllib.request
import json

def _get(url: str, timeout: int = 8) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AsymmetricStrikeTeam/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning(f"GET {url} failed: {e}")
        return None

# AFTER (async):
import aiohttp
import asyncio

async def _aget(session: aiohttp.ClientSession, url: str, timeout: int = 8) -> Optional[dict]:
    try:
        async with session.get(url, timeout=timeout) as response:
            return await response.json()
    except Exception as e:
        logger.warning(f"GET {url} failed: {e}")
        return None
```

### 1.2 Make Whisperer async

```python
# BEFORE:
def scan_firehose() -> Optional[TradeSignal]:
    # Sequential API calls
    profiles = _get(f"{DEXSCREENER_BASE}/token-profiles/latest")
    boosts = _get(f"{DEXSCREENER_BASE}/token-boosts/top")
    # ... more sequential calls
    
# AFTER:
async def scan_firehose_async() -> Optional[TradeSignal]:
    async with aiohttp.ClientSession() as session:
        # Concurrent API calls
        profiles_task = _aget(session, f"{DEXSCREENER_BASE}/token-profiles/latest")
        boosts_task = _aget(session, f"{DEXSCREENER_BASE}/token-boosts/top")
        trending_task = _aget(session, f"{DEXSCREENER_BASE}/search?q=trending")
        
        # Wait for all concurrently
        profiles, boosts, trending = await asyncio.gather(
            profiles_task, boosts_task, trending_task,
            return_exceptions=True
        )
```

### 1.3 Update Actuary for async GoPlus calls

**File:** `agents/actuary.py`
```python
# BEFORE:
def assess_risk(self, signal: TradeSignal) -> RiskAssessment:
    # Blocking HTTP calls
    token_security = self._call_goplus(signal.token_address, signal.chain)
    
# AFTER:
async def assess_risk_async(self, signal: TradeSignal) -> RiskAssessment:
    # Async HTTP calls
    async with aiohttp.ClientSession() as session:
        token_security = await self._acall_goplus(session, signal.token_address, signal.chain)
```

## Phase 2: Connection Pooling (Week 1)

### 2.1 Create shared session manager

**File:** `core/http_client.py`
```python
import aiohttp
from typing import Optional

class HTTPClient:
    _instance: Optional['HTTPClient'] = None
    _session: Optional[aiohttp.ClientSession] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,  # Total connections
                limit_per_host=30,  # Connections per host
                ttl_dns_cache=300,  # DNS cache TTL
            )
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={"User-Agent": "AsymmetricStrikeTeam/2.0"}
            )
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
```

### 2.2 Update all agents to use shared client

```python
from core.http_client import HTTPClient

class Whisperer:
    def __init__(self):
        self.http_client = HTTPClient()
    
    async def scan_firehose_async(self):
        session = await self.http_client.get_session()
        # Use shared session for all calls
```

## Phase 3: Async Main Pipeline (Week 2)

### 3.1 Create async pipeline runner

**File:** `main_async.py`
```python
import asyncio
import time

async def run_async_cycle(strategy: str = "degen", paper_mode: bool = True):
    """Run entire pipeline asynchronously."""
    
    # Initialize all agents
    whisperer = Whisperer()
    actuary = Actuary()
    slinger = UnifiedSlinger()
    
    # Step 1: Async signal scanning
    print("🔍 Scanning for signals...")
    signal = await whisperer.scan_firehose_async()
    if not signal:
        return False
    
    # Step 2: Async risk assessment
    print("🛡️  Assessing risk...")
    assessment = await actuary.assess_risk_async(signal)
    
    # Step 3: Execute (Web3.py is still blocking, but we can run in thread)
    print("⚡ Executing trade...")
    loop = asyncio.get_event_loop()
    order = await loop.run_in_executor(
        None,  # Use default ThreadPoolExecutor
        slinger.execute_order,
        assessment,
        signal.chain
    )
    
    return order is not None

async def main_async():
    """Main async entry point."""
    start_time = time.time()
    
    # Run multiple cycles concurrently if needed
    tasks = []
    for _ in range(3):  # Run 3 parallel scans
        task = run_async_cycle("degen", True)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    print(f"⏱️  Completed {len(tasks)} cycles in {elapsed:.2f}s")
```

### 3.2 Add Web3.py async wrapper

**File:** `core/web3_async.py`
```python
import asyncio
from web3 import Web3
from web3.middleware import geth_poa_middleware
from concurrent.futures import ThreadPoolExecutor

class AsyncWeb3:
    def __init__(self, rpc_url: str, max_workers: int = 4):
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.loop = asyncio.get_event_loop()
    
    async def get_balance(self, address: str):
        """Async wrapper for web3.eth.get_balance."""
        return await self.loop.run_in_executor(
            self.executor,
            self.web3.eth.get_balance,
            address
        )
    
    async def estimate_gas(self, transaction):
        """Async wrapper for gas estimation."""
        return await self.loop.run_in_executor(
            self.executor,
            self.web3.eth.estimate_gas,
            transaction
        )
    
    async def send_transaction(self, signed_txn):
        """Async wrapper for sending transactions."""
        return await self.loop.run_in_executor(
            self.executor,
            self.web3.eth.send_raw_transaction,
            signed_txn.rawTransaction
        )
```

## Phase 4: Caching Layer (Week 2)

### 4.1 Add Redis/In-memory cache

**File:** `core/cache.py`
```python
import asyncio
import pickle
from typing import Any, Optional
import aioredis  # or use built-in lru_cache for simplicity

class Cache:
    def __init__(self, ttl: int = 300):  # 5 minutes default
        self.ttl = ttl
        self._cache = {}
        self._locks = {}
    
    async def get(self, key: str) -> Optional[Any]:
        """Get from cache with async support."""
        if key in self._cache:
            data, expiry = self._cache[key]
            if time.time() < expiry:
                return data
            else:
                del self._cache[key]
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set cache value with TTL."""
        expiry = time.time() + (ttl or self.ttl)
        self._cache[key] = (value, expiry)
    
    async def get_or_set(self, key: str, coro, ttl: Optional[int] = None):
        """Get from cache or execute coroutine and cache result."""
        cached = await self.get(key)
        if cached is not None:
            return cached
        
        # Use lock to prevent duplicate coroutine execution
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        
        async with self._locks[key]:
            # Check cache again in case another task set it
            cached = await self.get(key)
            if cached is not None:
                return cached
            
            # Execute coroutine and cache result
            result = await coro
            await self.set(key, result, ttl)
            return result
```

### 4.2 Update agents to use cache

```python
from core.cache import Cache

class Whisperer:
    def __init__(self):
        self.cache = Cache(ttl=60)  # 1 minute cache for API calls
    
    async def scan_firehose_async(self):
        # Cache DexScreener calls
        profiles = await self.cache.get_or_set(
            "dexscreener:profiles",
            lambda: self._fetch_profiles_async(),
            ttl=30  # 30 seconds
        )
```

## Phase 5: Performance Monitoring (Week 3)

### 5.1 Add metrics collection

**File:** `core/metrics.py`
```python
import time
from typing import Dict, List
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class Timing:
    operation: str
    duration: float
    timestamp: float

class MetricsCollector:
    def __init__(self):
        self.timings: List[Timing] = []
        self.counts = defaultdict(int)
        self.errors = defaultdict(int)
    
    def record_timing(self, operation: str, duration: float):
        self.timings.append(Timing(operation, duration, time.time()))
        # Keep only last 1000 timings
        if len(self.timings) > 1000:
            self.timings = self.timings[-1000:]
    
    def increment(self, metric: str):
        self.counts[metric] += 1
    
    def record_error(self, error_type: str):
        self.errors[error_type] += 1
    
    def get_summary(self) -> Dict:
        # Calculate percentiles, averages, etc.
        return {
            "total_operations": len(self.timings),
            "avg_duration": sum(t.duration for t in self.timings) / len(self.timings) if self.timings else 0,
            "counts": dict(self.counts),
            "errors": dict(self.errors),
        }
```

### 5.2 Add decorators for automatic timing

```python
import functools
from core.metrics import metrics

def timed(operation_name: str):
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start
                metrics.record_timing(operation_name, duration)
                metrics.increment(f"{operation_name}_success")
                return result
            except Exception as e:
                duration = time.time() - start
                metrics.record_timing(operation_name, duration)
                metrics.increment(f"{operation_name}_error")
                metrics.record_error(type(e).__name__)
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start
                metrics.record_timing(operation_name, duration)
                metrics.increment(f"{operation_name}_success")
                return result
            except Exception as e:
                duration = time.time() - start
                metrics.record_timing(operation_name, duration)
                metrics.increment(f"{operation_name}_error")
                metrics.record_error(type(e).__name__)
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

# Usage:
@timed("whisperer_scan")
async def scan_firehose_async(self):
    # ... implementation
```

## Implementation Schedule

### Week 1: Foundation
- **Day 1-2:** Install dependencies (`aiohttp`, `aioredis`, etc.)
- **Day 3-4:** Convert Whisperer to async
- **Day 5:** Convert Actuary to async
- **Day 6-7:** Create shared HTTP client and connection pooling

### Week 2: Core Pipeline
- **Day 8-9:** Create async main pipeline (`main_async.py`)
- **Day 10-11:** Implement caching layer
- **Day 12:** Add Web3.py async wrapper
- **Day 13-14:** Test and benchmark improvements

### Week 3: Monitoring & Optimization
- **Day 15-16:** Add metrics collection
- **Day 17-18:** Profile and identify remaining bottlenecks
- **Day 19-20:** Implement additional optimizations
- **Day 21:** Final benchmarking and documentation

## Expected Performance Gains

| Component | Before | After Async | After All Optimizations |
|-----------|--------|-------------|-------------------------|
| Whisperer API calls | 5-8s (sequential) | 1-2s (concurrent) | 0.5-1s (cached) |
| Actuary checks | 2-4s | 0.5-1s | 0.2-0.5s |
| Web3 operations | 3-10s | 3-10s (still blocking) | 1-3s (threadpool) |
| **Total cycle time** | **10-22s** | **5-13s** | **2-5s** |

## Migration Strategy

### Step 1: Create parallel async implementation
- Keep existing `main.py` working
- Create new `main_async.py` with optimizations
- Run both and compare results

### Step 2: Gradual migration
- Start with non-critical components (Whisperer)
- Move to critical path once stable
- Keep fallback to sync version

### Step 3: Full migration
- Once async version is stable and faster
- Update all entry points to use async
- Remove old sync code

## Quick Wins (Do Today)

1. **Add connection reuse to current code:**
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=3, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry, pool_connections=100, pool_maxsize=100)
session.mount('http://', adapter)
session.mount('https://', adapter)
```

2. **Add simple caching:**
```python
from functools import lru_cache
import time

@lru_cache(maxsize=128)
def get_with_cache(url: str, ttl: int = 30):
    # Simple time-based cache
    return requests.get(url).json()
```

3. **Run profiler to find hotspots:**
```bash
python -m cProfile -s time main.py --strategy degen > profile.txt
head -50 profile.txt
```

This plan will give you **2-5x performance improvement** with **minimal risk** and **backward compatibility**.
#!/usr/bin/env python3
"""
PHANTOM MCP Agent - Execution Agent with MCP Integration

This agent follows the MCP integration pattern from the handover:
- Receives signals from sentiment pipeline
- Calls CCXT MCP for market data
- Calculates position sizing based on risk params
- Executes trades via CCXT MCP
- Logs execution to database

Phase 1: Foundation - CCXT MCP integration
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PhantomMCPAgent:
    """Execution agent that integrates with MCP servers for trading."""
    
    def __init__(self, config_path: str = None):
        """Initialize the PHANTOM agent with MCP configuration."""
        self.agent_name = "PHANTOM"
        self.version = "1.0.0"
        self.mcp_config = self._load_mcp_config(config_path)
        self.exchange_connections = {}
        self.risk_params = {
            'max_position_size_pct': 0.01,  # 1% of portfolio per trade
            'max_daily_loss_pct': 0.02,     # 2% max daily loss
            'stop_loss_pct': 0.30,          # 30% stop loss (Reaper rule)
            'take_profit_pct': 1.00,        # 100% take profit (Reaper rule)
            'min_confidence_score': 0.70,   # Minimum signal confidence
        }
        
        logger.info(f"Initialized {self.agent_name} v{self.version}")
        logger.info(f"Risk params: {self.risk_params}")
    
    def _load_mcp_config(self, config_path: str = None) -> Dict:
        """Load MCP configuration from file."""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                '..', 'mcp_config.json'
            )
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded MCP config from {config_path}")
            return config
        except FileNotFoundError:
            logger.warning(f"MCP config not found at {config_path}, using defaults")
            return {
                'mcpServers': {
                    'ccxt': {
                        'command': 'npx',
                        'args': ['-y', '@lazydino/ccxt-mcp']
                    }
                }
            }
    
    def _call_mcp_server(self, server_name: str, tool: str, params: Dict) -> Dict:
        """
        Call an MCP server tool.
        
        In a real implementation, this would use the MCP protocol.
        For now, we'll simulate the structure.
        """
        logger.info(f"Calling MCP server: {server_name}.{tool}")
        logger.debug(f"Params: {params}")
        
        # Simulate MCP call structure
        # In production, this would use actual MCP client library
        mcp_call = {
            'server': server_name,
            'tool': tool,
            'params': params,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # For CCXT MCP simulation
        if server_name == 'ccxt' and tool == 'fetch_ticker':
            return self._simulate_ccxt_fetch_ticker(params)
        elif server_name == 'ccxt' and tool == 'create_order':
            return self._simulate_ccxt_create_order(params)
        elif server_name == 'coingecko' and tool == 'get_trending':
            return self._simulate_coingecko_get_trending(params)
        
        return {
            'success': False,
            'error': f"Tool {tool} not implemented for {server_name}",
            'mcp_call': mcp_call
        }
    
    def _simulate_ccxt_fetch_ticker(self, params: Dict) -> Dict:
        """Simulate CCXT fetch_ticker response."""
        symbol = params.get('symbol', 'BTC/USDT')
        
        # Simulate market data
        import random
        base_price = 65000 + random.uniform(-1000, 1000)
        
        return {
            'success': True,
            'data': {
                'symbol': symbol,
                'timestamp': datetime.utcnow().isoformat(),
                'datetime': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                'high': base_price * 1.01,
                'low': base_price * 0.99,
                'bid': base_price * 0.999,
                'ask': base_price * 1.001,
                'vwap': base_price,
                'open': base_price * 0.995,
                'close': base_price,
                'last': base_price,
                'previousClose': base_price * 0.995,
                'change': base_price * 0.005,
                'percentage': 0.5,
                'average': base_price,
                'baseVolume': random.uniform(1000, 5000),
                'quoteVolume': random.uniform(50000000, 100000000),
                'info': {
                    'symbol': symbol,
                    'priceChange': '325.00',
                    'priceChangePercent': '0.50',
                    'weightedAvgPrice': str(base_price),
                    'prevClosePrice': str(base_price * 0.995),
                    'lastPrice': str(base_price),
                    'lastQty': '0.001',
                    'bidPrice': str(base_price * 0.999),
                    'bidQty': '10.5',
                    'askPrice': str(base_price * 1.001),
                    'askQty': '12.3',
                    'openPrice': str(base_price * 0.995),
                    'highPrice': str(base_price * 1.01),
                    'lowPrice': str(base_price * 0.99),
                    'volume': str(random.uniform(1000, 5000)),
                    'quoteVolume': str(random.uniform(50000000, 100000000)),
                    'openTime': int(time.time() * 1000) - 86400000,
                    'closeTime': int(time.time() * 1000),
                    'firstId': 100000000,
                    'lastId': 100000500,
                    'count': 500
                }
            }
        }
    
    def _simulate_ccxt_create_order(self, params: Dict) -> Dict:
        """Simulate CCXT create_order response."""
        symbol = params.get('symbol', 'BTC/USDT')
        order_type = params.get('type', 'limit')
        side = params.get('side', 'buy')
        amount = params.get('amount', 0.001)
        price = params.get('price', 65000)
        
        order_id = f"TEST_{int(time.time())}_{side.upper()}_{symbol.replace('/', '_')}"
        
        return {
            'success': True,
            'data': {
                'id': order_id,
                'timestamp': datetime.utcnow().isoformat(),
                'datetime': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                'lastTradeTimestamp': None,
                'symbol': symbol,
                'type': order_type,
                'side': side,
                'price': price,
                'amount': amount,
                'cost': price * amount,
                'average': None,
                'filled': 0.0,
                'remaining': amount,
                'status': 'open',
                'fee': None,
                'trades': None,
                'fees': [],
                'info': {
                    'orderId': order_id,
                    'symbol': symbol,
                    'status': 'NEW',
                    'clientOrderId': f"phantom_{int(time.time())}",
                    'price': str(price),
                    'origQty': str(amount),
                    'executedQty': '0',
                    'cummulativeQuoteQty': '0',
                    'type': order_type.upper(),
                    'side': side.upper(),
                    'stopPrice': '0',
                    'icebergQty': '0',
                    'time': int(time.time() * 1000),
                    'updateTime': int(time.time() * 1000),
                    'isWorking': True,
                    'origQuoteOrderQty': '0'
                }
            }
        }
    
    def _simulate_coingecko_get_trending(self, params: Dict) -> Dict:
        """Simulate CoinGecko trending coins response."""
        return {
            'success': True,
            'data': {
                'coins': [
                    {
                        'item': {
                            'id': 'bitcoin',
                            'coin_id': 1,
                            'name': 'Bitcoin',
                            'symbol': 'btc',
                            'market_cap_rank': 1,
                            'thumb': 'https://assets.coingecko.com/coins/images/1/thumb/bitcoin.png',
                            'small': 'https://assets.coingecko.com/coins/images/1/small/bitcoin.png',
                            'large': 'https://assets.coingecko.com/coins/images/1/large/bitcoin.png',
                            'slug': 'bitcoin',
                            'price_btc': 1.0,
                            'score': 0
                        }
                    },
                    {
                        'item': {
                            'id': 'ethereum',
                            'coin_id': 2,
                            'name': 'Ethereum',
                            'symbol': 'eth',
                            'market_cap_rank': 2,
                            'thumb': 'https://assets.coingecko.com/coins/images/279/thumb/ethereum.png',
                            'small': 'https://assets.coingecko.com/coins/images/279/small/ethereum.png',
                            'large': 'https://assets.coingecko.com/coins/images/279/large/ethereum.png',
                            'slug': 'ethereum',
                            'price_btc': 0.05,
                            'score': 1
                        }
                    }
                ],
                'exchanges': [],
                'nfts': [],
                'categories': []
            }
        }
    
    def receive_signal(self, signal: Dict) -> bool:
        """
        Receive a trading signal from the sentiment pipeline.
        
        Expected signal structure:
        {
            'symbol': 'BTC/USDT',
            'direction': 'buy' or 'sell',
            'confidence': 0.0-1.0,
            'signal_type': 'sentiment' or 'technical' or 'funding_rate',
            'timestamp': '2024-04-12T...',
            'metadata': {...}
        }
        """
        logger.info(f"Received signal: {signal.get('symbol')} {signal.get('direction')} "
                   f"(confidence: {signal.get('confidence', 0):.2f})")
        
        # Validate signal
        if not self._validate_signal(signal):
            logger.warning(f"Signal validation failed: {signal}")
            return False
        
        # Check confidence threshold
        if signal.get('confidence', 0) < self.risk_params['min_confidence_score']:
            logger.warning(f"Signal confidence too low: {signal.get('confidence', 0):.2f} "
                          f"< {self.risk_params['min_confidence_score']}")
            return False
        
        # Execute trade
        return self._execute_trade(signal)
    
    def _validate_signal(self, signal: Dict) -> bool:
        """Validate trading signal structure and content."""
        required_fields = ['symbol', 'direction', 'confidence']
        
        for field in required_fields:
            if field not in signal:
                logger.error(f"Missing required field: {field}")
                return False
        
        if signal['direction'] not in ['buy', 'sell']:
            logger.error(f"Invalid direction: {signal['direction']}")
            return False
        
        if not 0 <= signal['confidence'] <= 1:
            logger.error(f"Invalid confidence: {signal['confidence']}")
            return False
        
        return True
    
    def _execute_trade(self, signal: Dict) -> bool:
        """Execute a trade based on the signal."""
        symbol = signal['symbol']
        direction = signal['direction']
        confidence = signal['confidence']
        
        logger.info(f"Executing trade: {direction.upper()} {symbol} "
                   f"(confidence: {confidence:.2f})")
        
        try:
            # Step 1: Get current market data via CCXT MCP
            market_data = self._call_mcp_server(
                'ccxt', 'fetch_ticker', {'symbol': symbol}
            )
            
            if not market_data.get('success'):
                logger.error(f"Failed to fetch market data: {market_data.get('error')}")
                return False
            
            # Step 2: Calculate position size based on risk params
            position_size = self._calculate_position_size(signal, market_data['data'])
            
            # Step 3: Create order via CCXT MCP
            order_params = {
                'symbol': symbol,
                'type': 'limit',
                'side': direction,
                'amount': position_size,
                'price': market_data['data']['ask'] if direction == 'buy' else market_data['data']['bid']
            }
            
            order_result = self._call_mcp_server(
                'ccxt', 'create_order', order_params
            )
            
            if not order_result.get('success'):
                logger.error(f"Failed to create order: {order_result.get('error')}")
                return False
            
            # Step 4: Log execution
            self._log_execution(signal, market_data['data'], order_result['data'])
            
            logger.info(f"Trade executed successfully: {order_result['data']['id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}", exc_info=True)
            return False
    
    def _calculate_position_size(self, signal: Dict, market_data: Dict) -> float:
        """Calculate position size based on risk parameters."""
        # For simulation, use a fixed small size
        # In production, this would consider portfolio value, risk limits, etc.
        base_size = 0.001  # 0.001 BTC equivalent
        
        # Adjust based on confidence
        confidence = signal.get('confidence', 0.5)
        size_multiplier = 0.5 + confidence  # 0.5-1.5x based on confidence
        
        return base_size * size_multiplier
    
    def _log_execution(self, signal: Dict, market_data: Dict, order_data: Dict):
        """Log trade execution to database or file."""
        log_entry = {
            'agent': self.agent_name,
            'timestamp': datetime.utcnow().isoformat(),
            'signal': signal,
            'market_data': {
                'symbol': market_data.get('symbol'),
                'price': market_data.get('last'),
                'bid': market_data.get('bid'),
                'ask': market_data.get('ask')
            },
            'order': {
                'id': order_data.get('id'),
                'symbol': order_data.get('symbol'),
                'side': order_data.get('side'),
                'type': order_data.get('type'),
                'price': order_data.get('price'),
                'amount': order_data.get('amount'),
                'status': order_data.get('status')
            },
            'risk_params': self.risk_params
        }
        
        # Save to file (in production, this would go to a database)
        log_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'data', 'phantom_executions.json'
        )
        
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        try:
            # Read existing logs
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            # Add new log
            logs.append(log_entry)
            
            # Write back
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
            
            logger.debug(f"Logged execution to {log_file}")
            
        except Exception as e:
            logger.error(f"Failed to log execution: {e}")
    
    def scan_market(self) -> List[Dict]:
        """Scan market for opportunities using CoinGecko MCP."""
        logger.info("Scanning market for opportunities...")
        
        try:
            # Get trending coins from CoinGecko
            trending_result = self._call_mcp_server(
                'coingecko', 'get_trending', {}
            )
            
            if not trending_result.get('success'):
                logger.warning(f"Failed to get trending coins: {trending_result.get('error')}")
                return []
            
            opportunities = []
            for coin in trending_result['data'].get('coins', [])[:5]:  # Top 5
                coin_data = coin.get('item', {})
                opportunity = {
                    'symbol': f"{coin_data.get('symbol', '').upper()}/USDT",
                    'name': coin_data.get('name', ''),
                    'market_cap_rank': coin_data.get('market_cap_rank', 999),
                    'reason': 'trending_on_coingecko',
                    'confidence': 0.6,  # Base confidence for trending coins
                    'timestamp': datetime.utcnow().isoformat()
                }
                opportunities.append(opportunity)
            
            logger.info(f"Found {len(opportunities)} market opportunities")
            return opportunities
            
        except Exception as e:
            logger.error(f"Error scanning market: {e}", exc_info=True)
            return []
    
    def run(self, mode: str = 'signal'):
        """Run the agent in different modes."""
        logger.info(f"Starting {self.agent_name} in {mode} mode")
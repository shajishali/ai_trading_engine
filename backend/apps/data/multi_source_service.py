"""
Multi-Source Data Service
Supports multiple cryptocurrency data providers with fallback mechanism
"""
import requests
import logging
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from django.utils import timezone
from django.db import transaction

from apps.trading.models import Symbol
from apps.data.models import MarketData, DataSource
try:
    from apps.data.tradingview_service import TradingViewService
except ImportError:
    TradingViewService = None

logger = logging.getLogger(__name__)


class CoinMarketCapService:
    """CoinMarketCap API integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://pro-api.coinmarketcap.com/v1"
        self.headers = {
            'X-CMC_PRO_API_KEY': api_key or '',
            'Accept': 'application/json'
        }
    
    def get_historical_data(self, symbol: Symbol, days: int = 30) -> Optional[List[Dict]]:
        """Get historical OHLCV data from CoinMarketCap"""
        if not self.api_key:
            logger.warning("CoinMarketCap API key not provided")
            return None
        
        try:
            # CoinMarketCap uses symbol IDs, need to map first
            # For now, return None - would need API key and proper mapping
            logger.info(f"CoinMarketCap historical data not yet implemented for {symbol.symbol}")
            return None
        except Exception as e:
            logger.error(f"Error fetching CoinMarketCap data for {symbol.symbol}: {e}")
            return None


class CryptoCompareService:
    """CryptoCompare API integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://min-api.cryptocompare.com/data"
        self.headers = {'authorization': f'Apikey {api_key}'} if api_key else {}
    
    def get_historical_data(self, symbol: Symbol, days: int = 30) -> Optional[List[Dict]]:
        """Get historical OHLCV data from CryptoCompare"""
        try:
            # Map symbol to CryptoCompare format
            symbol_name = symbol.symbol.upper()
            
            # CryptoCompare uses different symbol names sometimes
            symbol_mapping = {
                'BTC': 'BTC',
                'ETH': 'ETH',
                # Add more mappings as needed
            }
            
            crypto_symbol = symbol_mapping.get(symbol_name, symbol_name)
            
            # Calculate timestamp
            to_time = int(time.time())
            limit = min(days * 24, 2000)  # Max 2000 data points
            
            url = f"{self.base_url}/v2/histohour"
            params = {
                'fsym': crypto_symbol,
                'tsym': 'USDT',
                'limit': limit,
                'toTs': to_time
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('Response') == 'Error':
                logger.warning(f"CryptoCompare error: {data.get('Message')}")
                return None
            
            # Parse response
            records = []
            if 'Data' in data and 'Data' in data['Data']:
                for item in data['Data']['Data']:
                    timestamp = datetime.fromtimestamp(item['time'], tz=dt_timezone.utc)
                    records.append({
                        'timestamp': timestamp,
                        'open': Decimal(str(item['open'])),
                        'high': Decimal(str(item['high'])),
                        'low': Decimal(str(item['low'])),
                        'close': Decimal(str(item['close'])),
                        'volume': Decimal(str(item['volumefrom']))
                    })
            
            logger.info(f"Fetched {len(records)} records from CryptoCompare for {symbol.symbol}")
            return records
            
        except Exception as e:
            logger.error(f"Error fetching CryptoCompare data for {symbol.symbol}: {e}")
            return None


class OKXService:
    """OKX (formerly OKEx) API integration"""
    
    def __init__(self):
        self.base_url = "https://www.okx.com/api/v5"
    
    def get_historical_data(self, symbol: Symbol, days: int = 30) -> Optional[List[Dict]]:
        """Get historical OHLCV data from OKX"""
        try:
            symbol_name = symbol.symbol.upper()
            trading_pair = f"{symbol_name}-USDT-SWAP"  # OKX uses different format
            
            # Calculate timestamps
            end_time = datetime.now(dt_timezone.utc)
            start_time = end_time - timedelta(days=days)
            
            url = f"{self.base_url}/market/candles"
            params = {
                'instId': trading_pair,
                'bar': '1H',  # 1 hour candles
                'after': str(int(start_time.timestamp() * 1000)),
                'before': str(int(end_time.timestamp() * 1000)),
                'limit': 300  # Max per request
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != '0':
                logger.warning(f"OKX error: {data.get('msg')}")
                return None
            
            # Parse response
            records = []
            for item in data.get('data', []):
                timestamp = datetime.fromtimestamp(int(item[0]) / 1000, tz=dt_timezone.utc)
                records.append({
                    'timestamp': timestamp,
                    'open': Decimal(str(item[1])),
                    'high': Decimal(str(item[2])),
                    'low': Decimal(str(item[3])),
                    'close': Decimal(str(item[4])),
                    'volume': Decimal(str(item[5]))
                })
            
            logger.info(f"Fetched {len(records)} records from OKX for {symbol.symbol}")
            return records
            
        except Exception as e:
            logger.error(f"Error fetching OKX data for {symbol.symbol}: {e}")
            return None


class BybitService:
    """Bybit API integration"""
    
    def __init__(self):
        self.base_url = "https://api.bybit.com/v5/market/kline"
    
    def get_historical_data(self, symbol: Symbol, days: int = 30) -> Optional[List[Dict]]:
        """Get historical OHLCV data from Bybit"""
        try:
            symbol_name = symbol.symbol.upper()
            trading_pair = f"{symbol_name}USDT"  # Bybit format
            
            # Calculate timestamps
            end_time = datetime.now(dt_timezone.utc)
            start_time = end_time - timedelta(days=days)
            
            url = self.base_url
            params = {
                'category': 'linear',  # USDT perpetual
                'symbol': trading_pair,
                'interval': '60',  # 1 hour
                'start': str(int(start_time.timestamp() * 1000)),
                'end': str(int(end_time.timestamp() * 1000)),
                'limit': 200  # Max per request
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('retCode') != 0:
                logger.warning(f"Bybit error: {data.get('retMsg')}")
                return None
            
            # Parse response
            records = []
            for item in data.get('result', {}).get('list', []):
                timestamp = datetime.fromtimestamp(int(item[0]) / 1000, tz=dt_timezone.utc)
                records.append({
                    'timestamp': timestamp,
                    'open': Decimal(str(item[1])),
                    'high': Decimal(str(item[2])),
                    'low': Decimal(str(item[3])),
                    'close': Decimal(str(item[4])),
                    'volume': Decimal(str(item[5]))
                })
            
            logger.info(f"Fetched {len(records)} records from Bybit for {symbol.symbol}")
            return records
            
        except Exception as e:
            logger.error(f"Error fetching Bybit data for {symbol.symbol}: {e}")
            return None


class MultiSourceDataService:
    """Service that aggregates data from multiple sources with fallback"""
    
    def __init__(self, source_priority: Optional[List[str]] = None):
        """
        Initialize with source priority list
        
        Args:
            source_priority: List of source names in priority order
                           Options: 'binance', 'coingecko', 'cryptocompare', 'okx', 'bybit'
        """
        self.source_priority = source_priority or [
            'binance',
            'tradingview',
            'cryptocompare',
            'okx',
            'bybit',
            'coingecko'
        ]
        
        # Initialize services
        self.services = {
            'cryptocompare': CryptoCompareService(),
            'okx': OKXService(),
            'bybit': BybitService(),
        }
        
        # TradingView requires special handling (CSV import, not direct API)
        if TradingViewService:
            self.services['tradingview'] = TradingViewService()
        
        # Get or create data sources
        self.data_sources = {}
        for source_name in self.source_priority:
            source, _ = DataSource.objects.get_or_create(
                name=source_name.title(),
                defaults={
                    'source_type': 'API',
                    'is_active': True
                }
            )
            self.data_sources[source_name] = source
    
    def fetch_historical_data(
        self,
        symbol: Symbol,
        timeframe: str = '1h',
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        days: int = 30
    ) -> Tuple[Optional[List[Dict]], str]:
        """
        Fetch historical data from multiple sources with fallback
        
        Returns:
            Tuple of (records, source_name) or (None, '') if all sources fail
        """
        if start is None:
            start = timezone.now() - timedelta(days=days)
        if end is None:
            end = timezone.now()
        
        # Try each source in priority order
        for source_name in self.source_priority:
            try:
                logger.info(f"Trying {source_name} for {symbol.symbol}...")
                
                if source_name == 'binance':
                    # Use existing Binance service
                    from apps.data.historical_data_manager import HistoricalDataManager
                    manager = HistoricalDataManager()
                    # This returns bool, need to get data differently
                    # For now, skip and use other sources
                    continue
                
                elif source_name == 'coingecko':
                    # Use existing CoinGecko service
                    from apps.data.services import CryptoDataIngestionService
                    service = CryptoDataIngestionService()
                    # This has different interface, handle separately
                    continue
                
                elif source_name in self.services:
                    service = self.services[source_name]
                    records = service.get_historical_data(symbol, days=days)
                    
                    if records and len(records) > 0:
                        logger.info(f"Successfully fetched {len(records)} records from {source_name}")
                        return records, source_name
                
            except Exception as e:
                logger.warning(f"Error with {source_name} for {symbol.symbol}: {e}")
                continue
        
        logger.error(f"All data sources failed for {symbol.symbol}")
        return None, ''
    
    def save_market_data(
        self,
        symbol: Symbol,
        records: List[Dict],
        timeframe: str = '1h',
        source_name: str = 'unknown'
    ) -> int:
        """Save market data records to database"""
        if not records:
            return 0
        
        saved = 0
        source = self.data_sources.get(source_name)
        
        with transaction.atomic():
            for record in records:
                _, created = MarketData.objects.update_or_create(
                    symbol=symbol,
                    timestamp=record['timestamp'],
                    timeframe=timeframe,
                    defaults={
                        'open_price': record['open'],
                        'high_price': record['high'],
                        'low_price': record['low'],
                        'close_price': record['close'],
                        'volume': record['volume'],
                        'source': source
                    }
                )
                if created:
                    saved += 1
        
        logger.info(f"Saved {saved} new records for {symbol.symbol} from {source_name}")
        return saved


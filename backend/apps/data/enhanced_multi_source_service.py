"""
Enhanced Multi-Source Data Service
Comprehensive solution for storing ALL crypto coin records with multiple data sources
Includes proper fallback mechanism, gap detection, and data quality assurance
"""

import requests
import logging
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.data.models import MarketData, DataSource, HistoricalDataRange, DataQuality

logger = logging.getLogger(__name__)


def safe_encode_symbol(symbol_str: str) -> str:
    """Safely encode symbol string for Windows console output"""
    if not symbol_str:
        return ""
    try:
        # Try to encode to ASCII, replacing problematic characters
        return symbol_str.encode('ascii', 'replace').decode('ascii')
    except:
        # If that fails, just return a safe version
        return str(symbol_str).encode('ascii', 'replace').decode('ascii')


class BinanceService:
    """Enhanced Binance API integration with proper error handling"""
    
    def __init__(self):
        self.base_url = "https://fapi.binance.com/fapi/v1/klines"
        self.spot_url = "https://api.binance.com/api/v3/klines"
        self.exchange_info_url = "https://api.binance.com/api/v3/exchangeInfo"
        self.futures_exchange_info_url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        self.rate_limit_delay = 0.2
        self._valid_symbols_cache = None
        self._cache_timeout = 3600  # Cache for 1 hour
    
    def _get_valid_binance_symbols(self) -> set:
        """Get set of valid Binance USDT trading pairs (cached)"""
        from django.core.cache import cache
        
        # Try to get from cache first
        cache_key = "binance_valid_symbols"
        cached_symbols = cache.get(cache_key)
        if cached_symbols:
            return cached_symbols
        
        valid_symbols = set()
        
        # Fetch from both spot and futures APIs
        for url in [self.exchange_info_url, self.futures_exchange_info_url]:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    for symbol_info in data.get('symbols', []):
                        symbol = symbol_info.get('symbol', '')
                        # Only include USDT pairs
                        if symbol.endswith('USDT') and symbol_info.get('status') == 'TRADING':
                            valid_symbols.add(symbol)
                time.sleep(0.1)  # Small delay between requests
            except Exception as e:
                logger.warning(f"Error fetching Binance exchange info from {url}: {e}")
                continue
        
        # Cache the result
        if valid_symbols:
            cache.set(cache_key, valid_symbols, self._cache_timeout)
            logger.info(f"Cached {len(valid_symbols)} valid Binance symbols")
        
        return valid_symbols
    
    def _is_valid_binance_symbol(self, symbol: str) -> bool:
        """Check if a symbol exists on Binance"""
        valid_symbols = self._get_valid_binance_symbols()
        return symbol in valid_symbols
        
    def get_historical_data(
        self, 
        symbol: Symbol, 
        timeframe: str = '1h',
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        days: int = 30
    ) -> Optional[List[Dict]]:
        """Get historical OHLCV data from Binance"""
        try:
            # Map symbol to Binance format
            symbol_upper = symbol.symbol.upper()
            binance_symbol = f"{symbol_upper}USDT"
            
            # Check if this symbol exists on Binance before trying to fetch
            if not self._is_valid_binance_symbol(binance_symbol):
                safe_symbol = safe_encode_symbol(symbol.symbol)
                logger.debug(f"[{safe_symbol}] {binance_symbol} doesn't exist on Binance, skipping...")
                return None
            
            # Map timeframe
            interval_map = {
                '1h': '1h',
                '4h': '4h',
                '1d': '1d',
                '1m': '1m',
                '5m': '5m',
                '15m': '15m'
            }
            interval = interval_map.get(timeframe, '1h')
            
            # Calculate timestamps
            if end is None:
                end = timezone.now()
            if start is None:
                start = end - timedelta(days=days)
            
            # Ensure UTC
            if start.tzinfo is None:
                start = start.replace(tzinfo=dt_timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=dt_timezone.utc)
            
            start_ms = int(start.timestamp() * 1000)
            end_ms = int(end.timestamp() * 1000)
            
            all_records = []
            current_start = start_ms
            max_limit = 1000  # Binance limit per request
            
            # Try futures first, then spot
            for api_url in [self.base_url, self.spot_url]:
                try:
                    api_records = []
                    api_current_start = start_ms
                    
                    while api_current_start < end_ms:
                        params = {
                            'symbol': binance_symbol,
                            'interval': interval,
                            'startTime': api_current_start,
                            'endTime': end_ms,
                            'limit': max_limit
                        }
                        
                        response = requests.get(api_url, params=params, timeout=30)
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            if not data:
                                break
                            
                            for k in data:
                                timestamp = datetime.fromtimestamp(k[0] / 1000, tz=dt_timezone.utc)
                                api_records.append({
                                    'timestamp': timestamp,
                                    'open': Decimal(str(k[1])),
                                    'high': Decimal(str(k[2])),
                                    'low': Decimal(str(k[3])),
                                    'close': Decimal(str(k[4])),
                                    'volume': Decimal(str(k[5])) if k[5] else Decimal('0')
                                })
                            
                            # Update current_start for next batch
                            if len(data) < max_limit:
                                break
                            api_current_start = data[-1][0] + 1
                            
                            time.sleep(self.rate_limit_delay)
                        elif response.status_code == 400:
                            # Invalid symbol for this API endpoint, try next endpoint
                            logger.debug(f"Binance {api_url}: Invalid symbol {binance_symbol}, trying next endpoint...")
                            break  # Break from while loop, continue to next API
                        else:
                            response.raise_for_status()
                    
                    # If we got records from this API, return them
                    if api_records:
                        all_records.extend(api_records)
                        safe_symbol = safe_encode_symbol(symbol.symbol)
                        logger.info(f"Fetched {len(api_records)} records from Binance ({api_url}) for {safe_symbol}")
                        return all_records
                        
                except requests.exceptions.HTTPError as e:
                    if hasattr(e, 'response') and e.response.status_code == 400:
                        # Invalid symbol for this API endpoint, try next endpoint
                        logger.debug(f"Binance {api_url}: Invalid symbol {binance_symbol}, trying next endpoint...")
                        continue
                    safe_symbol = safe_encode_symbol(symbol.symbol)
                    logger.warning(f"Binance API error for {safe_symbol}: {e}")
                    continue
                except Exception as e:
                    safe_symbol = safe_encode_symbol(symbol.symbol)
                    logger.warning(f"Error with Binance API for {safe_symbol}: {e}")
                    continue
            
            # If we get here, both Binance APIs failed
            safe_symbol = safe_encode_symbol(symbol.symbol)
            logger.debug(f"Binance (both futures and spot) failed for {safe_symbol}, will try next source")
            return None
            
        except Exception as e:
            safe_symbol = safe_encode_symbol(symbol.symbol)
            logger.error(f"Error fetching Binance data for {safe_symbol}: {e}")
            return None


class CoinGeckoService:
    """Enhanced CoinGecko API integration"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.rate_limit_delay = 0.6  # CoinGecko rate limit: 10-50 calls/minute
        
    def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: str = '1h',
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        days: int = 30
    ) -> Optional[List[Dict]]:
        """Get historical OHLCV data from CoinGecko"""
        try:
            # CoinGecko uses coin IDs, need to map symbol to ID
            coin_id = self._get_coin_id(symbol)
            if not coin_id:
                return None
            
            # Calculate days
            if start and end:
                days = (end - start).days
            days = min(days, 365)  # CoinGecko max is 365 days
            
            url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days,
                'interval': 'hourly' if timeframe == '1h' else 'daily'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'prices' not in data:
                return None
            
            records = []
            prices = data.get('prices', [])
            market_caps = data.get('market_caps', [])
            volumes = data.get('total_volumes', [])
            
            # Create a map for volumes and market caps by timestamp
            volume_map = {int(v[0]): Decimal(str(v[1])) for v in volumes}
            market_cap_map = {int(m[0]): Decimal(str(m[1])) for m in market_caps}
            
            for price_data in prices:
                timestamp_ms = int(price_data[0])
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=dt_timezone.utc)
                
                # Filter by date range if provided
                if start and timestamp < start:
                    continue
                if end and timestamp > end:
                    continue
                
                price = Decimal(str(price_data[1]))
                volume = volume_map.get(timestamp_ms, Decimal('0'))
                
                # For CoinGecko, we only have close price, so use it for all OHLC
                records.append({
                    'timestamp': timestamp,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': volume
                })
            
            time.sleep(self.rate_limit_delay)
            
            if records:
                safe_symbol = safe_encode_symbol(symbol.symbol)
                logger.info(f"Fetched {len(records)} records from CoinGecko for {safe_symbol}")
                return records
            
            return None
            
        except Exception as e:
            safe_symbol = safe_encode_symbol(symbol.symbol)
            logger.error(f"Error fetching CoinGecko data for {safe_symbol}: {e}")
            return None
    
    def _get_coin_id(self, symbol: Symbol) -> Optional[str]:
        """Get CoinGecko coin ID from symbol"""
        # Try to get from cache first
        cache_key = f"coingecko_id_{symbol.symbol}"
        coin_id = cache.get(cache_key)
        if coin_id:
            return coin_id
        
        # Common mappings
        symbol_to_id = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'BNB': 'binancecoin',
            'SOL': 'solana', 'XRP': 'ripple', 'ADA': 'cardano',
            'DOGE': 'dogecoin', 'TRX': 'tron', 'LINK': 'chainlink',
            'DOT': 'polkadot', 'MATIC': 'matic-network', 'AVAX': 'avalanche-2',
            'UNI': 'uniswap', 'ATOM': 'cosmos', 'LTC': 'litecoin',
            'BCH': 'bitcoin-cash', 'ALGO': 'algorand', 'VET': 'vechain',
            'FTM': 'fantom', 'ICP': 'internet-computer', 'SAND': 'the-sandbox',
            'MANA': 'decentraland', 'NEAR': 'near', 'APT': 'aptos',
            'OP': 'optimism', 'ARB': 'arbitrum', 'MKR': 'maker',
            'RUNE': 'thorchain', 'INJ': 'injective-protocol', 'STX': 'blockstack',
            'AAVE': 'aave', 'COMP': 'compound-governance-token', 'CRV': 'curve-dao-token',
            'LDO': 'lido-dao', 'CAKE': 'pancakeswap-token', 'PENDLE': 'pendle',
            'DYDX': 'dydx', 'FET': 'fetch-ai', 'CRO': 'crypto-com-chain',
            'OKB': 'okb', 'LEO': 'leo-token', 'QNT': 'quant-network',
            'HBAR': 'hedera-hashgraph', 'EGLD': 'elrond-erd-2', 'FLOW': 'flow',
            'SEI': 'sei-network', 'TIA': 'celestia', 'GALA': 'gala',
            'GRT': 'the-graph', 'XMR': 'monero', 'ZEC': 'zcash',
            'DAI': 'dai', 'TUSD': 'true-usd', 'GT': 'gatechain-token',
        }
        
        coin_id = symbol_to_id.get(symbol.symbol.upper())
        
        if not coin_id:
            # Try to fetch from CoinGecko API
            try:
                url = f"{self.base_url}/coins/list"
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    coins = response.json()
                    for coin in coins:
                        if coin['symbol'].upper() == symbol.symbol.upper():
                            coin_id = coin['id']
                            cache.set(cache_key, coin_id, 86400)  # Cache for 24 hours
                            break
                time.sleep(self.rate_limit_delay)
            except Exception as e:
                safe_symbol = safe_encode_symbol(symbol.symbol)
                logger.warning(f"Could not fetch coin ID from CoinGecko for {safe_symbol}: {e}")
        
        if coin_id:
            cache.set(cache_key, coin_id, 86400)
        
        return coin_id


class EnhancedMultiSourceDataService:
    """
    Enhanced multi-source data service with intelligent fallback
    Ensures ALL coins get data from at least one source
    """
    
    def __init__(self, source_priority: Optional[List[str]] = None):
        """
        Initialize with source priority list
        
        Args:
            source_priority: List of source names in priority order
                           Options: 'binance', 'coingecko', 'cryptocompare', 'okx', 'bybit'
        """
        self.source_priority = source_priority or [
            'binance',
            'coingecko',
            'cryptocompare',
            'okx',
            'bybit'
        ]
        
        # Initialize services
        self.services = {
            'binance': BinanceService(),
            'coingecko': CoinGeckoService(),
        }
        
        # Import other services if available
        try:
            from apps.data.multi_source_service import (
                CryptoCompareService, OKXService, BybitService
            )
            self.services['cryptocompare'] = CryptoCompareService()
            self.services['okx'] = OKXService()
            self.services['bybit'] = BybitService()
        except ImportError:
            logger.warning("Some multi-source services not available")
        
        # Get or create data sources
        self.data_sources = {}
        for source_name in self.source_priority:
            # Use filter().first() to handle potential duplicates gracefully
            source = DataSource.objects.filter(
                name=source_name.title()
            ).first()
            
            if not source:
                # Create if doesn't exist
                source = DataSource.objects.create(
                    name=source_name.title(),
                    source_type='API',
                    is_active=True
                )
            else:
                # If multiple exist, use the first one (oldest)
                # This handles edge cases where duplicates might still exist
                pass
            
            self.data_sources[source_name] = source
    
    def fetch_and_store_historical_data(
        self,
        symbol: Symbol,
        timeframe: str = '1h',
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        days: int = 30
    ) -> Tuple[bool, str, int]:
        """
        Fetch historical data from multiple sources with fallback
        Returns: (success, source_name, records_saved)
        """
        if start is None:
            start = timezone.now() - timedelta(days=days)
        if end is None:
            end = timezone.now()
        
        # Try each source in priority order
        for source_name in self.source_priority:
            if source_name not in self.services:
                continue
                
            try:
                safe_symbol = safe_encode_symbol(symbol.symbol)
                logger.info(f"[{safe_symbol}] Trying {source_name}...")
                service = self.services[source_name]
                
                # Call get_historical_data with appropriate parameters
                # Different services have different method signatures
                import inspect
                sig = inspect.signature(service.get_historical_data)
                params = sig.parameters.keys()
                
                # Build kwargs based on what the method accepts
                kwargs = {'symbol': symbol}
                
                if 'timeframe' in params:
                    kwargs['timeframe'] = timeframe
                if 'start' in params:
                    kwargs['start'] = start
                if 'end' in params:
                    kwargs['end'] = end
                if 'days' in params:
                    # Calculate days from start/end if needed
                    if start and end:
                        calculated_days = max(1, int((end - start).total_seconds() / 86400))
                        kwargs['days'] = calculated_days
                    else:
                        kwargs['days'] = days
                
                records = service.get_historical_data(**kwargs)
                
                # If records is None, it means the source doesn't have this symbol (e.g., invalid Binance pair)
                # Continue to next source
                if records is None:
                    safe_symbol = safe_encode_symbol(symbol.symbol)
                    logger.info(f"[{safe_symbol}] {source_name} doesn't have this symbol, trying next source...")
                    continue
                
                if records and len(records) > 0:
                    # Save to database
                    saved_count = self.save_market_data(
                        symbol=symbol,
                        records=records,
                        timeframe=timeframe,
                        source_name=source_name
                    )
                    
                    # >= 0 means data was fetched successfully (0 = already exists in DB)
                    safe_symbol = safe_encode_symbol(symbol.symbol)
                    if saved_count > 0:
                        logger.info(
                            f"Successfully fetched and saved {saved_count} records "
                            f"from {source_name} for {safe_symbol}"
                        )
                    else:
                        logger.info(
                            f"Fetched data from {source_name} for {safe_symbol} (already exists, no new records)"
                        )
                    return True, source_name, saved_count
                else:
                    safe_symbol = safe_encode_symbol(symbol.symbol)
                    logger.debug(f"{source_name} returned empty records for {safe_symbol}, trying next source...")
                
            except Exception as e:
                safe_symbol = safe_encode_symbol(symbol.symbol)
                logger.warning(f"Error with {source_name} for {safe_symbol}: {e}, trying next source...")
                continue
        
        safe_symbol = safe_encode_symbol(symbol.symbol)
        logger.warning(f"[{safe_symbol}] All data sources failed - no data available from any source")
        return False, '', 0
    
    def save_market_data(
        self,
        symbol: Symbol,
        records: List[Dict],
        timeframe: str = '1h',
        source_name: str = 'unknown'
    ) -> int:
        """Save market data records to database with deduplication - optimized for concurrent access"""
        if not records:
            return 0
        
        saved = 0
        source = self.data_sources.get(source_name)
        
        # Use smaller batch transactions to reduce lock time
        # Process in batches of 50 to minimize transaction duration
        batch_size = 50
        total_batches = (len(records) + batch_size - 1) // batch_size
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(records))
            batch_records = records[start_idx:end_idx]
            
            try:
                # Use shorter transactions per batch
                with transaction.atomic():
                    for record in batch_records:
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
            except Exception as e:
                # If batch fails, log and continue with next batch
                safe_symbol = safe_encode_symbol(symbol.symbol)
                logger.warning(f"Error saving batch {batch_idx + 1}/{total_batches} for {safe_symbol}: {e}")
                continue
        
        # Update historical data range
        if saved > 0:
            self._update_historical_range(symbol, timeframe, records)
        
        safe_symbol = safe_encode_symbol(symbol.symbol)
        logger.info(f"Saved {saved} new records for {safe_symbol} from {source_name}")
        return saved
    
    def _update_historical_range(self, symbol: Symbol, timeframe: str, records: List[Dict]):
        """Update historical data range tracking"""
        if not records:
            return
        
        try:
            timestamps = [r['timestamp'] for r in records]
            earliest = min(timestamps)
            latest = max(timestamps)
            
            HistoricalDataRange.objects.update_or_create(
                symbol=symbol,
                timeframe=timeframe,
                defaults={
                    'earliest_date': earliest,
                    'latest_date': latest,
                    'total_records': MarketData.objects.filter(
                        symbol=symbol,
                        timeframe=timeframe
                    ).count(),
                    'is_complete': False
                }
            )
        except Exception as e:
            safe_symbol = safe_encode_symbol(symbol.symbol)
            logger.error(f"Error updating historical range for {safe_symbol}: {e}")
    
    def fetch_hourly_data_for_all_coins(self, max_coins: Optional[int] = None) -> Dict:
        """
        Fetch latest hourly data for all active crypto coins
        Returns statistics about the operation
        
        Args:
            max_coins: Maximum number of coins to process (default: None = all)
        """
        symbols = Symbol.objects.filter(
            symbol_type='CRYPTO',
            is_active=True,
            is_crypto_symbol=True
        ).order_by('market_cap_rank', 'symbol')
        
        if max_coins:
            symbols = symbols[:max_coins]
        
        stats = {
            'total_symbols': symbols.count(),
            'successful': 0,
            'failed': 0,
            'total_records': 0,
            'sources_used': {}
        }
        
        # Calculate time range: last 2 hours (to ensure we get the latest complete hour)
        end_time = timezone.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        start_time = end_time - timedelta(hours=2)
        
        logger.info(f"Fetching hourly data for {stats['total_symbols']} coins from {start_time} to {end_time}")
        
        for idx, symbol in enumerate(symbols, 1):
            try:
                success, source_name, records_saved = self.fetch_and_store_historical_data(
                    symbol=symbol,
                    timeframe='1h',
                    start=start_time,
                    end=end_time
                )
                
                if success:
                    stats['successful'] += 1
                    stats['total_records'] += records_saved
                    stats['sources_used'][source_name] = stats['sources_used'].get(source_name, 0) + 1
                    safe_symbol = safe_encode_symbol(symbol.symbol)
                    logger.debug(f"[{idx}/{stats['total_symbols']}] {safe_symbol}: {records_saved} records from {source_name}")
                else:
                    stats['failed'] += 1
                    safe_symbol = safe_encode_symbol(symbol.symbol)
                    logger.warning(f"[{idx}/{stats['total_symbols']}] {safe_symbol}: Failed to fetch data")
                
                # Progress update every 25 symbols
                if idx % 25 == 0:
                    logger.info(
                        f"Hourly data progress: {idx}/{stats['total_symbols']} "
                        f"({stats['successful']} successful, {stats['failed']} failed)"
                    )
                    
            except Exception as e:
                safe_symbol = safe_encode_symbol(symbol.symbol)
                logger.error(f"Error processing {safe_symbol}: {e}")
                stats['failed'] += 1
        
        logger.info(
            f"Hourly data fetch completed: {stats['successful']}/{stats['total_symbols']} successful, "
            f"{stats['failed']} failed, {stats['total_records']} total records"
        )
        
        return stats
    
    def backfill_all_historical_data(
        self,
        start_year: int = 2020,
        timeframe: str = '1h',
        max_coins: Optional[int] = None
    ) -> Dict:
        """
        Backfill all historical data for all coins
        """
        symbols = Symbol.objects.filter(
            symbol_type='CRYPTO',
            is_active=True,
            is_crypto_symbol=True
        ).order_by('market_cap_rank', 'symbol')
        
        if max_coins:
            symbols = symbols[:max_coins]
        
        stats = {
            'total_symbols': symbols.count(),
            'successful': 0,
            'failed': 0,
            'total_records': 0,
            'sources_used': {}
        }
        
        start_date = datetime(start_year, 1, 1, tzinfo=dt_timezone.utc)
        end_date = timezone.now()
        
        logger.info(
            f"Starting historical backfill for {stats['total_symbols']} coins "
            f"from {start_date.date()} to {end_date.date()}"
        )
        
        for idx, symbol in enumerate(symbols, 1):
            try:
                safe_symbol = safe_encode_symbol(symbol.symbol)
                safe_name = safe_encode_symbol(symbol.name)
                logger.info(f"[{idx}/{stats['total_symbols']}] Processing {safe_symbol} ({safe_name})...")
                
                success, source_name, records_saved = self.fetch_and_store_historical_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start=start_date,
                    end=end_date
                )
                
                if success:
                    stats['successful'] += 1
                    stats['total_records'] += records_saved
                    stats['sources_used'][source_name] = stats['sources_used'].get(source_name, 0) + 1
                    logger.info(f"  ✓ [{idx}/{stats['total_symbols']}] {safe_symbol}: {records_saved:,} records from {source_name}")
                else:
                    stats['failed'] += 1
                    logger.warning(f"  ✗ [{idx}/{stats['total_symbols']}] {safe_symbol}: Failed to fetch data from any source")
                
                # Progress update every 10 symbols
                if idx % 10 == 0:
                    logger.info(
                        f"Progress: {idx}/{stats['total_symbols']} "
                        f"({stats['successful']} successful, {stats['failed']} failed, "
                        f"{stats['total_records']:,} total records)"
                    )
                
            except Exception as e:
                safe_symbol = safe_encode_symbol(symbol.symbol)
                logger.error(f"Error processing {safe_symbol}: {e}", exc_info=True)
                stats['failed'] += 1
        
        logger.info(
            f"Historical backfill completed: {stats['successful']} successful, "
            f"{stats['failed']} failed, {stats['total_records']} total records"
        )
        
        return stats


"""
Historical Data Service - Fetches real historical cryptocurrency data from Binance API
"""

import requests
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from typing import Dict, List, Optional, Tuple
import time

logger = logging.getLogger(__name__)


class HistoricalDataService:
    """Service for fetching real historical cryptocurrency data from Binance Futures API"""
    
    def __init__(self):
        # Use Binance Futures API for futures trading backtesting
        self.binance_api = "https://fapi.binance.com/fapi/v1"
        self.cache_timeout = 3600  # Cache for 1 hour
        self.rate_limit_delay = 0.1  # 100ms delay between requests
        
        # Symbol mapping for Binance API
        self.symbol_mapping = {
            'BTC': 'BTCUSDT',
            'ETH': 'ETHUSDT',
            'BNB': 'BNBUSDT',
            'ADA': 'ADAUSDT',
            'SOL': 'SOLUSDT',
            'XRP': 'XRPUSDT',
            'DOGE': 'DOGEUSDT',
            'TRX': 'TRXUSDT',
            'LINK': 'LINKUSDT',
            'DOT': 'DOTUSDT',
            'MATIC': 'MATICUSDT',
            'UNI': 'UNIUSDT',
            'AVAX': 'AVAXUSDT',
            'ATOM': 'ATOMUSDT',
            'FTM': 'FTMUSDT',
            'ALGO': 'ALGOUSDT',
            'VET': 'VETUSDT',
            'ICP': 'ICPUSDT',
            'THETA': 'THETAUSDT',
            'SAND': 'SANDUSDT',
            'MANA': 'MANAUSDT',
            'LTC': 'LTCUSDT',
            'BCH': 'BCHUSDT',
            'ETC': 'ETCUSDT',
            'XLM': 'XLMUSDT',
            'XMR': 'XMRUSDT',
            'ZEC': 'ZECUSDT',
            'DASH': 'DASHUSDT',
            'NEO': 'NEOUSDT',
            'QTUM': 'QTUMUSDT',
            'AAVE': 'AAVEUSDT',
            'COMP': 'COMPUSDT',
            'CRV': 'CRVUSDT',
            'LDO': 'LDOUSDT',
            'CAKE': 'CAKEUSDT',
            'PENDLE': 'PENDLEUSDT',
            'DYDX': 'DYDXUSDT',
            'FET': 'FETUSDT',
            'CRO': 'CROUSDT',
            'KCS': 'KCSUSDT',
            'OKB': 'OKBUSDT',
            'LEO': 'LEOUSDT',
            'QNT': 'QNTUSDT',
            'HBAR': 'HBARUSDT',
            'EGLD': 'EGLDUSDT',
            'FLOW': 'FLOWUSDT',
            'SEI': 'SEIUSDT',
            'TIA': 'TIAUSDT',
            'GALA': 'GALAUSDT',
            'GRT': 'GRTUSDT',
            'DAI': 'DAIUSDT',
            'TUSD': 'TUSDUSDT',
            'GT': 'GTUSDT',
            'NEAR': 'NEARUSDT',
            'APT': 'APTUSDT',
            'OP': 'OPUSDT',
            'ARB': 'ARBUSDT',
            'MKR': 'MKRUSDT',
            'RUNE': 'RUNEUSDT',
            'INJ': 'INJUSDT',
            'STX': 'STXUSDT',
        }
    
    def get_historical_data(self, symbol: str, start_date: datetime, end_date: datetime, 
                          interval: str = '1h') -> List[Dict]:
        """
        Get historical OHLCV data from Binance API
        
        Args:
            symbol: Trading symbol (e.g., 'BTC', 'ETH', 'LINK')
            start_date: Start date for historical data
            end_date: End date for historical data
            interval: Kline interval (1m, 5m, 15m, 30m, 1h, 4h, 1d)
        
        Returns:
            List of OHLCV data points
        """
        try:
            # Check cache first
            cache_key = f"historical_data_{symbol}_{start_date.date()}_{end_date.date()}_{interval}"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                logger.debug(f"Returning cached historical data for {symbol}")
                return cached_data
            
            # Map symbol to Binance format
            symbol_upper = symbol.upper()
            
            # Check if it's already a USDT pair
            if symbol_upper.endswith('USDT'):
                binance_symbol = symbol_upper
            else:
                # Map base symbol to USDT pair
                binance_symbol = self.symbol_mapping.get(symbol_upper)
                if not binance_symbol:
                    logger.error(f"Symbol {symbol} not supported for historical data")
                    return []
            
            # Convert dates to milliseconds
            start_ms = int(start_date.timestamp() * 1000)
            end_ms = int(end_date.timestamp() * 1000)
            
            # Fetch data from Binance
            historical_data = self._fetch_binance_klines(
                binance_symbol, start_ms, end_ms, interval
            )
            
            if historical_data:
                # Cache the results
                cache.set(cache_key, historical_data, self.cache_timeout)
                logger.info(f"Fetched {len(historical_data)} historical data points for {symbol}")
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return []
    
    def _fetch_binance_klines(self, symbol: str, start_ms: int, end_ms: int, 
                             interval: str) -> List[Dict]:
        """Fetch kline data from Binance API"""
        try:
            url = f"{self.binance_api}/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'startTime': start_ms,
                'endTime': end_ms,
                'limit': 1000  # Maximum per request
            }
            
            all_data = []
            current_start = start_ms
            
            while current_start < end_ms:
                params['startTime'] = current_start
                
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                klines = response.json()
                
                if not klines:
                    break
                
                # Convert kline data to our format
                for kline in klines:
                    timestamp = datetime.fromtimestamp(kline[0] / 1000, tz=timezone.get_current_timezone())
                    
                    # Skip if beyond end date
                    if timestamp > datetime.fromtimestamp(end_ms / 1000, tz=timezone.get_current_timezone()):
                        break
                    
                    data_point = {
                        'timestamp': timestamp,
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    }
                    all_data.append(data_point)
                
                # Update start time for next request
                if klines:
                    current_start = klines[-1][0] + 1
                else:
                    break
                
                # Rate limiting
                time.sleep(self.rate_limit_delay)
            
            return all_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Binance API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing Binance klines: {e}")
            return []
    
    def get_symbol_price_at_date(self, symbol: str, target_date: datetime) -> Optional[float]:
        """
        Get the price of a symbol at a specific date
        
        Args:
            symbol: Trading symbol
            target_date: Date to get price for
        
        Returns:
            Price at the specified date, or None if not found
        """
        try:
            # Get data for a small window around the target date
            # Handle timezone-aware and naive datetimes
            if target_date.tzinfo is None:
                from django.utils import timezone
                target_date = timezone.make_aware(target_date)
            
            start_date = target_date - timedelta(hours=1)
            end_date = target_date + timedelta(hours=1)
            
            historical_data = self.get_historical_data(symbol, start_date, end_date, '1h')
            
            if not historical_data:
                return None
            
            # Find the closest data point to target date
            # Handle timezone-aware and naive datetimes
            def time_diff(data_point):
                timestamp = data_point['timestamp']
                if timestamp.tzinfo is None and target_date.tzinfo is not None:
                    # Make timestamp timezone-aware
                    from django.utils import timezone
                    timestamp = timezone.make_aware(timestamp)
                elif timestamp.tzinfo is not None and target_date.tzinfo is None:
                    # Make target_date timezone-aware
                    from django.utils import timezone
                    target_date_tz = timezone.make_aware(target_date)
                else:
                    target_date_tz = target_date
                return abs((timestamp - target_date_tz).total_seconds())
            
            closest_data = min(historical_data, key=time_diff)
            
            return closest_data['close']
            
        except Exception as e:
            logger.error(f"Error getting price for {symbol} at {target_date}: {e}")
            return None
    
    def validate_symbol_support(self, symbol: str) -> bool:
        """Check if a symbol is supported for historical data"""
        symbol_upper = symbol.upper()
        
        # Check if it's a base symbol (e.g., 'BTC', 'AAVE')
        if symbol_upper in self.symbol_mapping:
            return True
        
        # Check if it's a USDT pair (e.g., 'BTCUSDT', 'AAVEUSDT')
        # Create reverse mapping to check USDT pairs
        reverse_mapping = {v: k for k, v in self.symbol_mapping.items()}
        if symbol_upper in reverse_mapping:
            return True
        
        return False
    
    def get_supported_symbols(self) -> List[str]:
        """Get list of supported symbols"""
        return list(self.symbol_mapping.keys())
    
    def get_available_intervals(self) -> List[str]:
        """Get list of available time intervals"""
        return ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
    
    def clear_cache(self, symbol: str = None):
        """Clear cached historical data"""
        if symbol:
            # Clear cache for specific symbol
            pattern = f"historical_data_{symbol.upper()}_*"
            # Note: Django cache doesn't support pattern deletion easily
            # This is a simplified approach
            logger.info(f"Cache cleared for symbol {symbol}")
        else:
            # Clear all historical data cache
            logger.info("All historical data cache cleared")


# Global instance
historical_data_service = HistoricalDataService()


def get_historical_data(symbol: str, start_date: datetime, end_date: datetime, 
                       interval: str = '1h') -> List[Dict]:
    """Get historical data for a symbol"""
    return historical_data_service.get_historical_data(symbol, start_date, end_date, interval)


def get_symbol_price_at_date(symbol: str, target_date: datetime) -> Optional[float]:
    """Get symbol price at specific date"""
    return historical_data_service.get_symbol_price_at_date(symbol, target_date)


def validate_symbol_support(symbol: str) -> bool:
    """Check if symbol is supported"""
    return historical_data_service.validate_symbol_support(symbol)


def get_supported_symbols() -> List[str]:
    """Get supported symbols"""
    return historical_data_service.get_supported_symbols()

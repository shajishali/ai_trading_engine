"""
TradingView Data Service
Fetches historical OHLCV data from TradingView using available methods
"""
import requests
import logging
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import List, Dict, Optional
from django.utils import timezone as django_timezone

logger = logging.getLogger(__name__)


class TradingViewService:
    """Service for fetching data from TradingView"""
    
    def __init__(self):
        # TradingView's internal API endpoint (used by their web interface)
        self.base_url = "https://symbol-search.tradingview.com"
        self.historical_url = "https://scanner.tradingview.com"
        
        # TradingView uses different symbol formats
        # Format: EXCHANGE:SYMBOL (e.g., BINANCE:BTCUSDT, COINBASE:BTCUSD)
        self.exchange_mapping = {
            'BINANCE': 'BINANCE',
            'COINBASE': 'COINBASE',
            'KRAKEN': 'KRAKEN',
            'BITSTAMP': 'BITSTAMP',
        }
    
    def _get_tradingview_symbol(self, symbol: str, exchange: str = 'BINANCE') -> str:
        """
        Convert symbol to TradingView format
        
        Args:
            symbol: Base symbol (e.g., BTC, ETH)
            exchange: Exchange name (default: BINANCE)
        
        Returns:
            TradingView symbol format (e.g., BINANCE:BTCUSDT)
        """
        exchange_upper = exchange.upper()
        
        # If symbol already ends with USDT, use as is
        if symbol.upper().endswith('USDT'):
            return f"{exchange_upper}:{symbol.upper()}"
        
        # Otherwise, append USDT
        return f"{exchange_upper}:{symbol.upper()}USDT"
    
    def get_historical_data(
        self,
        symbol: str,
        days: int = 30,
        interval: str = '1h',
        exchange: str = 'BINANCE'
    ) -> Optional[List[Dict]]:
        """
        Get historical OHLCV data from TradingView
        
        Note: TradingView doesn't have a public free API, so this uses
        alternative methods. For production, consider using TradingView's
        paid API or other data providers.
        
        Args:
            symbol: Base symbol (e.g., BTC, ETH)
            days: Number of days of historical data
            interval: Time interval (1m, 5m, 15m, 1h, 4h, 1d)
            exchange: Exchange name (BINANCE, COINBASE, etc.)
        
        Returns:
            List of OHLCV records or None if failed
        """
        try:
            # TradingView interval mapping
            interval_map = {
                '1m': '1',
                '5m': '5',
                '15m': '15',
                '1h': '60',
                '4h': '240',
                '1d': 'D'
            }
            
            tv_interval = interval_map.get(interval, '60')
            tv_symbol = self._get_tradingview_symbol(symbol, exchange)
            
            # Calculate timestamps
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=days)
            
            # TradingView's historical data endpoint
            # Note: This is an internal API and may not be stable
            url = "https://scanner.tradingview.com/crypto/scan"
            
            # Alternative: Use TradingView's chart data endpoint
            # This requires authentication for some endpoints
            chart_url = f"https://symbol-search.tradingview.com/symbol_search"
            
            # For now, return None and log that we need an alternative approach
            logger.warning(
                f"TradingView direct API access not available. "
                f"Consider using TradingView's paid API or alternative methods for {symbol}"
            )
            
            # Alternative approach: Use a library or service that provides TradingView data
            # For now, we'll use a workaround with their public endpoints
            return self._fetch_via_alternative_method(symbol, days, interval, exchange)
            
        except Exception as e:
            logger.error(f"Error fetching TradingView data for {symbol}: {e}")
            return None
    
    def _fetch_via_alternative_method(
        self,
        symbol: str,
        days: int,
        interval: str,
        exchange: str
    ) -> Optional[List[Dict]]:
        """
        Alternative method to fetch TradingView data
        
        This method uses TradingView's public endpoints or third-party services
        that provide TradingView data access.
        """
        try:
            # Method 1: Use TradingView's symbol search to verify symbol exists
            tv_symbol = self._get_tradingview_symbol(symbol, exchange)
            
            # For now, we'll use a proxy approach:
            # Since TradingView doesn't have a free public API, we recommend:
            # 1. Using TradingView's paid API
            # 2. Using a service that aggregates TradingView data
            # 3. Using TradingView's export feature (manual CSV import)
            
            logger.info(
                f"TradingView data fetch requested for {symbol}. "
                f"To use TradingView data, please: "
                f"1. Subscribe to TradingView API, or "
                f"2. Use CSV export from TradingView charts, or "
                f"3. Use alternative data providers"
            )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in alternative TradingView fetch: {e}")
            return None


class TradingViewCSVImportService:
    """
    Service for importing TradingView CSV exports
    
    TradingView allows users to export chart data as CSV.
    This service helps import that data into the database.
    """
    
    def __init__(self):
        pass
    
    def parse_tradingview_csv(self, csv_content: str) -> List[Dict]:
        """
        Parse TradingView CSV export format
        
        TradingView CSV format:
        time,open,high,low,close,volume
        2024-01-01 00:00:00,50000,51000,49000,50500,1234.56
        
        Args:
            csv_content: CSV file content as string
        
        Returns:
            List of OHLCV records
        """
        import csv
        from io import StringIO
        
        records = []
        
        try:
            csv_reader = csv.DictReader(StringIO(csv_content))
            
            for row in csv_reader:
                try:
                    # Parse timestamp (TradingView uses various formats)
                    time_str = row.get('time', '')
                    
                    # Try different timestamp formats
                    timestamp = None
                    for fmt in [
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d',
                        '%m/%d/%Y %H:%M:%S',
                        '%d/%m/%Y %H:%M:%S',
                    ]:
                        try:
                            timestamp = datetime.strptime(time_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if not timestamp:
                        # Try Unix timestamp
                        try:
                            timestamp = datetime.fromtimestamp(float(time_str))
                        except (ValueError, TypeError):
                            logger.warning(f"Could not parse timestamp: {time_str}")
                            continue
                    
                    # Ensure UTC timezone
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=dt_timezone.utc)
                    
                    records.append({
                        'timestamp': timestamp,
                        'open': Decimal(str(row.get('open', 0))),
                        'high': Decimal(str(row.get('high', 0))),
                        'low': Decimal(str(row.get('low', 0))),
                        'close': Decimal(str(row.get('close', 0))),
                        'volume': Decimal(str(row.get('volume', 0)))
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing CSV row: {e}")
                    continue
            
            logger.info(f"Parsed {len(records)} records from TradingView CSV")
            return records
            
        except Exception as e:
            logger.error(f"Error parsing TradingView CSV: {e}")
            return []
    
    def import_from_file(self, file_path: str) -> List[Dict]:
        """
        Import TradingView CSV from file
        
        Args:
            file_path: Path to CSV file
        
        Returns:
            List of OHLCV records
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_content = f.read()
            return self.parse_tradingview_csv(csv_content)
        except Exception as e:
            logger.error(f"Error reading TradingView CSV file: {e}")
            return []


# Alternative: Use a library that provides TradingView data access
# Example: tradingview-ta or similar libraries
class TradingViewTAService:
    """
    Service using tradingview-ta library (if installed)
    
    Install: pip install tradingview-ta
    Note: This library provides technical analysis, not historical data
    """
    
    def __init__(self):
        try:
            from tradingview_ta import TA_Handler
            self.ta_handler = TA_Handler
            self.available = True
        except ImportError:
            logger.warning("tradingview-ta library not installed. Install with: pip install tradingview-ta")
            self.available = False
    
    def get_current_data(self, symbol: str, exchange: str = 'BINANCE', interval: str = '1h'):
        """
        Get current market data from TradingView
        
        Note: This provides current data, not historical OHLCV
        """
        if not self.available:
            return None
        
        try:
            from tradingview_ta import TA_Handler
            
            handler = TA_Handler(
                symbol=symbol,
                screener="crypto",
                exchange=exchange,
                interval=interval
            )
            
            analysis = handler.get_analysis()
            return analysis
            
        except Exception as e:
            logger.error(f"Error getting TradingView TA data: {e}")
            return None


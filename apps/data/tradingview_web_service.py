"""
TradingView Web Service - Fetches data using TradingView's web endpoints
Uses TradingView's public charting data endpoints
"""
import requests
import logging
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class TradingViewWebService:
    """
    Service to fetch historical data from TradingView using their web API
    
    Note: TradingView uses a session-based API. This service attempts to
    access their public endpoints. For production use, consider:
    1. TradingView's paid API subscription
    2. Using TradingView's CSV export feature
    3. Using alternative data providers that aggregate TradingView data
    """
    
    def __init__(self):
        self.base_url = "https://symbol-search.tradingview.com"
        self.chart_url = "https://scanner.tradingview.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        })
    
    def _get_tradingview_symbol(self, symbol: str, exchange: str = 'BINANCE') -> str:
        """Convert symbol to TradingView format"""
        symbol_upper = symbol.upper()
        
        if symbol_upper.endswith('USDT'):
            return f"{exchange}:{symbol_upper}"
        
        return f"{exchange}:{symbol_upper}USDT"
    
    def search_symbol(self, symbol: str) -> Optional[Dict]:
        """Search for symbol on TradingView"""
        try:
            url = f"{self.base_url}/symbol_search"
            params = {
                'text': symbol,
                'exchange': '',
                'lang': 'en',
                'search_type': 'undefined',
                'domain': 'production',
                'sort_by_country': 'US'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                return data[0]  # Return first match
            return None
            
        except Exception as e:
            logger.error(f"Error searching TradingView symbol {symbol}: {e}")
            return None
    
    def get_historical_data(
        self,
        symbol: str,
        days: int = 30,
        interval: str = '1h',
        exchange: str = 'BINANCE'
    ) -> Optional[List[Dict]]:
        """
        Get historical OHLCV data from TradingView
        
        This method uses TradingView's internal API endpoints.
        Note: This may require authentication or may be rate-limited.
        """
        try:
            tv_symbol = self._get_tradingview_symbol(symbol, exchange)
            
            # TradingView uses a session-based API
            # We need to get a session ID first
            session_id = self._get_session_id()
            if not session_id:
                logger.warning("Could not get TradingView session ID")
                return None
            
            # Calculate timestamps
            end_time = int(datetime.now(timezone.utc).timestamp())
            start_time = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
            
            # TradingView chart data endpoint
            # Format: https://scanner.tradingview.com/crypto/scan
            # This is a complex endpoint that requires proper authentication
            
            # Alternative: Use a library that handles TradingView API
            # For now, we'll use a simpler approach with their public endpoints
            
            logger.info(
                f"TradingView data fetch for {symbol}. "
                f"Note: TradingView requires authentication for historical data API. "
                f"Consider using CSV export or paid API."
            )
            
            # Return None - user should use CSV import or alternative method
            return None
            
        except Exception as e:
            logger.error(f"Error fetching TradingView historical data: {e}")
            return None
    
    def _get_session_id(self) -> Optional[str]:
        """Get TradingView session ID (if needed)"""
        try:
            # TradingView session management
            # This is a simplified version - actual implementation may vary
            return None
        except Exception as e:
            logger.error(f"Error getting TradingView session: {e}")
            return None


class TradingViewDataImporter:
    """
    Import TradingView CSV exports into database
    
    This is the recommended way to use TradingView data:
    1. Export data from TradingView charts as CSV
    2. Use this service to import into database
    """
    
    def __init__(self):
        from .tradingview_service import TradingViewCSVImportService
        self.csv_importer = TradingViewCSVImportService()
    
    def import_csv_to_database(
        self,
        csv_file_path: str,
        symbol_obj,
        timeframe: str = '1h'
    ) -> int:
        """
        Import TradingView CSV export into MarketData table
        
        Args:
            csv_file_path: Path to TradingView CSV export
            symbol_obj: Symbol model instance
            timeframe: Timeframe (1h, 4h, 1d, etc.)
        
        Returns:
            Number of records imported
        """
        try:
            from apps.data.models import MarketData, DataSource
            from django.db import transaction
            
            # Parse CSV
            records = self.csv_importer.import_from_file(csv_file_path)
            
            if not records:
                logger.warning(f"No records parsed from CSV file: {csv_file_path}")
                return 0
            
            # Get or create TradingView data source
            data_source, _ = DataSource.objects.get_or_create(
                name='TradingView',
                defaults={
                    'source_type': 'FILE',
                    'is_active': True
                }
            )
            
            # Save to database
            saved = 0
            with transaction.atomic():
                for record in records:
                    _, created = MarketData.objects.update_or_create(
                        symbol=symbol_obj,
                        timestamp=record['timestamp'],
                        timeframe=timeframe,
                        defaults={
                            'open_price': record['open'],
                            'high_price': record['high'],
                            'low_price': record['low'],
                            'close_price': record['close'],
                            'volume': record['volume'],
                            'source': data_source
                        }
                    )
                    if created:
                        saved += 1
            
            logger.info(f"Imported {saved} records from TradingView CSV for {symbol_obj.symbol}")
            return saved
            
        except Exception as e:
            logger.error(f"Error importing TradingView CSV: {e}")
            return 0


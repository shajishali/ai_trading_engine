import time
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Dict, List, Optional

import requests
from requests.exceptions import HTTPError
from django.db import transaction
from django.utils import timezone

from apps.trading.models import Symbol
from apps.data.models import MarketData, HistoricalDataRange


logger = logging.getLogger(__name__)


class HistoricalDataManager:
    """Fetch, store, and track historical OHLCV data for futures trading backtesting.

    Responsibilities:
    - Chunked fetching from Binance Futures klines API per timeframe
    - Idempotent upsert to MarketData keyed by (symbol, timestamp, timeframe)
    - Range tracking via HistoricalDataRange
    - Simple rate limiting and retry logic
    """

    def __init__(self) -> None:
        # Use Binance Futures API for futures trading backtesting
        self.binance_api_base = "https://fapi.binance.com/fapi/v1/klines"
        self.base_delay_seconds = 0.2
        self.burst_every = 20
        self.burst_sleep = 2.0

        self.timeframes: Dict[str, Dict[str, int | str]] = {
            '1m': {'interval': '1m', 'max_days': 1},
            '5m': {'interval': '5m', 'max_days': 5},
            '15m': {'interval': '15m', 'max_days': 10},
            '1h': {'interval': '1h', 'max_days': 41},
            '4h': {'interval': '4h', 'max_days': 166},
            '1d': {'interval': '1d', 'max_days': 1000},
        }

        self.symbol_mapping: Dict[str, str] = {
            'BTC': 'BTCUSDT', 'ETH': 'ETHUSDT', 'BNB': 'BNBUSDT', 'SOL': 'SOLUSDT', 'XRP': 'XRPUSDT',
            'ADA': 'ADAUSDT', 'DOGE': 'DOGEUSDT', 'TRX': 'TRXUSDT', 'LINK': 'LINKUSDT', 'DOT': 'DOTUSDT',
            'MATIC': 'MATICUSDT', 'AVAX': 'AVAXUSDT', 'UNI': 'UNIUSDT', 'ATOM': 'ATOMUSDT', 'LTC': 'LTCUSDT',
            'BCH': 'BCHUSDT', 'ALGO': 'ALGOUSDT', 'VET': 'VETUSDT', 'FTM': 'FTMUSDT', 'ICP': 'ICPUSDT',
            'SAND': 'SANDUSDT', 'MANA': 'MANAUSDT', 'NEAR': 'NEARUSDT', 'APT': 'APTUSDT', 'OP': 'OPUSDT',
            'ARB': 'ARBUSDT', 'MKR': 'MKRUSDT', 'RUNE': 'RUNEUSDT', 'INJ': 'INJUSDT', 'STX': 'STXUSDT',
            'AAVE': 'AAVEUSDT', 'COMP': 'COMPUSDT', 'CRV': 'CRVUSDT', 'LDO': 'LDOUSDT', 'CAKE': 'CAKEUSDT',
            'PENDLE': 'PENDLEUSDT', 'DYDX': 'DYDXUSDT', 'FET': 'FETUSDT', 'CRO': 'CROUSDT', 'KCS': 'KCSUSDT',
            'OKB': 'OKBUSDT', 'LEO': 'LEOUSDT', 'QNT': 'QNTUSDT', 'HBAR': 'HBARUSDT', 'EGLD': 'EGLDUSDT',
            'FLOW': 'FLOWUSDT', 'SEI': 'SEIUSDT', 'TIA': 'TIAUSDT', 'GALA': 'GALAUSDT', 'GRT': 'GRTUSDT',
            'XMR': 'XMRUSDT', 'ZEC': 'ZECUSDT', 'DAI': 'DAIUSDT', 'TUSD': 'TUSDUSDT', 'GT': 'GTUSDT',
        }

    def fetch_complete_historical_data(
        self,
        symbol: Symbol,
        timeframe: str = '1h',
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> bool:
        """Fetch and persist historical OHLCV between start and end for a symbol/timeframe.

        If start/end are not provided, defaults to 2020-01-01 → now.
        """
        if timeframe not in self.timeframes:
            logger.error(f"Unsupported timeframe: {timeframe}")
            return False

        # Try to get mapped symbol (for Binance)
        symbol_upper = symbol.symbol.upper()
        mapped = self.symbol_mapping.get(symbol_upper)
        
        # If not in mapping, handle different cases:
        if not mapped:
            # Case 1: Symbol already ends with USDT (e.g., XRPUSDT -> XRPUSDT)
            if symbol_upper.endswith('USDT'):
                mapped = symbol_upper
                logger.debug(f"Symbol {symbol.symbol} is already a USDT pair: {mapped}")
            # Case 2: Try to construct Binance symbol (e.g., BTC -> BTCUSDT)
            else:
                mapped = f"{symbol_upper}USDT"
                # Safely encode symbol name for Windows console
                safe_symbol = symbol.symbol.encode('ascii', 'replace').decode('ascii')
                safe_mapped = mapped.encode('ascii', 'replace').decode('ascii')
                logger.warning(f"Symbol {safe_symbol} not in mapping, trying {safe_mapped} (may fail if pair doesn't exist)")

        # Ensure all dates are UTC
        if start is None:
            start = datetime(2020, 1, 1, tzinfo=dt_timezone.utc)
        elif start.tzinfo is None:
            start = start.replace(tzinfo=dt_timezone.utc)
            
        if end is None:
            end = timezone.now()
        elif end.tzinfo is None:
            end = end.replace(tzinfo=dt_timezone.utc)

        max_days = int(self.timeframes[timeframe]['max_days'])
        interval = str(self.timeframes[timeframe]['interval'])

        current = start
        total_saved = 0
        request_count = 0

        while current < end:
            window_end = min(current + timedelta(days=max_days), end)
            klines = self._fetch_klines_chunk(mapped, current, window_end, interval)
            if klines:
                saved = self._save_market_data(symbol, timeframe, klines)
                total_saved += saved
                # Avoid Unicode arrows to be compatible with Windows console
                # Safely encode symbol name for Windows console
                safe_symbol = symbol.symbol.encode('ascii', 'replace').decode('ascii')
                logger.info(
                    "Saved %s records for %s %s %s -> %s",
                    saved,
                    safe_symbol,
                    timeframe,
                    str(current.date()),
                    str(window_end.date()),
                )

            current = window_end
            request_count += 1

            if request_count % self.burst_every == 0:
                time.sleep(self.burst_sleep)
            else:
                time.sleep(self.base_delay_seconds)

        self._update_range(symbol, timeframe, start, end, total_saved)
        # Safely encode symbol name for Windows console
        safe_symbol = symbol.symbol.encode('ascii', 'replace').decode('ascii')
        logger.info("Backfill complete: %s %s, total_saved=%s", safe_symbol, timeframe, total_saved)
        return True

    def _fetch_klines_chunk(self, mapped_symbol: str, start: datetime, end: datetime, interval: str) -> List[Dict]:
        """Fetch klines chunk with proper UTC handling"""
        # Ensure timestamps are UTC
        if start.tzinfo is None:
            start = start.replace(tzinfo=dt_timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=dt_timezone.utc)
            
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        params = {
            'symbol': mapped_symbol,
            'interval': interval,
            'startTime': start_ms,
            'endTime': end_ms,
            'limit': 1000,
        }

        for attempt in range(3):
            try:
                resp = requests.get(self.binance_api_base, params=params, timeout=30)
                
                # Log detailed error information for debugging
                if resp.status_code != 200:
                    error_msg = f"Binance API error for {mapped_symbol}: Status {resp.status_code}"
                    try:
                        error_body = resp.json()
                        error_msg += f" - {error_body}"
                        logger.error(f"{error_msg} | Params: {params}")
                    except:
                        error_msg += f" - {resp.text[:200]}"
                        logger.error(f"{error_msg} | Params: {params}")
                    
                    # Don't retry on 400 Bad Request (invalid symbol) - it won't succeed
                    if resp.status_code == 400:
                        logger.error(f"Invalid trading pair: {mapped_symbol}. Skipping retries.")
                        return []
                    
                    resp.raise_for_status()
                
                data = resp.json()

                parsed: List[Dict] = []
                for k in data:
                    # Ensure timestamp is UTC
                    timestamp = datetime.fromtimestamp(k[0] / 1000, tz=dt_timezone.utc)
                    parsed.append({
                        'timestamp': timestamp,
                        'open': Decimal(str(k[1])),
                        'high': Decimal(str(k[2])),
                        'low': Decimal(str(k[3])),
                        'close': Decimal(str(k[4])),
                        'volume': Decimal(str(k[5])) if k[5] is not None else Decimal('0'),
                    })
                return parsed
            except requests.exceptions.HTTPError as e:
                # HTTP errors (400, 404, 500, etc.)
                delay = 0.5 * (2 ** attempt)
                error_detail = f"HTTP {e.response.status_code}" if hasattr(e, 'response') else str(e)
                logger.warning(f"Fetch attempt {attempt+1} failed for {mapped_symbol}: {error_detail}; retrying in {delay:.1f}s")
                time.sleep(delay)
            except Exception as e:
                # Other errors (timeout, connection, etc.)
                delay = 0.5 * (2 ** attempt)
                logger.warning(f"Fetch attempt {attempt+1} failed for {mapped_symbol}: {e}; retrying in {delay:.1f}s")
                time.sleep(delay)

        logger.error(f"Failed to fetch klines for {mapped_symbol} after {3} retries")
        return []

    def _save_market_data(self, symbol: Symbol, timeframe: str, records: List[Dict]) -> int:
        """Save market data with proper UTC timestamps"""
        saved = 0
        with transaction.atomic():
            for r in records:
                # Ensure timestamp is UTC
                timestamp = r['timestamp']
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=dt_timezone.utc)
                    
                _, created = MarketData.objects.update_or_create(
                    symbol=symbol,
                    timestamp=timestamp,
                    timeframe=timeframe,
                    defaults={
                        'open_price': r['open'],
                        'high_price': r['high'],
                        'low_price': r['low'],
                        'close_price': r['close'],
                        'volume': r['volume'],
                    }
                )
                if created:
                    saved += 1
        return saved

    def _update_range(self, symbol: Symbol, timeframe: str, start: datetime, end: datetime, total: int) -> None:
        """Update range tracking with UTC timestamps"""
        try:
            # Ensure timestamps are UTC
            if start.tzinfo is None:
                start = start.replace(tzinfo=dt_timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=dt_timezone.utc)
                
            HistoricalDataRange.objects.update_or_create(
                symbol=symbol,
                timeframe=timeframe,
                defaults={
                    'earliest_date': start,
                    'latest_date': end,
                    'total_records': total,
                    'is_complete': total > 0,
                }
            )
        except Exception as e:
            logger.error(f"Failed to update range tracking for {symbol.symbol} {timeframe}: {e}")

    def check_data_quality(self, symbol: Symbol, timeframe: str = '1h', days_back: int = 90) -> Dict:
        """Check data quality and detect gaps for a symbol/timeframe."""
        try:
            from apps.data.models import DataQuality
            from django.utils import timezone
            from datetime import timedelta
            
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Calculate expected records based on timeframe
            timeframe_minutes = {
                '1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440
            }
            
            minutes_per_record = timeframe_minutes.get(timeframe, 60)
            total_minutes = int((end_date - start_date).total_seconds() / 60)
            expected_records = total_minutes // minutes_per_record
            
            # Count actual records
            actual_records = MarketData.objects.filter(
                symbol=symbol,
                timeframe=timeframe,
                timestamp__gte=start_date,
                timestamp__lt=end_date
            ).count()
            
            missing_records = max(0, expected_records - actual_records)
            completeness_percentage = (actual_records / expected_records * 100) if expected_records > 0 else 0
            
            # Check for gaps (simplified - look for missing hours)
            has_gaps = missing_records > (expected_records * 0.01)  # More than 1% missing
            
            # Store quality metrics
            DataQuality.objects.create(
                symbol=symbol,
                timeframe=timeframe,
                date_range_start=start_date,
                date_range_end=end_date,
                total_expected_records=expected_records,
                total_actual_records=actual_records,
                missing_records=missing_records,
                completeness_percentage=completeness_percentage,
                has_gaps=has_gaps,
                has_anomalies=False,  # Simplified for now
            )
            
            return {
                'completeness_percentage': completeness_percentage,
                'expected_records': expected_records,
                'actual_records': actual_records,
                'missing_records': missing_records,
                'gaps_count': missing_records,
                'has_gaps': has_gaps,
                'date_range': f"{start_date.date()} to {end_date.date()}"
            }
            
        except Exception as e:
            logger.error(f"Error checking data quality for {symbol.symbol} {timeframe}: {e}")
            return {
                'completeness_percentage': 0,
                'expected_records': 0,
                'actual_records': 0,
                'missing_records': 0,
                'gaps_count': 0,
                'has_gaps': True,
                'error': str(e)
            }

    def fill_data_gaps(self, symbol: Symbol, timeframe: str = '1h') -> bool:
        """Fill detected gaps in historical data."""
        try:
            # Get the latest data range
            range_obj = HistoricalDataRange.objects.filter(
                symbol=symbol, timeframe=timeframe
            ).first()
            
            if not range_obj:
                logger.warning(f"No data range found for {symbol.symbol} {timeframe}")
                return False
            
            # Fetch last 7 days to fill any recent gaps
            end_date = timezone.now()
            start_date = end_date - timedelta(days=7)
            
            logger.info(f"Filling gaps for {symbol.symbol} {timeframe} from {start_date.date()} to {end_date.date()}")
            
            # Use existing fetch method to get recent data
            success = self.fetch_complete_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start=start_date,
                end=end_date
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error filling data gaps for {symbol.symbol} {timeframe}: {e}")
            return False


def get_historical_data_manager() -> HistoricalDataManager:
    return HistoricalDataManager()



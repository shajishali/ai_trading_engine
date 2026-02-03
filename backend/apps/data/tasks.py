from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from .models import DataSyncLog, Symbol, MarketData, TechnicalIndicator
from .historical_data_manager import HistoricalDataManager
from .services import CryptoDataIngestionService, TechnicalAnalysisService

logger = logging.getLogger(__name__)


@shared_task
def update_crypto_prices():
    """Update crypto prices from external APIs every 30 minutes"""
    try:
        logger.info("Starting crypto price update...")
        
        # Use the historical data manager to fetch latest data
        manager = HistoricalDataManager()
        symbols = Symbol.objects.filter(symbol_type='CRYPTO', is_active=True)
        
        success_count = 0
        
        for symbol in symbols:
            try:
                # Fetch the last 30 minutes of data
                end_time = timezone.now()
                start_time = end_time - timedelta(minutes=30)
                
                # Update 1H timeframe data
                if manager.fetch_complete_historical_data(symbol, timeframe='1h', start=start_time, end=end_time):
                    success_count += 1
                    logger.debug(f"Updated prices for {symbol.symbol}")
                    
            except Exception as e:
                logger.error(f"Error updating prices for {symbol.symbol}: {e}")
        
        logger.info(f"Price update completed: {success_count}/{symbols.count()} symbols updated")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Error in update_crypto_prices task: {e}")
        return False


@shared_task
def sync_crypto_symbols_task():
    """Celery task to sync crypto symbols"""
    try:
        service = CryptoDataIngestionService()
        success = service.sync_crypto_symbols()
        
        # Log the sync operation
        DataSyncLog.objects.create(
            source=service.data_source,
            sync_type='SYMBOLS',
            status='SUCCESS' if success else 'FAILED',
            start_time=timezone.now() - timedelta(minutes=5),
            end_time=timezone.now(),
            records_processed=Symbol.objects.filter(symbol_type='CRYPTO').count()
        )
        
        return success
    except Exception as e:
        logger.error(f"Error in sync_crypto_symbols_task: {e}")
        
        # Log the failed sync
        DataSyncLog.objects.create(
            source=service.data_source,
            sync_type='SYMBOLS',
            status='FAILED',
            start_time=timezone.now() - timedelta(minutes=5),
            end_time=timezone.now(),
            error_message=str(e)
        )
        
        return False


@shared_task
def sync_market_data_task():
    """Celery task to sync market data for all active crypto symbols"""
    try:
        service = CryptoDataIngestionService()
        symbols = Symbol.objects.filter(symbol_type='CRYPTO', is_active=True)
        
        success_count = 0
        total_count = len(symbols)
        
        for symbol in symbols:
            try:
                if service.sync_market_data(symbol):
                    success_count += 1
            except Exception as e:
                logger.error(f"Error syncing market data for {symbol.symbol}: {e}")
        
        # Log the sync operation
        DataSyncLog.objects.create(
            source=service.data_source,
            sync_type='MARKET_DATA',
            status='SUCCESS' if success_count > 0 else 'FAILED',
            start_time=timezone.now() - timedelta(minutes=10),
            end_time=timezone.now(),
            records_processed=success_count,
            total_records=total_count
        )
        
        return success_count > 0
    except Exception as e:
        logger.error(f"Error in sync_market_data_task: {e}")
        return False


@shared_task
def calculate_technical_indicators_task():
    """Celery task to calculate technical indicators for all active symbols"""
    try:
        service = TechnicalAnalysisService()
        symbols = Symbol.objects.filter(symbol_type='CRYPTO', is_active=True)
        
        success_count = 0
        total_count = len(symbols)
        
        for symbol in symbols:
            try:
                if service.calculate_all_indicators(symbol):
                    success_count += 1
            except Exception as e:
                logger.error(f"Error calculating indicators for {symbol.symbol}: {e}")
        
        # Log the sync operation
        DataSyncLog.objects.create(
            source=service.data_source,
            sync_type='TECHNICAL_INDICATORS',
            status='SUCCESS' if success_count > 0 else 'FAILED',
            start_time=timezone.now() - timedelta(minutes=5),
            end_time=timezone.now(),
            records_processed=success_count,
            total_records=total_count
        )
        
        return success_count > 0
    except Exception as e:
        logger.error(f"Error in calculate_technical_indicators_task: {e}")
        return False


@shared_task
def cleanup_old_data_task():
    """Celery task to cleanup old market data and indicators - DISABLED to preserve all historical data from 2020"""
    try:
        # DISABLED: Preserve all historical data from 2020 to yesterday
        # This ensures complete backtesting data coverage without data loss
        
        logger.info("Data cleanup task called but DISABLED to preserve all historical data from 2020")
        logger.info("All historical data from 2020 to yesterday will be preserved for backtesting")
        
        # Return success without deleting any data
        return True
        
        # ORIGINAL CLEANUP CODE (DISABLED):
        # # Retention by timeframe
        # cutoff_1m = timezone.now() - timedelta(days=365)
        # cutoff_1h = timezone.now() - timedelta(days=730)
        # cutoff_1d = timezone.now() - timedelta(days=1825)
        #
        # old_1m = MarketData.objects.filter(timestamp__lt=cutoff_1m, timeframe='1m')
        # old_1h = MarketData.objects.filter(timestamp__lt=cutoff_1h, timeframe='1h')
        # old_1d = MarketData.objects.filter(timestamp__lt=cutoff_1d, timeframe='1d')
        #
        # market_data_deleted = old_1m.count() + old_1h.count() + old_1d.count()
        #
        # old_1m.delete()
        # old_1h.delete()
        # old_1d.delete()
        #
        # # Indicators: keep 2 years
        # cutoff_ind = timezone.now() - timedelta(days=730)
        # old_indicators = TechnicalIndicator.objects.filter(timestamp__lt=cutoff_ind)
        # indicators_deleted = old_indicators.count()
        # old_indicators.delete()
        # 
        # logger.info(f"Cleaned up {market_data_deleted} old market data records and {indicators_deleted} old indicators")
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_data_task: {e}")
        return False


@shared_task
def update_historical_data_task():
    """Hourly incremental update for historical data (last 1 hour)."""
    try:
        manager = HistoricalDataManager()
        symbols = Symbol.objects.filter(symbol_type='CRYPTO', is_active=True)
        success = 0
        
        # Calculate time range: from 1 hour ago to 1 hour before current time
        # This ensures we always have data up to 1 hour before current time
        end_time = timezone.now() - timedelta(hours=1)  # 1 hour before current time
        start_time = end_time - timedelta(hours=1)     # 1 hour window
        
        logger.info(f"Hourly update: fetching data from {start_time} to {end_time}")
        
        for sym in symbols:
            try:
                if manager.fetch_complete_historical_data(sym, timeframe='1h', start=start_time, end=end_time):
                    success += 1
            except Exception as e:
                logger.error(f"Incremental update failed for {sym.symbol}: {e}")
        
        logger.info(f"Hourly incremental updates completed for {success}/{symbols.count()} symbols")
        return True
    except Exception as e:
        logger.error(f"Error in update_historical_data_task: {e}")
        return False


@shared_task
def update_historical_data_daily_task():
    """Daily comprehensive update for historical data (last 2 days) - backup task."""
    try:
        manager = HistoricalDataManager()
        symbols = Symbol.objects.filter(symbol_type='CRYPTO', is_active=True)
        success = 0
        
        # Daily backup: fetch last 2 days to ensure no gaps
        end_time = timezone.now() - timedelta(hours=1)  # Still 1 hour before current time
        start_time = end_time - timedelta(days=2)       # 2 days window
        
        logger.info(f"Daily backup update: fetching data from {start_time} to {end_time}")
        
        for sym in symbols:
            try:
                if manager.fetch_complete_historical_data(sym, timeframe='1h', start=start_time, end=end_time):
                    success += 1
            except Exception as e:
                logger.error(f"Daily backup update failed for {sym.symbol}: {e}")
        
        logger.info(f"Daily backup updates completed for {success}/{symbols.count()} symbols")
        return True
    except Exception as e:
        logger.error(f"Error in update_historical_data_daily_task: {e}")
        return False


@shared_task
def weekly_gap_check_and_fill_task():
    """Weekly task: check last 90 days for gaps and fill them."""
    try:
        manager = HistoricalDataManager()
        symbols = Symbol.objects.filter(symbol_type='CRYPTO', is_active=True)[:50]
        for sym in symbols:
            report = manager.check_data_quality(sym, timeframe='1h', days_back=90)
            if report.get('has_gaps'):
                manager.fill_data_gaps(sym, timeframe='1h')
        logger.info("Weekly gap check/fill completed")
        return True
    except Exception as e:
        logger.error(f"Error in weekly_gap_check_and_fill_task: {e}")
        return False


@shared_task
def health_check_task():
    """Celery task to perform system health check"""
    try:
        # Check data freshness
        latest_data = MarketData.objects.order_by('-timestamp').first()
        if latest_data:
            data_age = timezone.now() - latest_data.timestamp
            if data_age > timedelta(hours=1):
                logger.warning(f"Market data is {data_age} old")
        
        # Check symbol count
        symbol_count = Symbol.objects.filter(symbol_type='CRYPTO', is_active=True).count()
        if symbol_count < 50:
            logger.warning(f"Only {symbol_count} active crypto symbols found")
        
        # Check recent sync logs
        recent_syncs = DataSyncLog.objects.filter(
            end_time__gte=timezone.now() - timedelta(hours=1)
        )
        
        failed_syncs = recent_syncs.filter(status='FAILED')
        if failed_syncs.exists():
            logger.warning(f"Found {failed_syncs.count()} failed syncs in the last hour")
        
        return True
    except Exception as e:
        logger.error(f"Error in health_check_task: {e}")
        return False


@shared_task
def upload_file_to_s3_task(file_path: str, s3_key: str):
    """Upload a file to S3 bucket"""
    try:
        from django.core.files.storage import default_storage
        
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {'status': 'error', 'error': 'File not found'}
        
        with open(file_path, 'rb') as f:
            default_storage.save(s3_key, f)
        
        logger.info(f"Successfully uploaded {file_path} to S3 as {s3_key}")
        return {'status': 'success', 's3_key': s3_key}
        
    except Exception as e:
        logger.error(f"Error uploading file to S3: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task
def download_file_from_s3_task(s3_key: str, local_path: str):
    """Download a file from S3 bucket"""
    try:
        from django.core.files.storage import default_storage
        
        if not default_storage.exists(s3_key):
            logger.error(f"File not found in S3: {s3_key}")
            return {'status': 'error', 'error': 'File not found in S3'}
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Download file
        with default_storage.open(s3_key, 'rb') as s3_file:
            with open(local_path, 'wb') as local_file:
                local_file.write(s3_file.read())
        
        logger.info(f"Successfully downloaded {s3_key} from S3 to {local_path}")
        return {'status': 'success', 'local_path': local_path}
        
    except Exception as e:
        logger.error(f"Error downloading file from S3: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task
def migrate_local_files_to_s3_task():
    """Migrate existing local files to S3"""
    try:
        from django.core.files.storage import default_storage
        from django.conf import settings
        
        migrated_count = 0
        error_count = 0
        
        # Migrate media files
        if hasattr(settings, 'MEDIA_ROOT') and settings.MEDIA_ROOT:
            media_root = settings.MEDIA_ROOT
            if os.path.exists(media_root):
                for root, dirs, files in os.walk(media_root):
                    for file in files:
                        try:
                            local_path = os.path.join(root, file)
                            relative_path = os.path.relpath(local_path, media_root)
                            s3_key = f'media/{relative_path}'
                            
                            # Check if file already exists in S3
                            if not default_storage.exists(s3_key):
                                with open(local_path, 'rb') as f:
                                    default_storage.save(s3_key, f)
                                migrated_count += 1
                                logger.info(f"Migrated {local_path} to S3")
                            
                        except Exception as e:
                            error_count += 1
                            logger.error(f"Error migrating {local_path}: {e}")
        
        # Migrate static files
        if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
            static_root = settings.STATIC_ROOT
            if os.path.exists(static_root):
                for root, dirs, files in os.walk(static_root):
                    for file in files:
                        try:
                            local_path = os.path.join(root, file)
                            relative_path = os.path.relpath(local_path, static_root)
                            s3_key = f'static/{relative_path}'
                            
                            # Check if file already exists in S3
                            if not default_storage.exists(s3_key):
                                with open(local_path, 'rb') as f:
                                    default_storage.save(s3_key, f)
                                migrated_count += 1
                                logger.info(f"Migrated {local_path} to S3")
                            
                        except Exception as e:
                            error_count += 1
                            logger.error(f"Error migrating {local_path}: {e}")
        
        logger.info(f"Migration completed. Migrated: {migrated_count}, Errors: {error_count}")
        return {
            'status': 'success',
            'migrated_count': migrated_count,
            'error_count': error_count
        }
        
    except Exception as e:
        logger.error(f"Error in migrate_local_files_to_s3_task: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task
def cleanup_s3_files_task():
    """Clean up old files from S3"""
    try:
        from django.core.files.storage import default_storage
        from datetime import datetime, timedelta
        
        # Clean up old model files (keep only last 10 versions)
        model_files = []
        try:
            # List files in models directory
            for file_info in default_storage.listdir('models')[1]:  # [1] gets files
                if file_info.endswith('.h5') or file_info.endswith('.tflite'):
                    model_files.append(file_info)
            
            # Sort by modification time and keep only recent ones
            model_files.sort(reverse=True)
            files_to_delete = model_files[10:]  # Keep only 10 most recent
            
            for file_name in files_to_delete:
                s3_key = f'models/{file_name}'
                default_storage.delete(s3_key)
                logger.info(f"Deleted old model file: {s3_key}")
                
        except Exception as e:
            logger.error(f"Error cleaning up model files: {e}")
        
        # Clean up old media files (older than 30 days)
        cutoff_date = datetime.now() - timedelta(days=30)
        try:
            for file_info in default_storage.listdir('media')[1]:  # [1] gets files
                # This is a simplified cleanup - in production you'd want more sophisticated logic
                if 'temp' in file_info.lower() or 'cache' in file_info.lower():
                    s3_key = f'media/{file_info}'
                    default_storage.delete(s3_key)
                    logger.info(f"Deleted temporary file: {s3_key}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up media files: {e}")
        
        logger.info("S3 cleanup completed")
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Error in cleanup_s3_files_task: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task
def fetch_and_store_coins_task(max_coins=None):
    """Celery task to fetch and store ALL coins from CoinGecko API automatically"""
    import requests
    import time
    from decimal import Decimal
    from apps.trading.models import Symbol
    
    try:
        if max_coins:
            logger.info(f"Starting fetch_and_store_coins task - fetching coins (up to {max_coins})")
        else:
            logger.info(f"Starting fetch_and_store_coins task - fetching ALL coins (no limit)")
        
        # Fetch all coins from CoinGecko API
        all_coins = []
        page = 1
        per_page = 250  # Maximum per page for CoinGecko API
        
        while True:  # Continue until no more coins
            try:
                url = "https://api.coingecko.com/api/v3/coins/markets"
                params = {
                    'vs_currency': 'usd',
                    'order': 'market_cap_desc',
                    'per_page': per_page,
                    'page': page,
                    'sparkline': False
                }
                
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                coins = response.json()
                
                if not coins or len(coins) == 0:
                    break
                
                all_coins.extend(coins)
                logger.info(f"Fetched page {page}: {len(coins)} coins (Total: {len(all_coins)})")
                
                # If we got less than per_page, we've reached the end
                if len(coins) < per_page:
                    break
                
                # Check if we've reached the limit (if specified)
                if max_coins and len(all_coins) >= max_coins:
                    break
                
                page += 1
                # Add delay to avoid rate limiting (CoinGecko: 10-50 calls/minute)
                time.sleep(0.6)
            
            except requests.exceptions.RequestException as e:
                logger.error(f"API Error on page {page}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error fetching page {page}: {e}")
                break
        
        # Apply limit only if specified
        if max_coins:
            coins_to_process = all_coins[:max_coins]
        else:
            coins_to_process = all_coins
        logger.info(f"Total coins fetched: {len(coins_to_process)}")
        
        # Store coins in database
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for coin in coins_to_process:
            try:
                # Validate and clean symbol code
                symbol_code = coin.get('symbol', '').strip().upper()
                if not symbol_code or len(symbol_code) > 20:
                    error_count += 1
                    logger.warning(f"Invalid symbol: {coin.get('symbol', 'unknown')}")
                    continue
                
                # Validate and clean coin name (truncate if too long)
                coin_name = coin.get('name', symbol_code)
                if coin_name:
                    coin_name = coin_name.strip()[:100]  # Truncate to max 100 chars
                else:
                    coin_name = symbol_code
                
                # Get market cap rank (handle None)
                market_cap_rank = coin.get('market_cap_rank')
                if market_cap_rank is not None and (market_cap_rank < 0 or market_cap_rank > 100000):
                    market_cap_rank = None
                
                # Try to get existing symbol
                try:
                    symbol = Symbol.objects.get(symbol=symbol_code)
                    # Update existing symbol
                    updated = False
                    if symbol.name != coin_name:
                        symbol.name = coin_name
                        updated = True
                    if not symbol.is_active:
                        symbol.is_active = True
                        updated = True
                    if not symbol.is_crypto_symbol:
                        symbol.is_crypto_symbol = True
                        updated = True
                    if not symbol.is_spot_tradable:
                        symbol.is_spot_tradable = True
                        updated = True
                    if symbol.market_cap_rank != market_cap_rank:
                        symbol.market_cap_rank = market_cap_rank
                        updated = True
                    
                    if updated:
                        symbol.save()
                        updated_count += 1
                        logger.debug(f"Updated: {symbol_code} - {coin_name}")
                
                except Symbol.DoesNotExist:
                    # Create new symbol
                    try:
                        symbol = Symbol.objects.create(
                            symbol=symbol_code,
                            name=coin_name,
                            symbol_type='CRYPTO',
                            exchange='CoinGecko',
                            is_active=True,
                            is_crypto_symbol=True,
                            is_spot_tradable=True,
                            market_cap_rank=market_cap_rank,
                        )
                        created_count += 1
                        logger.debug(f"Created: {symbol_code} - {coin_name}")
                    except Exception as create_error:
                        # Handle unique constraint or other database errors
                        error_count += 1
                        logger.warning(f"Failed to create {symbol_code}: {create_error}")
                        continue
                
                except Symbol.MultipleObjectsReturned:
                    # Handle duplicate symbols (shouldn't happen but just in case)
                    error_count += 1
                    logger.warning(f"Multiple symbols found for {symbol_code}")
                    continue
            
            except Exception as e:
                error_count += 1
                coin_symbol = coin.get('symbol', 'unknown')
                logger.warning(f"Error processing coin {coin_symbol}: {e}", exc_info=True)
                continue
        
        result = {
            'status': 'success',
            'created': created_count,
            'updated': updated_count,
            'errors': error_count,
            'total_processed': len(coins_to_process),
            'total_fetched': len(all_coins)
        }
        
        logger.info(
            f"fetch_and_store_coins_task completed: "
            f"Created={created_count}, Updated={updated_count}, "
            f"Errors={error_count}, Total={len(coins_to_process)}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in fetch_and_store_coins_task: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


@shared_task
def sync_binance_futures_symbols_task(deactivate_non_futures: bool = True, force_refresh: bool = False):
    """
    Sync DB symbols so ONLY Binance USDT perpetual futures base-assets are active crypto symbols.

    This is the source of truth for which coins are eligible for signal generation.
    """
    from apps.trading.binance_futures_service import sync_binance_futures_symbols

    return sync_binance_futures_symbols(
        deactivate_non_futures=deactivate_non_futures,
        force_refresh=force_refresh,
    )


@shared_task
def load_binance_futures_market_data_task(
    days: int = 90,
    max_symbols_per_run: int = 30,
    timeframes: tuple = ('1h', '4h', '1d'),
):
    """
    Sync Binance futures symbols and fill market data for signal generation.
    Runs on a schedule; each run processes up to max_symbols_per_run coins (prioritizing
    those with no or oldest data). Over multiple runs, all coins get data.

    Call from Celery Beat (e.g. every 2 hours) until all records are stored.
    """
    from django.db.models import Min, Max
    from apps.trading.models import Symbol
    from apps.trading.binance_futures_service import (
        sync_binance_futures_symbols,
        get_binance_usdt_futures_base_assets,
    )
    from .models import MarketData, HistoricalDataRange
    from .historical_data_manager import get_historical_data_manager

    logger.info("[Binance Futures Data] Starting: sync symbols + load market data batch.")

    # Step 1: Sync symbol list from Binance
    try:
        result = sync_binance_futures_symbols(
            deactivate_non_futures=True,
            force_refresh=True,
        )
        if result.get('status') != 'success':
            logger.warning(f"[Binance Futures Data] Sync failed: {result.get('error')}")
            return {'status': 'error', 'error': result.get('error'), 'synced': 0, 'filled': 0}
    except Exception as e:
        logger.exception(f"[Binance Futures Data] Sync error: {e}")
        return {'status': 'error', 'error': str(e), 'synced': 0, 'filled': 0}

    valid = get_binance_usdt_futures_base_assets(force_refresh=True)
    symbols_qs = Symbol.objects.filter(
        symbol_type='CRYPTO',
        is_active=True,
        is_crypto_symbol=True,
    )
    if valid:
        symbols_qs = symbols_qs.filter(symbol__in=valid)

    # Step 2: Pick symbols that need data most (no data or oldest latest_date)
    # Subquery: latest MarketData timestamp per symbol for 1h
    from django.db.models import OuterRef, Subquery
    latest_1h = MarketData.objects.filter(
        symbol=OuterRef('pk'),
        timeframe='1h',
    ).order_by('-timestamp')
    symbols_with_latest = symbols_qs.annotate(
        latest_ts=Subquery(latest_1h.values('timestamp')[:1]),
    ).order_by('latest_ts')  # nulls first in Django (ASC nulls first)
    to_process = list(symbols_with_latest[:max_symbols_per_run])
    if not to_process:
        logger.info("[Binance Futures Data] No symbols to process.")
        return {'status': 'ok', 'synced': 1, 'filled': 0, 'message': 'no symbols to process'}

    # Step 3: Fetch market data for each
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    manager = get_historical_data_manager()
    timeframes_list = list(timeframes)
    ok = 0
    fail = 0
    for symbol in to_process:
        symbol_ok = False
        for tf in timeframes_list:
            try:
                if manager.fetch_complete_historical_data(
                    symbol, timeframe=tf, start=start_date, end=end_date
                ):
                    symbol_ok = True
            except Exception as e:
                logger.warning(f"[Binance Futures Data] {symbol.symbol} {tf}: {e}")
        if symbol_ok:
            ok += 1
        else:
            fail += 1

    logger.info(
        f"[Binance Futures Data] Done. Processed {len(to_process)} symbols: ok={ok}, fail={fail}"
    )
    return {
        'status': 'ok',
        'synced': 1,
        'filled': ok,
        'failed': fail,
        'total_processed': len(to_process),
    }





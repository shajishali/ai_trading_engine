"""
Backtesting API Views
Handles coin name input, date period selection, and signal generation based on strategy
"""

import json
import logging
import csv
import io
import zipfile
import base64
from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.trading.models import Symbol
from apps.signals.models import TradingSignal, SignalType
from apps.analytics.models import BacktestResult
from apps.data.models import MarketData
from django.db.models import Min, Max, Avg

logger = logging.getLogger(__name__)


class BacktestAPIView(View):
    """Main backtesting API endpoint"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        """Handle backtesting requests"""
        try:
            # Handle both form data and JSON data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                # Handle form data
                data = request.POST
            
            # Clean up data - remove None and empty string values
            cleaned_data = {}
            for key, value in data.items():
                if value is not None and value != '' and value != 'null':
                    cleaned_data[key] = value
            data = cleaned_data
            
            # Extract parameters with safe defaults
            symbol_str = data.get('symbol', 'BTC')
            if symbol_str:
                symbol_str = symbol_str.upper()
            else:
                symbol_str = 'BTC'
            
            start_date_str = data.get('start_date')
            end_date_str = data.get('end_date')
            action = data.get('action', 'generate_signals')
            
            # Parse dates and make timezone-aware
            from django.utils import timezone as tz
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                if start_date.tzinfo is None:
                    start_date = tz.make_aware(start_date)
            else:
                start_date = tz.now() - timedelta(days=365)
            
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                # Set to end of day
                end_date = end_date.replace(hour=23, minute=59, second=59)
                if end_date.tzinfo is None:
                    end_date = tz.make_aware(end_date)
            else:
                end_date = tz.now()
            
            # Get or create symbol
            symbol = self._get_or_create_symbol(symbol_str)
            
            if action == 'generate_signals':
                return self._generate_historical_signals(request, symbol, start_date, end_date)
            elif action == 'backtest':
                return self._run_backtest(request, symbol, start_date, end_date)
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'})
                
        except Exception as e:
            logger.error(f"Backtesting API error: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    def _get_or_create_symbol(self, symbol_str: str) -> Symbol:
        """Get or create symbol object"""
        try:
            symbol, created = Symbol.objects.get_or_create(
                symbol=symbol_str,
                defaults={
                    'name': f'{symbol_str} Trading Pair',
                    'symbol_type': 'CRYPTO',
                    'is_crypto_symbol': True,
                    'is_spot_tradable': True,
                    'is_active': True
                }
            )
            return symbol
        except Exception as e:
            logger.error(f"Error getting/creating symbol {symbol_str}: {e}")
            raise

    def _normalize_signal_prices(self, signal: dict) -> None:
        """Ensure SELL has target < entry < stop; BUY has stop < entry < target. Mutates signal in place."""
        try:
            stype = (signal.get('signal_type') or '').upper()
            
            # Safe float conversion with None handling
            def safe_float(value, default=0.0):
                if value is None or value == '' or value == 'null':
                    return default
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return default
            
            entry = safe_float(signal.get('entry_price'), 0)
            target = safe_float(signal.get('target_price'), 0)
            stop = safe_float(signal.get('stop_loss'), 0)
            if entry <= 0:
                return
            is_sell = 'SELL' in stype or 'STRONG_SELL' in stype
            if is_sell:
                if target >= entry or stop <= entry:
                    signal['target_price'] = entry * 0.85
                    signal['stop_loss'] = entry * 1.08
                    risk = signal['stop_loss'] - entry
                    reward = entry - signal['target_price']
                    signal['risk_reward_ratio'] = reward / risk if risk > 0 else 0.0
            else:
                if stop >= entry or target <= entry:
                    signal['stop_loss'] = entry * 0.92
                    signal['target_price'] = entry * 1.15
                    risk = entry - signal['stop_loss']
                    reward = signal['target_price'] - entry
                    signal['risk_reward_ratio'] = reward / risk if risk > 0 else 0.0
        except (TypeError, ValueError, KeyError):
            pass

    def _backtest_strategy_details(self, leverage):
        """Strategy details for API response; when leverage=10 use mandatory 50% TP / 25% SL of capital."""
        try:
            from apps.signals.risk_constants import (
                LEVERAGE_10X,
                TAKE_PROFIT_CAPITAL_PERCENT,
                STOP_LOSS_CAPITAL_PERCENT,
                TAKE_PROFIT_PRICE_PERCENT_10X,
                STOP_LOSS_PRICE_PERCENT_10X,
            )
            if leverage == LEVERAGE_10X:
                return {
                    'leverage': LEVERAGE_10X,
                    'take_profit_capital_percent': TAKE_PROFIT_CAPITAL_PERCENT,
                    'stop_loss_capital_percent': STOP_LOSS_CAPITAL_PERCENT,
                    'take_profit_percentage': TAKE_PROFIT_PRICE_PERCENT_10X,
                    'stop_loss_percentage': STOP_LOSS_PRICE_PERCENT_10X,
                    'min_risk_reward_ratio': 1.5,
                    'rsi_buy_range': [20, 50],
                    'rsi_sell_range': [50, 80],
                    'volume_threshold': 1.2,
                }
        except ImportError:
            pass
        return {
            'take_profit_percentage': 15.0,
            'stop_loss_percentage': 8.0,
            'min_risk_reward_ratio': 1.5,
            'rsi_buy_range': [20, 50],
            'rsi_sell_range': [50, 80],
            'volume_threshold': 1.2,
        }

    def _generate_historical_signals(self, request, symbol, start_date, end_date):
        """Generate historical signals for the given period using YOUR actual strategy"""
        try:
            # Make dates timezone-aware if they aren't already
            from django.utils import timezone
            if start_date.tzinfo is None:
                start_date = timezone.make_aware(start_date)
            if end_date.tzinfo is None:
                end_date = timezone.make_aware(end_date)
            
            # Get user-specified signal count (safe parsing; blank => 0)
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            raw_count = data.get('desired_signal_count')
            try:
                desired_signal_count = int(raw_count) if raw_count not in (None, '', 'null') else 0
            except (TypeError, ValueError):
                desired_signal_count = 0
            # Clamp to valid range 0..100
            if desired_signal_count < 0:
                desired_signal_count = 0
            if desired_signal_count > 100:
                desired_signal_count = 100
            
            # Optional leverage: when 10, use mandatory 50% profit / 25% stop loss of capital
            raw_leverage = data.get('leverage') or data.get('leverage_multiplier')
            try:
                leverage = int(raw_leverage) if raw_leverage not in (None, '', 'null') else None
            except (TypeError, ValueError):
                leverage = None
            
            # First, check if signals already exist in database for this period
            existing_signals = TradingSignal.objects.filter(
                symbol=symbol,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).order_by('created_at')
            
            if existing_signals.exists():
                logger.info(f"Found {existing_signals.count()} existing signals in database for {symbol.symbol}")
                # Convert database signals to API format and normalize SELL/BUY prices
                formatted_signals = []
                for signal in existing_signals:
                    # Safe float conversion helper
                    def safe_float_db(value, default=0.0):
                        if value is None:
                            return default
                        try:
                            return float(value)
                        except (TypeError, ValueError):
                            return default
                    
                    sig_db = {
                        'id': f"db_{signal.id}",
                        'symbol': str(signal.symbol.symbol),
                        'signal_type': str(signal.signal_type.name if signal.signal_type else 'N/A'),
                        'strength': str(signal.strength),
                        'confidence_score': safe_float_db(signal.confidence_score, 0.5),
                        'entry_price': safe_float_db(signal.entry_price, 0),
                        'target_price': safe_float_db(signal.target_price, 0),
                        'stop_loss': safe_float_db(signal.stop_loss, 0),
                        'risk_reward_ratio': safe_float_db(signal.risk_reward_ratio, 0),
                        'timeframe': str(signal.timeframe or '1D'),
                        'quality_score': safe_float_db(signal.quality_score, 0),
                        'created_at': signal.created_at.isoformat(),
                        'is_executed': False,
                        'executed_at': None,
                        'strategy_confirmations': int(signal.metadata.get('confirmations', 0) if signal.metadata else 0),
                        'strategy_details': signal.metadata or {}
                    }
                    self._normalize_signal_prices(sig_db)
                    formatted_signals.append(sig_db)
                
                logger.info(f"Returning {len(formatted_signals)} cached signals from database")
                
                # PHASE 2: Analyze existing signals
                signal_analysis = None
                if formatted_signals:
                    try:
                        signal_analysis = self._analyze_generated_signals(symbol, start_date, end_date)
                        logger.info(f"Analysis completed for existing signals: {signal_analysis['total_summary']['total_signals']} signals analyzed")
                    except Exception as e:
                        logger.error(f"Error analyzing existing signals for {symbol.symbol}: {e}")
                        signal_analysis = None
                
                # Prepare response data
                response_data = {
                    'success': True,
                    'action': 'generate_signals',
                    'signals': formatted_signals,
                    'total_signals': len(formatted_signals),
                    'symbol': symbol.symbol,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'strategy_used': 'YOUR_ACTUAL_STRATEGY',
                    'source': 'database_cache',
                    'strategy_details': self._backtest_strategy_details(leverage),
                    'leverage': leverage
                }
                
                # Add signal count analysis and filtering
                max_possible_signals = len(formatted_signals)
                
                # Filter to best signals if count is specified
                if desired_signal_count > 0 and max_possible_signals > desired_signal_count:
                    formatted_signals = self._select_best_signals_by_count(
                        formatted_signals, desired_signal_count
                    )
                
                # Simulate signal execution for backtesting
                executed_signals = self._simulate_signal_execution(formatted_signals, symbol, start_date, end_date)
                
                # Generate summarizing results
                summarizing_results = self._generate_summarizing_results(
                    executed_signals, symbol, start_date, end_date
                )
                
                # PHASE 2: Add analysis results to response
                if executed_signals:
                    try:
                        signal_analysis = self._analyze_executed_signals(executed_signals, symbol, start_date, end_date)
                        response_data['signal_analysis'] = signal_analysis
                        logger.info(f"Added signal analysis to response for existing signals")
                    except Exception as e:
                        logger.error(f"Error analyzing existing signals: {e}")
                
                # Add new fields to response
                response_data.update({
                    'max_possible_signals': max_possible_signals,
                    'desired_signal_count': desired_signal_count,
                    'summarizing_results': summarizing_results,
                    'signals': executed_signals,
                    'total_signals': len(executed_signals)
                })
                
                return JsonResponse(response_data)
            
            # No existing signals found, generate new ones
            logger.info(f"No existing signals found for {symbol.symbol}, generating new ones")
            
            # Import the new strategy-based backtesting service
            from apps.signals.strategy_backtesting_service import StrategyBacktestingService
            
            # Create strategy backtesting service (leverage=10 => mandatory 50% TP / 25% SL of capital)
            strategy_service = StrategyBacktestingService(leverage=leverage)
            
            # Generate signals based on YOUR actual strategy
            signals = strategy_service.generate_historical_signals(symbol, start_date, end_date)
            
            # Convert signals to the required format (safe float to avoid NoneType)
            def _safe_float(v, default=0.0):
                if v is None:
                    return default
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return default

            formatted_signals = []
            for signal in signals:
                sig = {
                    'id': signal.get('id', f"strategy_{hash(signal['created_at'])}"),
                    'symbol': str(signal.get('symbol', '')),
                    'signal_type': str(signal.get('signal_type', '')),
                    'strength': str(signal.get('strength', '')),
                    'confidence_score': _safe_float(signal.get('confidence_score'), 0.5),
                    'entry_price': _safe_float(signal.get('entry_price')),
                    'target_price': _safe_float(signal.get('target_price')),
                    'stop_loss': _safe_float(signal.get('stop_loss')),
                    'risk_reward_ratio': _safe_float(signal.get('risk_reward_ratio'), 0.0),
                    'timeframe': str(signal.get('timeframe', '1D')),
                    'quality_score': _safe_float(signal.get('quality_score'), 0.5),
                    'created_at': str(signal.get('created_at', '')),
                    'is_executed': False,
                    'executed_at': None,
                    'strategy_confirmations': int(signal.get('strategy_confirmations') or 0),
                    'strategy_details': signal.get('strategy_details', {})
                }
                self._normalize_signal_prices(sig)
                formatted_signals.append(sig)
            
            logger.info(f"Generated {len(formatted_signals)} new signals using YOUR strategy for {symbol.symbol}")
            
            # Add signal count analysis and filtering
            max_possible_signals = len(formatted_signals)
            
            # Filter to best signals if count is specified
            if desired_signal_count > 0 and max_possible_signals > desired_signal_count:
                formatted_signals = self._select_best_signals_by_count(
                    formatted_signals, desired_signal_count
                )
            
            # Simulate signal execution for backtesting
            executed_signals = self._simulate_signal_execution(formatted_signals, symbol, start_date, end_date)
            
            # Generate summarizing results
            summarizing_results = self._generate_summarizing_results(
                executed_signals, symbol, start_date, end_date
            )
            
            # PHASE 2: Analyze the generated signals immediately
            signal_analysis = None
            if executed_signals:
                try:
                    signal_analysis = self._analyze_executed_signals(executed_signals, symbol, start_date, end_date)
                    logger.info(f"Analysis completed for {symbol.symbol}: {signal_analysis['total_summary']['total_signals']} signals analyzed")
                except Exception as e:
                    logger.error(f"Error analyzing signals for {symbol.symbol}: {e}")
                    signal_analysis = None
            
            # Check if no signals were generated and provide helpful message
            no_signals_reason = None
            if len(formatted_signals) == 0:
                # Check if it's due to no historical data
                from apps.data.models import MarketData
                data_count = MarketData.objects.filter(
                    symbol=symbol,
                    timestamp__gte=start_date,
                    timestamp__lte=end_date
                ).count()
                
                if data_count == 0:
                    no_signals_reason = f"No historical data available for {symbol.symbol} in the selected date range ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}). Please try a different cryptocurrency or date range."
                else:
                    no_signals_reason = f"Your strategy analyzed {data_count} data points for {symbol.symbol} but found no signals meeting your criteria. This is normal - your strategy is selective and only generates high-quality signals."
            
            # Prepare response data
            response_data = {
                'success': True,
                'action': 'generate_signals',
                'signals': executed_signals,
                'total_signals': len(executed_signals),
                'max_possible_signals': max_possible_signals,
                'desired_signal_count': desired_signal_count,
                'summarizing_results': summarizing_results,
                'symbol': symbol.symbol,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'strategy_used': 'YOUR_ACTUAL_STRATEGY',
                'source': 'newly_generated',
                'no_signals_reason': no_signals_reason,
                'strategy_details': self._backtest_strategy_details(leverage),
                'leverage': leverage,
            }
            
            # PHASE 2: Add analysis results to response
            if signal_analysis:
                response_data['signal_analysis'] = signal_analysis
                logger.info(f"Added signal analysis to response for {symbol.symbol}")
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Error generating historical signals with YOUR strategy: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    def _run_backtest(self, request, symbol, start_date, end_date):
        """Run a full backtest"""
        try:
            # Parse optional leverage (10 => mandatory 50% TP / 25% SL of capital)
            if getattr(request, 'content_type', '') == 'application/json':
                try:
                    data_bt = json.loads(request.body)
                except Exception:
                    data_bt = {}
            else:
                data_bt = getattr(request, 'POST', {})
            raw_lev = data_bt.get('leverage') or data_bt.get('leverage_multiplier')
            try:
                leverage_bt = int(raw_lev) if raw_lev not in (None, '', 'null') else None
            except (TypeError, ValueError):
                leverage_bt = None

            logger.info(f"Running backtest for {symbol.symbol} from {start_date} to {end_date}")
            
            # Get signals in the date range
            signals = TradingSignal.objects.filter(
                symbol=symbol,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).order_by('created_at')
            
            # If no signals exist, generate them first
            if not signals.exists():
                logger.info(f"No signals found for {symbol.symbol} in date range. Generating signals first...")
                
                # Generate signals using the same method as generate_signals action
                try:
                    # Import the strategy backtesting service
                    from apps.signals.strategy_backtesting_service import StrategyBacktestingService
                    
                    # Create strategy backtesting service (leverage=10 => 50% TP / 25% SL of capital)
                    strategy_service = StrategyBacktestingService(leverage=leverage_bt)
                    
                    # Generate signals based on YOUR actual strategy
                    generated_signals = strategy_service.generate_historical_signals(symbol, start_date, end_date)
                    
                    if not generated_signals:
                        logger.warning(f"No signals could be generated for {symbol.symbol} in date range")
                        return JsonResponse({
                            'success': True,
                            'action': 'backtest',
                            'result': {
                                'total_signals': 0,
                                'executed_signals': 0,
                                'expired_signals': 0,
                                'profit_signals': 0,
                                'loss_signals': 0,
                                'not_opened_signals': 0,
                                'total_profit_loss': 0.0,
                                'total_capital_used': 0.0,
                                'win_rate': 0.0,
                                'individual_signals': []
                            }
                        })
                    
                    # Convert generated signals to TradingSignal format for backtesting (safe float)
                    def _safe_float_bt(v, default=0.0):
                        if v is None:
                            return default
                        try:
                            return float(v)
                        except (TypeError, ValueError):
                            return default
                    formatted_signals = []
                    for signal in generated_signals:
                        created_at = signal.get('created_at')
                        if hasattr(created_at, 'isoformat'):
                            created_at_str = created_at.isoformat()
                        elif isinstance(created_at, str):
                            created_at_str = created_at
                        else:
                            created_at_str = str(created_at) if created_at else ''
                        sig_bt = {
                            'id': signal.get('id', f"strategy_{hash(created_at_str)}"),
                            'symbol': str(signal.get('symbol', '')),
                            'signal_type': str(signal.get('signal_type', '')),
                            'strength': str(signal.get('strength', '')),
                            'confidence_score': _safe_float_bt(signal.get('confidence_score'), 0.5),
                            'entry_price': _safe_float_bt(signal.get('entry_price')),
                            'target_price': _safe_float_bt(signal.get('target_price')),
                            'stop_loss': _safe_float_bt(signal.get('stop_loss')),
                            'risk_reward_ratio': _safe_float_bt(signal.get('risk_reward_ratio'), 0.0),
                            'timeframe': str(signal.get('timeframe', '1D')),
                            'quality_score': _safe_float_bt(signal.get('quality_score'), 0.5),
                            'created_at': created_at_str,
                            'is_executed': False,
                            'executed_at': None,
                            'strategy_confirmations': int(signal.get('strategy_confirmations') or 0),
                            'strategy_details': signal.get('strategy_details', {})
                        }
                        self._normalize_signal_prices(sig_bt)
                        formatted_signals.append(sig_bt)
                    
                    logger.info(f"Generated {len(formatted_signals)} signals for backtesting {symbol.symbol}")
                    
                    # Use generated signals for backtesting
                    signals_to_backtest = formatted_signals
                except Exception as e:
                    logger.error(f"Error generating signals for backtest: {e}")
                    return JsonResponse({
                        'success': False,
                        'error': f'Failed to generate signals for backtesting: {str(e)}'
                    })
            else:
                # Convert database signals to format needed for backtesting
                signals_to_backtest = []
                for signal in signals:
                    # Safe float conversion for database signals
                    def safe_float_signal(value, default=0.0):
                        if value is None:
                            return default
                        try:
                            return float(value)
                        except (TypeError, ValueError):
                            return default
                    
                    signals_to_backtest.append({
                        'id': signal.id,
                        'created_at': signal.created_at.isoformat(),
                        'entry_price': str(signal.entry_price) if signal.entry_price is not None else '0',
                        'target_price': str(signal.target_price) if signal.target_price is not None else '0',
                        'stop_loss': str(signal.stop_loss) if signal.stop_loss is not None else '0',
                        'signal_type': signal.signal_type.name if signal.signal_type else 'BUY',
                        'confidence_score': safe_float_signal(signal.confidence_score, 0),
                        'risk_reward_ratio': safe_float_signal(signal.risk_reward_ratio, 0)
                    })
            
            # Get historical data for backtesting
            historical_df = self._get_historical_data(symbol, start_date, end_date)
            
            if historical_df.empty:
                logger.error(f"No historical data found for {symbol.symbol}")
                return JsonResponse({
                    'success': False,
                    'error': f'No historical data available for {symbol.symbol}'
                })
            
            # Convert DataFrame to dict format expected by _simulate_single_signal_execution
            # (timestamp -> {open, high, low, close, volume}) so simulation can check if price hit target/stop
            from django.utils import timezone as tz
            historical_data = {}
            for ts, row in historical_df.iterrows():
                # Ensure timestamp is timezone-aware for comparison with signal_time
                if hasattr(ts, 'to_pydatetime'):
                    ts = ts.to_pydatetime()
                if ts.tzinfo is None:
                    ts = tz.make_aware(ts)
                # Safe float conversion for historical data
                def safe_float_hist(value, default=0.0):
                    if value is None:
                        return default
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        return default
                
                historical_data[ts] = {
                    'open': safe_float_hist(row.get('open'), 0),
                    'high': safe_float_hist(row.get('high'), 0),
                    'low': safe_float_hist(row.get('low'), 0),
                    'close': safe_float_hist(row.get('close'), 0),
                    'volume': safe_float_hist(row.get('volume'), 0)
                }
            logger.info(f"Converted {len(historical_data)} price bars for execution simulation")
            
            # Simulate signal execution for all signals
            executed_signals = []
            for signal_data in signals_to_backtest:
                # signal_data is already in dictionary format
                # Ensure it has all required fields
                # Safe float conversion helper
                def safe_float_exec(value, default=0.0):
                    if value is None or value == '':
                        return default
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        return default
                
                signal_dict = {
                    'id': signal_data.get('id'),
                    'created_at': signal_data.get('created_at'),
                    'entry_price': str(signal_data.get('entry_price', 0)) if signal_data.get('entry_price') is not None else '0',
                    'target_price': str(signal_data.get('target_price', 0)) if signal_data.get('target_price') is not None else '0',
                    'stop_loss': str(signal_data.get('stop_loss', 0)) if signal_data.get('stop_loss') is not None else '0',
                    'signal_type': signal_data.get('signal_type', 'BUY'),
                    'confidence_score': safe_float_exec(signal_data.get('confidence_score'), 0),
                    'risk_reward_ratio': safe_float_exec(signal_data.get('risk_reward_ratio'), 0)
                }
                
                # Simulate execution
                execution_result = self._simulate_single_signal_execution(signal_dict, historical_data, symbol)
                
                # Merge execution result into signal_dict for analysis
                # Include all signals (both executed and not executed) for proper analysis
                signal_dict.update(execution_result)
                executed_signals.append(signal_dict)
            
            # Analyze executed signals
            analysis_result = self._analyze_executed_signals(executed_signals, symbol, start_date, end_date)
            
            # Safe access to total_signals (could be in total_summary or top level)
            total_signals = analysis_result.get('total_signals') or analysis_result.get('total_summary', {}).get('total_signals', 0)
            executed_count = analysis_result.get('executed_signals', 0)
            
            logger.info(f"Backtest completed: {total_signals} signals, {executed_count} executed")
            
            return JsonResponse({
                'success': True,
                'action': 'backtest',
                'result': analysis_result
            })
            
        except Exception as e:
            logger.error(f"Error running backtest: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    def _get_historical_data(self, symbol, start_date, end_date):
        """Get historical market data for backtesting"""
        try:
            from apps.data.models import MarketData
            import pandas as pd
            
            # Get market data for the symbol and timeframe
            market_data = MarketData.objects.filter(
                symbol=symbol,
                timeframe='1d',  # Use daily data (available in database)
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            if not market_data.exists():
                logger.warning(f"No market data found for {symbol.symbol} in date range")
                return pd.DataFrame()
            
            # Convert to DataFrame with safe float conversion
            def safe_float_market(value, default=0.0):
                if value is None:
                    return default
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return default
            
            data = []
            for record in market_data:
                data.append({
                    'timestamp': record.timestamp,
                    'open': safe_float_market(record.open_price, 0),
                    'high': safe_float_market(record.high_price, 0),
                    'low': safe_float_market(record.low_price, 0),
                    'close': safe_float_market(record.close_price, 0),
                    'volume': safe_float_market(record.volume, 0)
                })
            
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"Retrieved {len(df)} historical data points for {symbol.symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol.symbol}: {e}")
            return pd.DataFrame()
    
    def _analyze_generated_signals(self, symbol, start_date, end_date):
        """PHASE 2: Analyze the generated signals using the coin performance analyzer"""
        try:
            from apps.signals.coin_performance_analyzer import CoinPerformanceAnalyzer
            
            # Initialize the analyzer
            analyzer = CoinPerformanceAnalyzer()
            
            # Analyze the signals for this symbol and period
            analysis = analyzer.analyze_coin_signals(symbol, start_date, end_date)
            
            # Get strategy quality rating
            quality_rating = analyzer.get_strategy_quality_rating(analysis)
            
            # Add quality rating to analysis
            analysis['strategy_quality'] = quality_rating
            
            logger.info(f"Signal analysis completed for {symbol.symbol}: {analysis['total_summary']['total_signals']} signals, {analysis['total_summary']['total_profit_percentage']:.2f}% profit")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing signals for {symbol.symbol}: {e}")
            # Return empty analysis on error
            return {
                'symbol': symbol.symbol,
                'symbol_name': symbol.name,
                'analysis_date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'period': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'days': (end_date - start_date).days
                },
                'total_summary': {
                    'total_signals': 0,
                    'profit_signals': 0,
                    'loss_signals': 0,
                    'not_opened_signals': 0,
                    'total_investment': 0,
                    'total_profit_loss': 0,
                    'total_profit_percentage': 0
                },
                'individual_signals': [],
                'strategy_quality': {
                    'quality_score': 0,
                    'quality_rating': 'Error',
                    'recommendation': f'Error analyzing signals: {str(e)}',
                    'metrics': {'profit_rate': 0, 'execution_rate': 0, 'profit_percentage': 0}
                }
            }
    
    def _select_best_signals_by_count(self, signals, count):
        """Select the best N signals based on quality metrics"""
        if not signals or count <= 0:
            return signals
        
        # Sort signals by quality score (confidence * risk_reward_ratio)
        def signal_quality_score(signal):
            confidence = signal.get('confidence_score', 0)
            risk_reward = signal.get('risk_reward_ratio', 1)
            quality_score = signal.get('quality_score', 0)
            return (confidence * 0.4) + (risk_reward * 0.3) + (quality_score * 0.3)
        
        sorted_signals = sorted(signals, key=signal_quality_score, reverse=True)
        return sorted_signals[:count]
    
    def _generate_summarizing_results(self, signals, symbol, start_date, end_date):
        """Generate summarizing results for the selected signals"""
        if not signals:
            return {
                'total_signals': 0,
                'buy_signals': 0,
                'sell_signals': 0,
                'avg_confidence': 0,
                'avg_risk_reward': 0,
                'best_signal': None,
                'signal_distribution': {},
                'quality_breakdown': {}
            }
        
        # Calculate basic statistics
        total_signals = len(signals)
        buy_signals = len([s for s in signals if s.get('signal_type', '').upper() in ['BUY', 'STRONG_BUY']])
        sell_signals = len([s for s in signals if s.get('signal_type', '').upper() in ['SELL', 'STRONG_SELL']])
        
        # Calculate averages
        confidences = [s.get('confidence_score', 0) for s in signals]
        risk_rewards = [s.get('risk_reward_ratio', 1) for s in signals]
        
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        avg_risk_reward = sum(risk_rewards) / len(risk_rewards) if risk_rewards else 0
        
        # Find best signal
        best_signal = max(signals, key=lambda s: s.get('confidence_score', 0) * s.get('risk_reward_ratio', 1))
        
        # Signal distribution
        signal_distribution = {}
        for signal in signals:
            signal_type = signal.get('signal_type', 'UNKNOWN')
            signal_distribution[signal_type] = signal_distribution.get(signal_type, 0) + 1
        
        # Quality breakdown
        high_quality = len([s for s in signals if s.get('confidence_score', 0) >= 0.8])
        medium_quality = len([s for s in signals if 0.6 <= s.get('confidence_score', 0) < 0.8])
        low_quality = len([s for s in signals if s.get('confidence_score', 0) < 0.6])
        
        return {
            'total_signals': total_signals,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'avg_confidence': round(avg_confidence, 2),
            'avg_risk_reward': round(avg_risk_reward, 2),
            'best_signal': {
                'type': best_signal.get('signal_type'),
                'confidence': best_signal.get('confidence_score'),
                'risk_reward': best_signal.get('risk_reward_ratio'),
                'entry_price': best_signal.get('entry_price'),
                'target_price': best_signal.get('target_price')
            },
            'signal_distribution': signal_distribution,
            'quality_breakdown': {
                'high_quality': high_quality,
                'medium_quality': medium_quality,
                'low_quality': low_quality
            }
        }
    
    def _simulate_signal_execution(self, signals, symbol, start_date, end_date):
        """Simulate signal execution for backtesting by checking if targets were hit"""
        if not signals:
            return signals
        
        logger.info(f"Simulating execution for {len(signals)} signals for {symbol.symbol}")
        
        # Get historical price data for execution simulation
        historical_data = self._get_historical_price_data(symbol, start_date, end_date)
        
        executed_signals = []
        for signal in signals:
            try:
                # Create a copy of the signal to modify; ensure SELL/BUY prices are logical
                executed_signal = signal.copy()
                self._normalize_signal_prices(executed_signal)

                # Simulate execution using normalized prices
                execution_result = self._simulate_single_signal_execution(
                    executed_signal, historical_data, symbol
                )
                
                # Update signal with execution results
                executed_signal.update(execution_result)
                executed_signals.append(executed_signal)
                
            except Exception as e:
                logger.error(f"Error simulating execution for signal {signal.get('id', 'unknown')}: {e}")
                # Keep original signal if execution simulation fails
                executed_signals.append(signal)
        
        logger.info(f"Simulated execution for {len(executed_signals)} signals")
        return executed_signals
    
    def _get_historical_price_data(self, symbol, start_date, end_date):
        """Get historical price data for execution simulation"""
        try:
            from apps.data.models import MarketData
            from apps.data.historical_data_service import get_historical_data
            
            # Map USDT symbols to base symbols for database lookup
            symbol_mapping = {
                'BTCUSDT': 'BTC', 'ETHUSDT': 'ETH', 'BNBUSDT': 'BNB', 'SOLUSDT': 'SOL', 'XRPUSDT': 'XRP',
                'ADAUSDT': 'ADA', 'DOGEUSDT': 'DOGE', 'TRXUSDT': 'TRX', 'LINKUSDT': 'LINK', 'DOTUSDT': 'DOT',
                'MATICUSDT': 'MATIC', 'AVAXUSDT': 'AVAX', 'UNIUSDT': 'UNI', 'ATOMUSDT': 'ATOM', 'LTCUSDT': 'LTC',
                'BCHUSDT': 'BCH', 'ALGOUSDT': 'ALGO', 'VETUSDT': 'VET', 'FTMUSDT': 'FTM', 'ICPUSDT': 'ICP',
                'SANDUSDT': 'SAND', 'MANAUSDT': 'MANA', 'NEARUSDT': 'NEAR', 'APTUSDT': 'APT', 'OPUSDT': 'OP',
                'ARBUSDT': 'ARB', 'MKRUSDT': 'MKR', 'RUNEUSDT': 'RUNE', 'INJUSDT': 'INJ', 'STXUSDT': 'STX',
                'AAVEUSDT': 'AAVE', 'COMPUSDT': 'COMP', 'CRVUSDT': 'CRV', 'LDOUSDT': 'LDO', 'CAKEUSDT': 'CAKE',
                'PENDLEUSDT': 'PENDLE', 'DYDXUSDT': 'DYDX', 'FETUSDT': 'FET', 'CROUSDT': 'CRO', 'KCSUSDT': 'KCS',
                'OKBUSDT': 'OKB', 'LEOUSDT': 'LEO', 'QNTUSDT': 'QNT', 'HBARUSDT': 'HBAR', 'EGLDUSDT': 'EGLD',
                'FLOWUSDT': 'FLOW', 'SEIUSDT': 'SEI', 'TIAUSDT': 'TIA', 'GALAUSDT': 'GALA', 'GRTUSDT': 'GRT',
                'XMRUSDT': 'XMR', 'ZECUSDT': 'ZEC', 'DAIUSDT': 'DAI', 'TUSDUSDT': 'TUSD', 'GTUSDT': 'GT',
            }
            
            # Get the base symbol for database lookup
            base_symbol_name = symbol_mapping.get(symbol.symbol, symbol.symbol)
            
            # Try to find the symbol in database
            from apps.trading.models import Symbol
            try:
                base_symbol = Symbol.objects.get(symbol=base_symbol_name)
            except Symbol.DoesNotExist:
                logger.error(f"Symbol {base_symbol_name} not found in database")
                return {}
            
            # First try to get data from database using base symbol
            market_data = MarketData.objects.filter(
                symbol=base_symbol,
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            price_data = {}
            
            # Safe float conversion helper
            def safe_float_price(value, default=0.0):
                if value is None:
                    return default
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return default
            
            if market_data.exists():
                # Use existing database data
                for data_point in market_data:
                    timestamp = data_point.timestamp
                    price_data[timestamp] = {
                        'open': safe_float_price(data_point.open_price, 0),
                        'high': safe_float_price(data_point.high_price, 0),
                        'low': safe_float_price(data_point.low_price, 0),
                        'close': safe_float_price(data_point.close_price, 0),
                        'volume': safe_float_price(data_point.volume, 0)
                    }
                logger.info(f"Retrieved {len(price_data)} price data points from database for execution simulation")
            else:
                # Fetch real historical data from Binance API
                logger.info(f"No database data found, fetching real historical data for {symbol.symbol}")
                historical_data = get_historical_data(symbol.symbol, start_date, end_date, '1h')
                
                if historical_data:
                    for data_point in historical_data:
                        timestamp = data_point['timestamp']
                        price_data[timestamp] = {
                            'open': data_point['open'],
                            'high': data_point['high'],
                            'low': data_point['low'],
                            'close': data_point['close'],
                            'volume': data_point['volume']
                        }
                    logger.info(f"Retrieved {len(price_data)} real historical price data points for execution simulation")
                else:
                    logger.warning(f"No historical data available for {symbol.symbol} in range {start_date} to {end_date}")
            
            return price_data
            
        except Exception as e:
            logger.error(f"Error getting historical price data: {e}")
            return {}
    
    def _simulate_single_signal_execution(self, signal, historical_data, symbol):
        """Simulate execution of a single signal"""
        try:
            from datetime import datetime, timedelta
            from decimal import Decimal
            
            # Parse signal timestamp
            signal_time = datetime.fromisoformat(signal['created_at'].replace('Z', '+00:00'))
            if signal_time.tzinfo is None:
                from django.utils import timezone
                signal_time = timezone.make_aware(signal_time)
            
            # FIXED: Handle empty or invalid price values
            try:
                entry_price = float(signal['entry_price']) if signal['entry_price'] and signal['entry_price'] != '' else 0.0
                target_price = float(signal['target_price']) if signal['target_price'] and signal['target_price'] != '' else 0.0
                stop_loss = float(signal['stop_loss']) if signal['stop_loss'] and signal['stop_loss'] != '' else 0.0
            except (ValueError, TypeError):
                # If prices are invalid, skip this signal
                return {
                    'is_executed': False,
                    'executed_at': None,
                    'execution_price': None,
                    'is_profitable': None,
                    'profit_loss': 0.0,
                    'execution_status': 'INVALID_PRICES'
                }
            
            # Skip signals with zero prices
            if entry_price == 0.0 or target_price == 0.0 or stop_loss == 0.0:
                return {
                    'is_executed': False,
                    'executed_at': None,
                    'execution_price': None,
                    'is_profitable': None,
                    'profit_loss': 0.0,
                    'execution_status': 'ZERO_PRICES'
                }
            
            signal_type = signal['signal_type'].upper()
            
            # Look for execution in the next 7 days after signal
            execution_window = timedelta(days=7)
            end_time = signal_time + execution_window
            
            # Find price data points within the execution window
            relevant_price_data = []
            for timestamp, price_data in historical_data.items():
                if timestamp >= signal_time and timestamp <= end_time:
                    relevant_price_data.append((timestamp, price_data))
            
            # Sort by timestamp to process chronologically
            relevant_price_data.sort(key=lambda x: x[0])
            
            if not relevant_price_data:
                # No price data found, mark as not executed
                return {
                    'is_executed': False,
                    'executed_at': None,
                    'execution_price': None,
                    'is_profitable': None,
                    'profit_loss': 0.0,
                    'execution_status': 'NO_DATA'
                }
            
            # Process price data chronologically to find execution
            execution_price = None
            execution_time = None
            execution_status = 'NOT_EXECUTED'
            
            for timestamp, price_data in relevant_price_data:
                high_price = price_data['high']
                low_price = price_data['low']
                
                if signal_type in ['BUY', 'STRONG_BUY']:
                    # For buy signals, check if price hit target (above entry) or stop loss (below entry)
                    if high_price >= target_price:
                        execution_price = target_price
                        execution_time = timestamp
                        execution_status = 'TARGET_HIT'
                        break
                    elif low_price <= stop_loss:
                        execution_price = stop_loss
                        execution_time = timestamp
                        execution_status = 'STOP_LOSS_HIT'
                        break
                else:  # SELL or STRONG_SELL
                    # For sell signals, check if price hit target (below entry) or stop loss (above entry)
                    if low_price <= target_price:
                        execution_price = target_price
                        execution_time = timestamp
                        execution_status = 'TARGET_HIT'
                        break
                    elif high_price >= stop_loss:
                        execution_price = stop_loss
                        execution_time = timestamp
                        execution_status = 'STOP_LOSS_HIT'
                        break
            
            # If no target or stop loss was hit, execute at the last available price
            if execution_price is None and relevant_price_data:
                last_timestamp, last_price_data = relevant_price_data[-1]
                execution_price = last_price_data['close']
                execution_time = last_timestamp
                execution_status = 'CLOSE_PRICE'
            
            # Calculate profit/loss based on whether target or stop loss was hit
            if execution_price is not None:
                if execution_status == 'TARGET_HIT':
                    # Target was hit = PROFIT
                    if signal_type in ['BUY', 'STRONG_BUY']:
                        profit_loss = (target_price - entry_price) / entry_price * 100
                    else:  # SELL or STRONG_SELL
                        profit_loss = (entry_price - target_price) / entry_price * 100
                    is_profitable = True
                elif execution_status == 'STOP_LOSS_HIT':
                    # Stop loss was hit = LOSS
                    if signal_type in ['BUY', 'STRONG_BUY']:
                        profit_loss = (stop_loss - entry_price) / entry_price * 100
                    else:  # SELL or STRONG_SELL
                        profit_loss = (entry_price - stop_loss) / entry_price * 100
                    is_profitable = False
                else:
                    # Close price execution - calculate based on actual execution
                    if signal_type in ['BUY', 'STRONG_BUY']:
                        profit_loss = (execution_price - entry_price) / entry_price * 100
                        is_profitable = execution_price > entry_price
                    else:  # SELL or STRONG_SELL
                        profit_loss = (entry_price - execution_price) / entry_price * 100
                        is_profitable = execution_price < entry_price
            else:
                # No execution possible
                return {
                    'is_executed': False,
                    'executed_at': None,
                    'execution_price': None,
                    'is_profitable': None,
                    'profit_loss': 0.0,
                    'execution_status': 'NO_DATA'
                }
            
            # Determine if signal was opened (executed) and closed (hit target or stop loss)
            is_opened = execution_status in ['TARGET_HIT', 'STOP_LOSS_HIT', 'CLOSE_PRICE']
            is_closed = execution_status in ['TARGET_HIT', 'STOP_LOSS_HIT']
            
            # Signal open date (when signal was executed/opened)
            open_date = execution_time.isoformat() if (execution_time and is_opened) else None
            
            # Signal closing date (when signal hit target or stop loss)
            closing_date = execution_time.isoformat() if (execution_time and is_closed) else None
            
            return {
                'is_executed': True,
                'executed_at': execution_time.isoformat() if execution_time else None,
                'open_date': open_date,  # When signal was opened/executed
                'closing_date': closing_date,  # Only set when signal hit target or stop loss
                'execution_price': round(execution_price, 6),
                'is_profitable': is_profitable,
                'profit_loss': round(profit_loss, 2),
                'execution_status': execution_status,
                'is_opened': is_opened,
                'is_closed': is_closed
            }
            
        except Exception as e:
            logger.error(f"Error simulating single signal execution: {e}")
            return {
                'is_executed': False,
                'executed_at': None,
                'execution_price': None,
                'is_profitable': None,
                'profit_loss': 0.0,
                'execution_status': 'ERROR'
            }
    
    def _analyze_executed_signals(self, executed_signals, symbol, start_date, end_date):
        """Analyze executed signals for performance metrics"""
        try:
            total_signals = len(executed_signals)
            profit_signals = 0
            loss_signals = 0
            not_opened_signals = 0
            total_investment = 0
            total_profit_loss = 0
            
            individual_signals = []
            
            for signal in executed_signals:
                # Calculate investment (assuming $1000 per signal)
                investment = 1000.0
                total_investment += investment
                
                if signal.get('is_executed', False):
                    profit_loss_pct = signal.get('profit_loss', 0)
                    profit_loss_amount = investment * (profit_loss_pct / 100)
                    total_profit_loss += profit_loss_amount
                    
                    if signal.get('is_profitable', False):
                        profit_signals += 1
                        status = 'PROFIT'
                    else:
                        loss_signals += 1
                        status = 'LOSS'
                else:
                    profit_loss_amount = 0
                    not_opened_signals += 1
                    status = 'NOT_OPENED'
                
                # Derive dates/times
                created_at_str = signal.get('created_at', '') or ''
                executed_at_str = signal.get('executed_at', None)
                open_date_str = signal.get('open_date', None)  # When signal was opened/executed
                closing_date_str = signal.get('closing_date', None)  # When signal hit target or stop loss

                # Signal created date (when signal was generated)
                signal_date = created_at_str[:10] if created_at_str else ''
                signal_time = created_at_str[11:19] if len(created_at_str) >= 19 else ''

                # Signal open date (when signal was opened/executed)
                if open_date_str:
                    open_date = open_date_str[:10]
                    open_time = open_date_str[11:19] if len(open_date_str) >= 19 else ''
                else:
                    open_date = ''
                    open_time = ''

                # Signal closing date (when signal hit take profit or stop loss)
                if closing_date_str:
                    closing_date = closing_date_str[:10]
                    closing_time = closing_date_str[11:19] if len(closing_date_str) >= 19 else ''
                else:
                    closing_date = ''
                    closing_time = ''

                # Add to individual signals with explicit fields used by UI
                individual_signals.append({
                    'signal_id': signal.get('id', 'unknown'),
                    'date': signal_date,  # legacy field
                    'time': signal_time,  # legacy field
                    'signal_date': signal_date,  # Signal created date
                    'signal_time': signal_time,  # Signal created time
                    'open_date': open_date,  # Signal open date (when executed)
                    'open_time': open_time,  # Signal open time
                    'closing_date': closing_date,  # Signal closing date (when hit target/stop loss)
                    'closing_time': closing_time,  # Signal closing time
                    'executed_at': executed_at_str,  # raw timestamp (legacy)
                    'type': signal.get('signal_type', 'UNKNOWN'),
                    'signal_type': signal.get('signal_type', 'UNKNOWN'),
                    'entry_price': signal.get('entry_price', 0),
                    'target_price': signal.get('target_price', 0),
                    'stop_loss': signal.get('stop_loss', 0),
                    'execution_price': signal.get('execution_price', 0),
                    'is_executed': signal.get('is_executed', False),
                    'is_opened': signal.get('is_opened', False),  # whether signal was opened
                    'is_closed': signal.get('is_closed', False),  # whether signal hit target or stop loss
                    'status': status,
                    'p_l_amount': round(profit_loss_amount, 2),
                    'profit_loss_amount': round(profit_loss_amount, 2),  # legacy
                    'p_l_percentage': round(signal.get('profit_loss', 0), 2),
                    'profit_loss_percentage': round(signal.get('profit_loss', 0), 2),  # legacy
                    'confidence': signal.get('confidence_score', 0),
                    'confidence_score': signal.get('confidence_score', 0),
                    'risk_reward_ratio': signal.get('risk_reward_ratio', 0)
                })
            
            # Calculate total profit percentage
            total_profit_percentage = (total_profit_loss / total_investment * 100) if total_investment > 0 else 0
            
            # Calculate strategy quality
            quality_score = self._calculate_strategy_quality(
                total_signals, profit_signals, loss_signals, not_opened_signals, total_profit_percentage
            )
            
            # Validate signal prices against real market history
            try:
                from apps.data.price_validation_service import validate_backtesting_results
                validation_results = validate_backtesting_results(
                    symbol.symbol, start_date, end_date, individual_signals
                )
                logger.info(f"Price validation: {validation_results['valid_signals']}/{validation_results['total_signals']} signals valid")
            except Exception as e:
                logger.warning(f"Price validation failed: {e}")
                validation_results = None
            
            return {
                'symbol': symbol.symbol,
                'symbol_name': symbol.name,
                'analysis_date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_signals': total_signals,  # Add at top level for compatibility
                'executed_signals': profit_signals + loss_signals,  # Add executed count
                'expired_signals': 0,  # Not tracking expired separately
                'profit_signals': profit_signals,
                'loss_signals': loss_signals,
                'not_opened_signals': not_opened_signals,
                'total_investment': total_investment,
                'total_profit_loss': total_profit_loss,
                'profit_percentage': round(total_profit_percentage, 2),
                'win_rate': ((profit_signals / (profit_signals + loss_signals)) * 100) if (profit_signals + loss_signals) > 0 else 0.0,
                'quality_score': quality_score.get('quality_score', 0),
                'quality_rating': quality_score.get('quality_rating', 'Unknown'),
                'period': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'days': (end_date - start_date).days
                },
                'total_summary': {
                    'total_signals': total_signals,
                    'profit_signals': profit_signals,
                    'loss_signals': loss_signals,
                    'not_opened_signals': not_opened_signals,
                    'total_investment': total_investment,
                    'total_profit_loss': total_profit_loss,
                    'total_profit_percentage': round(total_profit_percentage, 2)
                },
                'individual_signals': individual_signals,
                'strategy_quality': quality_score,
                'price_validation': validation_results
            }
            
        except Exception as e:
            logger.error(f"Error analyzing executed signals: {e}")
            return self._empty_signal_analysis(symbol, start_date, end_date)
    
    def _calculate_strategy_quality(self, total_signals, profit_signals, loss_signals, not_opened_signals, profit_percentage):
        """Calculate strategy quality score and rating"""
        try:
            if total_signals == 0:
                return {
                    'quality_score': 0,
                    'quality_rating': 'No Data',
                    'recommendation': 'No signals generated to analyze',
                    'metrics': {'profit_rate': 0, 'execution_rate': 0, 'profit_percentage': 0}
                }
            
            # Calculate metrics
            profit_rate = (profit_signals / total_signals) * 100 if total_signals > 0 else 0
            execution_rate = ((profit_signals + loss_signals) / total_signals) * 100 if total_signals > 0 else 0
            
            # Calculate quality score (0-100)
            quality_score = 0
            
            # Execution rate component (40% weight)
            execution_score = min(execution_rate * 0.4, 40)
            quality_score += execution_score
            
            # Profit rate component (30% weight)
            profit_score = min(profit_rate * 0.3, 30)
            quality_score += profit_score
            
            # Profit percentage component (30% weight)
            profit_pct_score = min(max(profit_percentage, 0) * 0.3, 30)
            quality_score += profit_pct_score
            
            # Determine rating
            if quality_score >= 80:
                rating = 'Excellent'
                recommendation = 'Strategy is performing very well. Consider increasing position sizes.'
            elif quality_score >= 60:
                rating = 'Good'
                recommendation = 'Strategy is performing well. Monitor for consistency.'
            elif quality_score >= 40:
                rating = 'Fair'
                recommendation = 'Strategy needs improvement. Review entry/exit criteria.'
            elif quality_score >= 20:
                rating = 'Poor'
                recommendation = 'Strategy needs significant improvement. Consider strategy revision.'
            else:
                rating = 'Very Poor'
                recommendation = 'Strategy is not performing well. Major revision required.'
            
            return {
                'quality_score': round(quality_score, 1),
                'quality_rating': rating,
                'recommendation': recommendation,
                'metrics': {
                    'profit_rate': round(profit_rate, 1),
                    'execution_rate': round(execution_rate, 1),
                    'profit_percentage': round(profit_percentage, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating strategy quality: {e}")
            return {
                'quality_score': 0,
                'quality_rating': 'Error',
                'recommendation': f'Error calculating quality: {str(e)}',
                'metrics': {'profit_rate': 0, 'execution_rate': 0, 'profit_percentage': 0}
            }
    
    def _empty_signal_analysis(self, symbol, start_date, end_date):
        """Return empty signal analysis structure"""
        return {
            'symbol': symbol.symbol,
            'symbol_name': symbol.name,
            'analysis_date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_signals': 0,  # Add at top level for compatibility
            'executed_signals': 0,
            'expired_signals': 0,
            'profit_signals': 0,
            'loss_signals': 0,
            'not_opened_signals': 0,
            'total_investment': 0,
            'total_profit_loss': 0,
            'profit_percentage': 0,
            'win_rate': 0.0,
            'quality_score': 0,
            'quality_rating': 'No Data',
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'days': (end_date - start_date).days
            },
            'total_summary': {
                'total_signals': 0,
                'profit_signals': 0,
                'loss_signals': 0,
                'not_opened_signals': 0,
                'total_investment': 0,
                'total_profit_loss': 0,
                'total_profit_percentage': 0
            },
            'individual_signals': [],
            'strategy_quality': {
                'quality_score': 0,
                'quality_rating': 'No Data',
                'recommendation': 'No signals to analyze',
                'metrics': {'profit_rate': 0, 'execution_rate': 0, 'profit_percentage': 0}
            }
        }


class BacktestSearchAPIView(View):
    """API for managing backtest searches"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        """Get symbols or search history"""
        action = request.GET.get('action', 'symbols')
        
        if action == 'symbols':
            return self._get_symbols()
        elif action == 'history':
            return self._get_search_history(request)
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'})
    
    def post(self, request):
        """Delete a search"""
        try:
            data = json.loads(request.body)
            search_id = data.get('search_id')
            
            if not search_id:
                return JsonResponse({'success': False, 'error': 'Search ID required'})
            
            # For now, just return success (no actual deletion)
            return JsonResponse({'success': True})
            
        except Exception as e:
            logger.error(f"Error deleting search: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    def _get_symbols(self):
        """Get available symbols"""
        try:
            symbols = Symbol.objects.filter(
                is_crypto_symbol=True,
                is_active=True
            ).order_by('symbol')
            
            symbol_list = []
            for symbol in symbols:
                symbol_list.append({
                    'symbol': symbol.symbol,
                    'name': symbol.name,
                    'is_spot_tradable': symbol.is_spot_tradable
                })
            
            return JsonResponse({
                'success': True,
                'symbols': symbol_list
            })
            
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    def _get_search_history(self, request):
        """Get search history for the user"""
        try:
            # For now, return empty history
            return JsonResponse({
                'success': True,
                'searches': []
            })
            
        except Exception as e:
            logger.error(f"Error getting search history: {e}")
            return JsonResponse({'success': False, 'error': str(e)})


class TradingViewExportAPIView(View):
    """API for exporting signals to TradingView format"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        """Export signals to CSV for TradingView"""
        try:
            data = json.loads(request.body)
            
            symbol = data.get('symbol', 'BTC')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            
            # Get signals for the period
            symbol_obj = Symbol.objects.filter(symbol=symbol).first()
            if not symbol_obj:
                return JsonResponse({'success': False, 'error': 'Symbol not found'})
            
            # Get signals in the date range
            signals = TradingSignal.objects.filter(
                symbol=symbol_obj,
                created_at__date__range=[start_date.split('T')[0], end_date.split('T')[0]]
            ).order_by('created_at')
            
            # Generate CSV content
            csv_content = self._generate_csv_content(signals)
            
            filename = f"{symbol}_signals_{start_date.split('T')[0]}_to_{end_date.split('T')[0]}.csv"
            
            return JsonResponse({
                'success': True,
                'csv_content': csv_content,
                'filename': filename
            })
            
        except Exception as e:
            logger.error(f"Error exporting to TradingView: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    def _generate_csv_content(self, signals):
        """Generate CSV content for signals"""
        headers = [
            'Timestamp', 'Symbol', 'Signal Type', 'Strength', 'Confidence',
            'Entry Price', 'Target Price', 'Stop Loss', 'Risk/Reward',
            'Timeframe', 'Quality Score'
        ]
        
        rows = [headers]
        
        for signal in signals:
            row = [
                signal.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                signal.symbol.symbol,
                signal.signal_type.name if signal.signal_type else 'N/A',
                signal.strength,
                f"{signal.confidence_score:.2f}",
                str(signal.entry_price) if signal.entry_price else 'N/A',
                str(signal.target_price) if signal.target_price else 'N/A',
                str(signal.stop_loss) if signal.stop_loss else 'N/A',
                str(signal.risk_reward_ratio) if signal.risk_reward_ratio else 'N/A',
                signal.timeframe or 'N/A',
                str(signal.quality_score) if signal.quality_score else 'N/A'
            ]
            rows.append(row)
        
        # Convert to CSV format
        csv_lines = []
        for row in rows:
            csv_lines.append(','.join(f'"{str(cell)}"' for cell in row))
        
        return '\n'.join(csv_lines)


class BacktestingHistoryExportAPIView(View):
    """API for exporting all backtesting history as CSV files"""
    
    @method_decorator(csrf_exempt)
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        """Export all backtesting history for each cryptocurrency"""
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'export_all_history':
                return self._export_all_backtesting_history()
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'})
                
        except Exception as e:
            logger.error(f"Backtesting history export error: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    def _export_all_backtesting_history(self):
        """Export all backtesting signals for each cryptocurrency as separate CSV files"""
        try:
            # Get all backtesting signals grouped by symbol
            backtesting_signals = TradingSignal.objects.filter(
                metadata__is_backtesting=True
            ).select_related('symbol', 'signal_type').order_by('symbol__symbol', 'created_at')
            
            if not backtesting_signals.exists():
                return JsonResponse({
                    'success': False, 
                    'error': 'No backtesting history found'
                })
            
            # Group signals by symbol
            signals_by_symbol = {}
            for signal in backtesting_signals:
                symbol = signal.symbol.symbol
                if symbol not in signals_by_symbol:
                    signals_by_symbol[symbol] = []
                signals_by_symbol[symbol].append(signal)
            
            # Create ZIP file in memory
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Create CSV file for each symbol
                for symbol, signals in signals_by_symbol.items():
                    csv_content = self._generate_csv_for_symbol(symbol, signals)
                    filename = f"{symbol}_backtesting_history.csv"
                    zip_file.writestr(filename, csv_content)
            
            # Prepare ZIP file for download
            zip_buffer.seek(0)
            zip_data = base64.b64encode(zip_buffer.getvalue()).decode('utf-8')
            
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f"backtesting_history_all_cryptos_{timestamp}.zip"
            
            return JsonResponse({
                'success': True,
                'files': {
                    'zip_data': zip_data,
                    'filename': zip_filename,
                    'symbols_count': len(signals_by_symbol),
                    'total_signals': backtesting_signals.count()
                }
            })
            
        except Exception as e:
            logger.error(f"Error exporting backtesting history: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    def _generate_csv_for_symbol(self, symbol, signals):
        """Generate CSV content for a specific symbol"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Safe float conversion helper
        def safe_float_export(value, default=0.0):
            if value is None:
                return default
            try:
                return float(value)
            except (TypeError, ValueError):
                return default
        
        # CSV Headers
        headers = [
            'Date', 'Time', 'Symbol', 'Signal Type', 'Strength', 'Confidence Score',
            'Entry Price', 'Target Price', 'Stop Loss', 'Risk/Reward Ratio',
            'Timeframe', 'Entry Point Type', 'Quality Score', 'Is Executed',
            'Execution Price', 'Is Profitable', 'Profit/Loss', 'Performance %',
            'Notes', 'Created At', 'Updated At'
        ]
        writer.writerow(headers)
        
        # Add signal data
        for signal in signals:
            # Calculate performance percentage with safe float conversion
            performance_pct = 0
            if signal.is_executed and signal.execution_price and signal.entry_price:
                exec_price = safe_float_export(signal.execution_price, 0)
                entry_price = safe_float_export(signal.entry_price, 0)
                if entry_price > 0:
                    if signal.signal_type.name in ['BUY', 'STRONG_BUY']:
                        performance_pct = ((exec_price - entry_price) / entry_price) * 100
                    else:
                        performance_pct = ((entry_price - exec_price) / entry_price) * 100
            
            row = [
                signal.created_at.strftime('%Y-%m-%d'),
                signal.created_at.strftime('%H:%M:%S'),
                symbol,
                signal.signal_type.name if signal.signal_type else 'N/A',
                signal.strength or 'N/A',
                f"{signal.confidence_score:.2f}" if signal.confidence_score else 'N/A',
                str(signal.entry_price) if signal.entry_price else 'N/A',
                str(signal.target_price) if signal.target_price else 'N/A',
                str(signal.stop_loss) if signal.stop_loss else 'N/A',
                f"{signal.risk_reward_ratio:.2f}" if signal.risk_reward_ratio else 'N/A',
                signal.timeframe or 'N/A',
                signal.entry_point_type or 'N/A',
                f"{signal.quality_score:.2f}" if signal.quality_score else 'N/A',
                'Yes' if signal.is_executed else 'No',
                str(signal.execution_price) if signal.execution_price else 'N/A',
                'Yes' if signal.is_profitable else 'No' if signal.is_profitable is not None else 'N/A',
                str(signal.profit_loss) if signal.profit_loss else 'N/A',
                f"{performance_pct:.2f}%" if performance_pct else 'N/A',
                signal.notes or 'N/A',
                signal.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                signal.updated_at.strftime('%Y-%m-%d %H:%M:%S') if signal.updated_at else 'N/A'
            ]
            writer.writerow(row)
        
        return output.getvalue()


class AvailableSymbolsAPIView(View):
    """API to get symbols with real historical data for backtesting"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        """Get symbols that have real historical data for backtesting"""
        try:
            symbols_info = []
            
            # Strategy 1: Try to get symbols from MarketData (if historical data exists)
            try:
                # Define popular cryptocurrencies (support both USDT and base formats)
                popular_symbols_usdt = [
                    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'AAVEUSDT',
                    'XRPUSDT', 'DOGEUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT', 'LINKUSDT',
                    'UNIUSDT', 'ATOMUSDT', 'FTMUSDT', 'ALGOUSDT', 'VETUSDT', 'ICPUSDT',
                    'THETAUSDT', 'FILUSDT', 'TRXUSDT', 'XLMUSDT', 'LTCUSDT', 'BCHUSDT',
                    'ETCUSDT', 'XMRUSDT', 'ZECUSDT', 'DASHUSDT', 'NEOUSDT', 'QTUMUSDT'
                ]
                # Also try base symbols (BTC, ETH, etc.)
                popular_symbols_base = [
                    'BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'AAVE', 'XRP', 'DOGE', 'MATIC',
                    'DOT', 'AVAX', 'LINK', 'UNI', 'ATOM', 'FTM', 'ALGO', 'VET', 'ICP',
                    'THETA', 'FIL', 'TRX', 'XLM', 'LTC', 'BCH', 'ETC', 'XMR', 'ZEC',
                    'DASH', 'NEO', 'QTUM'
                ]
                all_popular = popular_symbols_usdt + popular_symbols_base
                
                # Get symbols that have MarketData
                symbols_with_data = MarketData.objects.filter(
                    symbol__symbol__in=all_popular,
                    close_price__gt=0  # Any positive price
                ).values_list('symbol__symbol', flat=True).distinct()
                
                if symbols_with_data:
                    for symbol_name in symbols_with_data:
                        try:
                            symbol = Symbol.objects.get(symbol=symbol_name)
                            data_count = MarketData.objects.filter(symbol=symbol).count()
                            
                            # Check data quality (price range)
                            price_stats = MarketData.objects.filter(symbol=symbol).aggregate(
                                min_price=Min('close_price'),
                                max_price=Max('close_price'),
                                avg_price=Avg('close_price')
                            )
                            
                            # Determine if data looks realistic
                            is_real_data = (
                                price_stats['min_price'] and 
                                price_stats['min_price'] > 0.001 and  # Not too low
                                price_stats['max_price'] and 
                                price_stats['max_price'] < 1000000   # Not too high
                            )
                            
                            # Safe float conversion helper for price stats
                            def safe_float_stats(value, default=0.0):
                                if value is None:
                                    return default
                                try:
                                    return float(value)
                                except (TypeError, ValueError):
                                    return default
                            
                            symbols_info.append({
                                'symbol': symbol_name,
                                'name': symbol.name or symbol_name,
                                'data_count': data_count,
                                'is_available': True,
                                'is_real_data': is_real_data,
                                'price_range': {
                                    'min': safe_float_stats(price_stats['min_price'], 0) if price_stats['min_price'] else 0,
                                    'max': safe_float_stats(price_stats['max_price'], 0) if price_stats['max_price'] else 0,
                                    'avg': safe_float_stats(price_stats['avg_price'], 0) if price_stats['avg_price'] else 0
                                }
                            })
                        except Symbol.DoesNotExist:
                            continue
            except Exception as e:
                logger.warning(f"Error getting symbols from MarketData: {e}")
            
            # Strategy 2: Fallback to Symbol table (all active crypto symbols)
            if not symbols_info:
                logger.info("No symbols found in MarketData, falling back to Symbol table")
                try:
                    active_symbols = Symbol.objects.filter(
                        is_crypto_symbol=True,
                        is_active=True
                    ).order_by('symbol')[:100]  # Limit to top 100
                    
                    # Safe float conversion helper for price stats
                    def safe_float_stats_fallback(value, default=0.0):
                        if value is None:
                            return default
                        try:
                            return float(value)
                        except (TypeError, ValueError):
                            return default
                    
                    for symbol in active_symbols:
                        # Try to get MarketData count if available
                        try:
                            data_count = MarketData.objects.filter(symbol=symbol).count()
                            price_stats = MarketData.objects.filter(symbol=symbol).aggregate(
                                min_price=Min('close_price'),
                                max_price=Max('close_price'),
                                avg_price=Avg('close_price')
                            )
                            is_real_data = data_count > 0 and (
                                price_stats['min_price'] and price_stats['min_price'] > 0.001
                            )
                        except:
                            data_count = 0
                            price_stats = {'min_price': None, 'max_price': None, 'avg_price': None}
                            is_real_data = False
                        
                        symbols_info.append({
                            'symbol': symbol.symbol,
                            'name': symbol.name or symbol.symbol,
                            'data_count': data_count,
                            'is_available': True,
                            'is_real_data': is_real_data,
                            'price_range': {
                                'min': safe_float_stats_fallback(price_stats['min_price'], 0) if price_stats['min_price'] else 0,
                                'max': safe_float_stats_fallback(price_stats['max_price'], 0) if price_stats['max_price'] else 0,
                                'avg': safe_float_stats_fallback(price_stats['avg_price'], 0) if price_stats['avg_price'] else 0
                            }
                        })
                except Exception as e:
                    logger.error(f"Error getting symbols from Symbol table: {e}")
            
            # Sort by data count (most data first), then by symbol name
            symbols_info.sort(key=lambda x: (x['data_count'], x['symbol']), reverse=True)
            
            if not symbols_info:
                logger.warning("No symbols available for backtesting")
                return JsonResponse({
                    'success': False,
                    'error': 'No symbols found. Please ensure symbols are configured in the database.',
                    'symbols': [],
                    'total_available': 0
                })
            
            return JsonResponse({
                'success': True,
                'symbols': symbols_info,
                'total_available': len(symbols_info),
                'message': f'Found {len(symbols_info)} symbols available for backtesting'
            })
            
        except Exception as e:
            logger.error(f"Error getting available symbols: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Error loading symbols: {str(e)}',
                'symbols': [],
                'total_available': 0
            })

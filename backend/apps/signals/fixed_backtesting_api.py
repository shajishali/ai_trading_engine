"""
FIXED Backtesting API - Correct Signal Execution Logic
This fixes the issue where SELL signals were showing as losses when they should be profits
"""

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from django.db.models import Q

from apps.trading.models import Symbol
from apps.signals.models import TradingSignal
from apps.data.models import MarketData

logger = logging.getLogger(__name__)

class FixedBacktestAPIView(View):
    """FIXED backtesting API with correct signal execution logic"""

    def post(self, request):
        """Run FIXED backtest with correct SELL signal execution"""
        try:
            data = json.loads(request.body)
            
            # Extract parameters
            symbol_name = data.get('symbol', '').upper()
            start_date_str = data.get('start_date')
            end_date_str = data.get('end_date')
            
            if not symbol_name or not start_date_str or not end_date_str:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required parameters: symbol, start_date, end_date'
                }, status=400)
            
            # Parse dates
            try:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                
                # Ensure UTC timezone
                if start_date.tzinfo is None:
                    start_date = timezone.make_aware(start_date)
                if end_date.tzinfo is None:
                    end_date = timezone.make_aware(end_date)
                    
            except ValueError as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid date format: {str(e)}'
                }, status=400)
            
            # Get symbol
            try:
                symbol = Symbol.objects.get(symbol=symbol_name, symbol_type='CRYPTO', is_active=True)
            except Symbol.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Symbol {symbol_name} not found or not active'
                }, status=404)
            
            # Run FIXED backtest
            logger.info(f"Running FIXED backtest for {symbol_name} from {start_date.date()} to {end_date.date()}")
            
            backtest_results = self._run_fixed_backtest(symbol, start_date, end_date)
            
            # Prepare response
            response_data = {
                'success': True,
                'backtest_results': backtest_results,
                'metadata': {
                    'symbol': symbol_name,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'backtest_timestamp': timezone.now().isoformat(),
                    'fixes_applied': {
                        'sell_signal_execution': 'FIXED - SELL signals now execute at correct prices',
                        'target_hit_logic': 'FIXED - Target price execution logic corrected',
                        'profit_loss_calculation': 'FIXED - P&L calculation for SELL signals corrected'
                    }
                }
            }
            
            logger.info(f"FIXED backtest completed for {symbol_name}: {backtest_results['total_signals']} signals processed")
            
            return JsonResponse(response_data)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in FIXED backtest API: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Backtest failed: {str(e)}'
            }, status=500)

    def _run_fixed_backtest(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> dict:
        """Run FIXED backtest with correct signal execution logic"""
        try:
            # Get signals in date range
            signals = TradingSignal.objects.filter(
                symbol=symbol,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).order_by('created_at')
            
            if not signals.exists():
                return {
                    'symbol': symbol.symbol,
                    'total_signals': 0,
                    'executed_signals': 0,
                    'expired_signals': 0,
                    'total_profit_loss': 0.0,
                    'total_capital_used': 0.0,
                    'win_rate': 0.0,
                    'results': []
                }
            
            # Get historical data for the period (extend by 7 days to cover signal expiration)
            extended_end_date = end_date + timedelta(days=7)
            historical_data = self._get_historical_data(symbol, start_date, extended_end_date)
            
            if historical_data.empty:
                logger.error(f"No historical data found for {symbol.symbol}")
                return {
                    'symbol': symbol.symbol,
                    'total_signals': signals.count(),
                    'executed_signals': 0,
                    'expired_signals': 0,
                    'total_profit_loss': 0.0,
                    'total_capital_used': 0.0,
                    'win_rate': 0.0,
                    'results': [],
                    'error': 'No historical data available'
                }
            
            # Simulate each signal with FIXED logic
            results = []
            executed_count = 0
            expired_count = 0
            total_profit_loss = 0.0
            total_capital_used = 0.0
            winning_trades = 0
            
            for signal in signals:
                result = self._simulate_signal_execution_fixed(signal, historical_data)
                results.append(result)
                
                if result['is_executed']:
                    executed_count += 1
                    total_profit_loss += result['profit_loss_amount']
                    total_capital_used += result['capital_used']
                    
                    if result['profit_loss_amount'] > 0:
                        winning_trades += 1
                else:
                    expired_count += 1
            
            # Calculate win rate
            win_rate = (winning_trades / executed_count * 100) if executed_count > 0 else 0.0
            
            return {
                'symbol': symbol.symbol,
                'total_signals': signals.count(),
                'executed_signals': executed_count,
                'expired_signals': expired_count,
                'total_profit_loss': total_profit_loss,
                'total_capital_used': total_capital_used,
                'win_rate': win_rate,
                'winning_trades': winning_trades,
                'losing_trades': executed_count - winning_trades,
                'results': results,
                'fixes_applied': {
                    'sell_signal_execution': 'FIXED',
                    'target_hit_logic': 'FIXED',
                    'profit_loss_calculation': 'FIXED'
                }
            }
            
        except Exception as e:
            logger.error(f"Error running FIXED backtest for {symbol.symbol}: {e}")
            return {
                'symbol': symbol.symbol,
                'error': f'Backtest failed: {str(e)}',
                'total_signals': 0,
                'executed_signals': 0,
                'expired_signals': 0,
                'total_profit_loss': 0.0,
                'total_capital_used': 0.0,
                'win_rate': 0.0,
                'results': []
            }

    def _simulate_signal_execution_fixed(self, signal: TradingSignal, historical_data) -> dict:
        """FIXED signal execution simulation with correct SELL logic"""
        try:
            # Ensure signal timestamp is UTC
            signal_time = signal.created_at
            if signal_time.tzinfo is None:
                signal_time = signal_time.replace(tzinfo=timezone.utc)
            
            # Calculate position size based on capital
            position_size = Decimal('1000')  # $1000 per trade
            
            entry_price = float(signal.entry_price)
            target_price = float(signal.target_price)
            stop_loss = float(signal.stop_loss)
            signal_type = signal.signal_type.upper()
            
            # 7-day execution window
            execution_window = timedelta(days=7)
            end_time = signal_time + execution_window
            
            logger.info(f"FIXED Signal {signal.id}: {signal_type} Entry=${entry_price:.2f}, Target=${target_price:.2f}, SL=${stop_loss:.2f}")
            
            # Find relevant price data within execution window
            relevant_data = historical_data[
                (historical_data.index >= signal_time) & 
                (historical_data.index <= end_time)
            ].copy()
            
            if relevant_data.empty:
                return {
                    'signal_id': signal.id,
                    'is_executed': False,
                    'execution_status': 'NO_DATA_IN_WINDOW',
                    'executed_at': None,
                    'execution_price': None,
                    'profit_loss_percentage': 0.0,
                    'profit_loss_amount': 0.0,
                    'capital_used': 0.0,
                    'reason': 'No price data available in 7-day window'
                }
            
            # Process each day chronologically to find execution
            execution_price = None
            execution_time = None
            execution_status = 'NOT_EXECUTED'
            
            for timestamp, row in relevant_data.iterrows():
                high_price = float(row['high'])
                low_price = float(row['low'])
                close_price = float(row['close'])
                
                if signal_type in ['BUY', 'STRONG_BUY']:
                    # For BUY signals: check if price hit target (above entry) or stop loss (below entry)
                    if high_price >= target_price:
                        execution_price = target_price
                        execution_time = timestamp
                        execution_status = 'TARGET_HIT'
                        logger.info(f"FIXED BUY Signal {signal.id}: Target hit at ${target_price:.2f}")
                        break
                    elif low_price <= stop_loss:
                        execution_price = stop_loss
                        execution_time = timestamp
                        execution_status = 'STOP_LOSS_HIT'
                        logger.info(f"FIXED BUY Signal {signal.id}: Stop loss hit at ${stop_loss:.2f}")
                        break
                else:  # SELL or STRONG_SELL
                    # FIXED: For SELL signals: check if price hit target (below entry) or stop loss (above entry)
                    if low_price <= target_price:
                        execution_price = target_price  # FIXED: Execute at target price, not market price
                        execution_time = timestamp
                        execution_status = 'TARGET_HIT'
                        logger.info(f"FIXED SELL Signal {signal.id}: Target hit at ${target_price:.2f}")
                        break
                    elif high_price >= stop_loss:
                        execution_price = stop_loss  # FIXED: Execute at stop loss price, not market price
                        execution_time = timestamp
                        execution_status = 'STOP_LOSS_HIT'
                        logger.info(f"FIXED SELL Signal {signal.id}: Stop loss hit at ${stop_loss:.2f}")
                        break
            
            # If no TP/SL hit within 7 days, mark as expired
            if execution_price is None:
                return {
                    'signal_id': signal.id,
                    'is_executed': False,
                    'execution_status': 'EXPIRED_7_DAYS',
                    'executed_at': None,
                    'execution_price': None,
                    'profit_loss_percentage': 0.0,
                    'profit_loss_amount': 0.0,
                    'capital_used': 0.0,
                    'reason': 'Signal expired after 7 days without execution'
                }
            
            # FIXED: Calculate profit/loss correctly
            if signal_type in ['BUY', 'STRONG_BUY']:
                profit_loss_percentage = (execution_price - entry_price) / entry_price * 100
                profit_loss_amount = (execution_price - entry_price) * (position_size / entry_price)
            else:  # SELL or STRONG_SELL
                # FIXED: For SELL signals, profit when execution_price < entry_price
                profit_loss_percentage = (entry_price - execution_price) / entry_price * 100
                profit_loss_amount = (entry_price - execution_price) * (position_size / entry_price)
            
            logger.info(f"FIXED Signal {signal.id} Result: {execution_status}, P&L: {profit_loss_percentage:.2f}%")
            
            return {
                'signal_id': signal.id,
                'is_executed': True,
                'execution_status': execution_status,
                'executed_at': execution_time,
                'execution_price': execution_price,
                'profit_loss_percentage': profit_loss_percentage,
                'profit_loss_amount': float(profit_loss_amount),
                'capital_used': float(position_size),
                'reason': f'FIXED: Executed via {execution_status.lower().replace("_", " ")}'
            }
            
        except Exception as e:
            logger.error(f"Error simulating FIXED signal execution for signal {signal.id}: {e}")
            return {
                'signal_id': signal.id,
                'is_executed': False,
                'execution_status': 'ERROR',
                'executed_at': None,
                'execution_price': None,
                'profit_loss_percentage': 0.0,
                'profit_loss_amount': 0.0,
                'capital_used': 0.0,
                'reason': f'Error: {str(e)}'
            }

    def _get_historical_data(self, symbol: Symbol, start_date: datetime, end_date: datetime):
        """Get historical data for backtesting"""
        try:
            import pandas as pd
            
            market_data = MarketData.objects.filter(
                symbol=symbol,
                timeframe='1h',  # Use 1h data for more granular backtesting
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            if not market_data.exists():
                return pd.DataFrame()
            
            # Convert to DataFrame
            data = []
            for md in market_data:
                data.append({
                    'timestamp': md.timestamp,
                    'open': float(md.open_price),
                    'high': float(md.high_price),
                    'low': float(md.low_price),
                    'close': float(md.close_price),
                    'volume': float(md.volume)
                })
            
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            return df
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return pd.DataFrame()




























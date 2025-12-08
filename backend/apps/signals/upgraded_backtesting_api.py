"""
Upgraded Backtesting API Views with Enhanced Signal Management
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
from apps.signals.upgraded_backtesting_service import upgraded_backtesting_service

logger = logging.getLogger(__name__)

class UpgradedBacktestAPIView(View):
    """Upgraded backtesting API with enhanced signal management"""

    def post(self, request):
        """Run upgraded backtest with enhanced signal management"""
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
            
            # Run upgraded backtest
            logger.info(f"Running upgraded backtest for {symbol_name} from {start_date.date()} to {end_date.date()}")
            
            backtest_results = upgraded_backtesting_service.backtest_signals(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )
            
            # Generate summary
            summary = upgraded_backtesting_service.get_backtest_summary(backtest_results)
            
            # Prepare response
            response_data = {
                'success': True,
                'backtest_results': backtest_results,
                'summary': summary,
                'metadata': {
                    'symbol': symbol_name,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'backtest_timestamp': timezone.now().isoformat(),
                    'upgraded_features': {
                        'signal_expiration_days': 7,
                        'take_profit_percentage': 60,
                        'stop_loss_percentage': 40,
                        'description': 'Signals expire after 7 days, TP=60% of capital, SL=40% of capital'
                    }
                }
            }
            
            logger.info(f"Upgraded backtest completed for {symbol_name}: {backtest_results['total_signals']} signals processed")
            
            return JsonResponse(response_data)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in upgraded backtest API: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Backtest failed: {str(e)}'
            }, status=500)

    def get(self, request):
        """Get backtest configuration and available symbols"""
        try:
            # Get available symbols
            symbols = Symbol.objects.filter(
                symbol_type='CRYPTO', 
                is_active=True
            ).values('symbol', 'name').order_by('symbol')
            
            # Get backtest configuration
            config = {
                'signal_expiration_days': upgraded_backtesting_service.signal_expiration_days,
                'take_profit_percentage': upgraded_backtesting_service.take_profit_percentage,
                'stop_loss_percentage': upgraded_backtesting_service.stop_loss_percentage,
                'position_size_percentage': float(upgraded_backtesting_service.position_size_percentage),
                'initial_capital': float(upgraded_backtesting_service.initial_capital),
                'description': {
                    'signal_expiration': 'Signals expire after 7 days if not executed',
                    'take_profit': 'Fixed 60% take profit of capital',
                    'stop_loss': 'Maximum 40% stop loss of capital',
                    'position_sizing': '10% of capital per trade'
                }
            }
            
            return JsonResponse({
                'success': True,
                'symbols': list(symbols),
                'config': config,
                'features': [
                    '7-day signal expiration window',
                    'Fixed 60% take profit of capital',
                    'Maximum 40% stop loss of capital',
                    'Enhanced signal categorization',
                    'Detailed execution tracking'
                ]
            })
            
        except Exception as e:
            logger.error(f"Error getting backtest config: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to get configuration: {str(e)}'
            }, status=500)

class SignalAnalysisAPIView(View):
    """API for analyzing signal execution patterns"""

    def post(self, request):
        """Analyze signal execution patterns"""
        try:
            data = json.loads(request.body)
            
            symbol_name = data.get('symbol', '').upper()
            days_back = data.get('days_back', 30)
            
            if not symbol_name:
                return JsonResponse({
                    'success': False,
                    'error': 'Symbol parameter required'
                }, status=400)
            
            # Get symbol
            try:
                symbol = Symbol.objects.get(symbol=symbol_name, symbol_type='CRYPTO', is_active=True)
            except Symbol.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Symbol {symbol_name} not found'
                }, status=404)
            
            # Get signals from the last N days
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days_back)
            
            signals = TradingSignal.objects.filter(
                symbol=symbol,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).order_by('-created_at')
            
            # Analyze signal patterns
            analysis = self._analyze_signal_patterns(signals, symbol)
            
            return JsonResponse({
                'success': True,
                'analysis': analysis,
                'period': f'Last {days_back} days',
                'total_signals': signals.count()
            })
            
        except Exception as e:
            logger.error(f"Error in signal analysis: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Analysis failed: {str(e)}'
            }, status=500)

    def _analyze_signal_patterns(self, signals, symbol):
        """Analyze signal execution patterns"""
        try:
            total_signals = signals.count()
            
            if total_signals == 0:
                return {
                    'total_signals': 0,
                    'signal_types': {},
                    'execution_patterns': {},
                    'recommendations': ['No signals found in the specified period']
                }
            
            # Analyze by signal type
            signal_types = {}
            for signal in signals:
                signal_type = signal.signal_type
                if signal_type not in signal_types:
                    signal_types[signal_type] = 0
                signal_types[signal_type] += 1
            
            # Get recent backtest results for context
            end_date = timezone.now()
            start_date = end_date - timedelta(days=30)
            
            backtest_results = upgraded_backtesting_service.backtest_signals(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )
            
            # Generate recommendations
            recommendations = []
            
            if backtest_results['expired_signals'] > backtest_results['executed_signals']:
                recommendations.append("High signal expiration rate - consider adjusting entry criteria")
            
            if backtest_results['win_rate'] < 50:
                recommendations.append("Low win rate - review take profit and stop loss levels")
            
            if backtest_results['total_signals'] > 50:
                recommendations.append("High signal frequency - consider filtering for higher quality signals")
            
            return {
                'total_signals': total_signals,
                'signal_types': signal_types,
                'execution_patterns': {
                    'executed_signals': backtest_results['executed_signals'],
                    'expired_signals': backtest_results['expired_signals'],
                    'execution_rate': (backtest_results['executed_signals'] / total_signals * 100) if total_signals > 0 else 0,
                    'win_rate': backtest_results['win_rate']
                },
                'recommendations': recommendations,
                'backtest_summary': upgraded_backtesting_service.get_backtest_summary(backtest_results)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing signal patterns: {e}")
            return {'error': f'Analysis failed: {str(e)}'}




























"""
Improved views for signal generation using the new service
"""

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.cache import cache
import json
import logging

from apps.trading.models import Symbol
from apps.signals.improved_signal_generation_service import generate_improved_signals_for_symbol, improved_signal_service

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class ImprovedSignalGenerationView(View):
    """Improved signal generation API endpoint"""
    
    def post(self, request):
        """Generate improved signals for a symbol or all symbols"""
        try:
            data = json.loads(request.body)
            symbol_name = data.get('symbol')
            generate_all = data.get('generate_all', False)
            
            if not symbol_name and not generate_all:
                return JsonResponse({
                    'success': False,
                    'error': 'Either symbol name or generate_all must be provided'
                }, status=400)
            
            if generate_all:
                return self._generate_signals_for_all_symbols()
            else:
                return self._generate_signals_for_symbol(symbol_name)
                
        except Exception as e:
            logger.error(f"Error in improved signal generation: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _generate_signals_for_symbol(self, symbol_name: str):
        """Generate signals for a specific symbol"""
        try:
            result = generate_improved_signals_for_symbol(symbol_name)
            
            if result['success']:
                # Clear relevant caches
                self._clear_signal_caches(symbol_name)
                
                return JsonResponse({
                    'success': True,
                    'symbol': symbol_name,
                    'signals_generated': result['signals_generated'],
                    'signal_ids': result['signal_ids'],
                    'message': f"Generated {result['signals_generated']} improved signals for {symbol_name}"
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error']
                }, status=404)
                
        except Exception as e:
            logger.error(f"Error generating signals for {symbol_name}: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _generate_signals_for_all_symbols(self):
        """Generate signals for all major cryptocurrencies"""
        try:
            # Define major cryptocurrencies to process
            major_symbols = [
                'BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOGE', 'MATIC', 'DOT', 'AVAX',
                'LINK', 'UNI', 'ATOM', 'LTC', 'BCH', 'XLM', 'ADAUSDT', 'AVAXUSDT', 
                'BTCUSDT', 'ETHUSDT', 'AAVEUSDT', 'LINKUSDT'
            ]
            
            results = []
            total_signals = 0
            
            for symbol_name in major_symbols:
                try:
                    symbol = Symbol.objects.get(symbol__iexact=symbol_name, is_active=True)
                    signals = improved_signal_service.generate_signals_for_symbol(symbol)
                    
                    results.append({
                        'symbol': symbol_name,
                        'signals_generated': len(signals),
                        'success': True
                    })
                    total_signals += len(signals)
                    
                except Symbol.DoesNotExist:
                    results.append({
                        'symbol': symbol_name,
                        'signals_generated': 0,
                        'success': False,
                        'error': 'Symbol not found'
                    })
                except Exception as e:
                    results.append({
                        'symbol': symbol_name,
                        'signals_generated': 0,
                        'success': False,
                        'error': str(e)
                    })
            
            # Clear all signal caches
            self._clear_all_signal_caches()
            
            return JsonResponse({
                'success': True,
                'total_signals_generated': total_signals,
                'symbols_processed': len(major_symbols),
                'results': results,
                'message': f"Generated {total_signals} signals across {len(major_symbols)} symbols"
            })
            
        except Exception as e:
            logger.error(f"Error generating signals for all symbols: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _clear_signal_caches(self, symbol_name: str = None):
        """Clear signal-related caches"""
        try:
            if symbol_name:
                # Clear symbol-specific caches
                cache.delete(f"current_price_{symbol_name}")
                cache.delete(f"sync_prices_{symbol_name}")
                cache.delete(f"signals_api_{symbol_name}_None_true_50")
            else:
                # Clear general signal caches
                cache.delete("signal_statistics")
                cache.delete("signals_api_None_None_true_50")
                
        except Exception as e:
            logger.warning(f"Error clearing caches: {e}")
    
    def _clear_all_signal_caches(self):
        """Clear all signal-related caches"""
        self._clear_signal_caches()
        
        # Clear additional caches
        cache.clear()  # Nuclear option - clear all caches
        logger.info("Cleared all caches after signal generation")


@method_decorator(login_required, name='dispatch')
class SignalQualityCheckView(View):
    """View to check signal quality and identify issues"""
    
    def get(self, request):
        """Get signal quality report"""
        try:
            from apps.signals.models import TradingSignal
            
            # Check for various quality issues
            issues = self._analyze_signal_quality()
            
            return JsonResponse({
                'success': True,
                'signal_quality_report': issues,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error checking signal quality: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _analyze_signal_quality(self):
        """Analyze signals for quality issues"""
        issues = {
            'total_signals': 0,
            'invalid_entry_prices': 0,
            'invalid_targets': 0,
            'impossible_price_ratios': 0,
            'duplicate_signals': 0,
            'examples': []
        }
        
        try:
            from apps.signals.models import TradingSignal
            
            signals = TradingSignal.objects.filter(is_valid=True).order_by('-created_at')[:100]
            issues['total_signals'] = signals.count()
            
            seen_combinations = set()
            
            for signal in signals:
                # Check entry price
                if not signal.entry_price or signal.entry_price <= 0:
                    issues['invalid_entry_prices'] += 1
                    issues['examples'].append({
                        'symbol': signal.symbol.symbol,
                        'issue': 'Invalid entry price',
                        'entry_price': float(signal.entry_price) if signal.entry_price else None
                    })
                
                # Check targets
                if not signal.target_price or signal.target_price <= 0:
                    issues['invalid_signals'] += 1
                
                # Check impossible ratios (targets too far from entry)
                if signal.entry_price and signal.target_price:
                    ratio = float(signal.target_price) / float(signal.entry_price)
                    if ratio > 5.0 or ratio < 0.2:  # More than 5x or less than 0.2x
                        issues['impossible_price_ratios'] += 1
                        if len(issues['examples']) < 10:
                            issues['examples'].append({
                                'symbol': signal.symbol.symbol,
                                'issue': 'Impossible price ratio',
                                'entry_price': float(signal.entry_price),
                                'target_price': float(signal.target_price),
                                'ratio': ratio
                            })
                
                # Check for duplicates
                combo = f"{signal.symbol.symbol}_{signal.signal_type.name}_{signal.entry_price}"
                if combo in seen_combinations:
                    issues['duplicate_signals'] += 1
                else:
                    seen_combinations.add(combo)
            
            return issues
            
        except Exception as e:
            logger.error(f"Error analyzing signal quality: {e}")
            return {'error': str(e)}

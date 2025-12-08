"""
Price Synchronization Service for Trading Signals

This service ensures price consistency between signal creation and display,
fixing the issue where signals show different prices than expected.
"""

import logging
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class PriceSyncService:
    """
    Service to synchronize prices between signal creation and display
    """
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.price_history_cache_timeout = 3600  # 1 hour
        
    def get_synchronized_prices(self, symbol: str) -> Dict:
        """
        Get synchronized prices for a symbol, ensuring consistency
        """
        try:
            # Try to get from cache first
            cache_key = f"sync_prices_{symbol}"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                logger.debug(f"Returning cached synchronized prices for {symbol}")
                return cached_data
            
            # Get live prices
            live_prices = self._get_live_prices(symbol)
            
            # Get historical prices from signals
            historical_prices = self._get_historical_prices(symbol)
            
            # Synchronize prices
            synchronized_data = self._synchronize_price_data(symbol, live_prices, historical_prices)
            
            # Cache the synchronized data
            cache.set(cache_key, synchronized_data, self.cache_timeout)
            
            return synchronized_data
            
        except Exception as e:
            logger.error(f"Error getting synchronized prices for {symbol}: {e}")
            return self._get_fallback_prices(symbol)
    
    def _get_live_prices(self, symbol: str) -> Dict:
        """Get live prices from external APIs"""
        try:
            from apps.data.real_price_service import get_live_prices
            live_prices = get_live_prices()
            
            # Handle USDT pairs (e.g., BTCUSDT -> BTC)
            base_symbol = symbol
            if symbol.endswith('USDT'):
                base_symbol = symbol[:-4]  # Remove 'USDT'
            
            if base_symbol in live_prices:
                return live_prices[base_symbol]
            elif symbol in live_prices:
                return live_prices[symbol]
            else:
                logger.warning(f"No live price data found for {symbol} (tried {base_symbol})")
                return {}
                
        except Exception as e:
            logger.error(f"Error fetching live prices for {symbol}: {e}")
            return {}
    
    def _get_historical_prices(self, symbol: str) -> Dict:
        """Get historical prices from recent signals"""
        try:
            from apps.signals.models import TradingSignal
            from apps.trading.models import Symbol
            
            # Get the symbol object
            try:
                symbol_obj = Symbol.objects.get(symbol__iexact=symbol)
            except Symbol.DoesNotExist:
                return {}
            
            # Get recent signals for this symbol
            recent_signals = TradingSignal.objects.filter(
                symbol=symbol_obj,
                is_valid=True
            ).order_by('-created_at')[:10]
            
            if not recent_signals:
                return {}
            
            # Calculate average prices from recent signals
            entry_prices = [float(signal.entry_price) for signal in recent_signals if signal.entry_price]
            target_prices = [float(signal.target_price) for signal in recent_signals if signal.target_price]
            stop_losses = [float(signal.stop_loss) for signal in recent_signals if signal.stop_loss]
            
            historical_data = {
                'avg_entry_price': sum(entry_prices) / len(entry_prices) if entry_prices else 0,
                'avg_target_price': sum(target_prices) / len(target_prices) if target_prices else 0,
                'avg_stop_loss': sum(stop_losses) / len(stop_losses) if stop_losses else 0,
                'last_signal_price': float(recent_signals[0].entry_price) if recent_signals[0].entry_price else 0,
                'last_signal_time': recent_signals[0].created_at.isoformat(),
                'signal_count': len(recent_signals)
            }
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error getting historical prices for {symbol}: {e}")
            return {}
    
    def _synchronize_price_data(self, symbol: str, live_prices: Dict, historical_prices: Dict) -> Dict:
        """Synchronize live and historical price data"""
        try:
            current_price = live_prices.get('price', 0)
            price_change_24h = live_prices.get('change_24h', 0)
            volume_24h = live_prices.get('volume_24h', 0)
            
            # Get historical data
            last_signal_price = historical_prices.get('last_signal_price', 0)
            avg_entry_price = historical_prices.get('avg_entry_price', 0)
            signal_count = historical_prices.get('signal_count', 0)
            
            # Calculate price consistency metrics
            price_discrepancy = 0
            if current_price > 0 and last_signal_price > 0:
                price_discrepancy = abs(current_price - last_signal_price) / last_signal_price * 100
            
            # Determine price reliability
            price_reliability = self._calculate_price_reliability(
                current_price, last_signal_price, signal_count
            )
            
            synchronized_data = {
                'symbol': symbol,
                'current_price': current_price,
                'price_change_24h': price_change_24h,
                'volume_24h': volume_24h,
                'last_signal_price': last_signal_price,
                'avg_entry_price': avg_entry_price,
                'price_discrepancy_percent': round(price_discrepancy, 2),
                'price_reliability': price_reliability,
                'signal_count': signal_count,
                'last_updated': timezone.now().isoformat(),
                'data_source': 'synchronized',
                'price_status': self._get_price_status(price_discrepancy, price_reliability)
            }
            
            # Add price alerts if there are significant discrepancies
            if price_discrepancy > 5:  # 5% threshold
                synchronized_data['price_alert'] = {
                    'type': 'PRICE_DISCREPANCY',
                    'message': f'Price discrepancy detected: {price_discrepancy:.1f}%',
                    'severity': 'warning' if price_discrepancy < 10 else 'critical'
                }
            
            return synchronized_data
            
        except Exception as e:
            logger.error(f"Error synchronizing price data for {symbol}: {e}")
            return self._get_fallback_prices(symbol)
    
    def _calculate_price_reliability(self, current_price: float, last_signal_price: float, signal_count: int) -> str:
        """Calculate price reliability score"""
        try:
            if current_price <= 0 or last_signal_price <= 0:
                return 'unknown'
            
            # Calculate price stability
            price_change = abs(current_price - last_signal_price) / last_signal_price * 100
            
            # Factor in signal count (more signals = more reliable)
            signal_factor = min(1.0, signal_count / 10.0)
            
            if price_change < 2 and signal_factor > 0.5:
                return 'high'
            elif price_change < 5 and signal_factor > 0.3:
                return 'medium'
            elif price_change < 10:
                return 'low'
            else:
                return 'very_low'
                
        except Exception as e:
            logger.warning(f"Error calculating price reliability: {e}")
            return 'unknown'
    
    def _get_price_status(self, price_discrepancy: float, price_reliability: str) -> str:
        """Get overall price status"""
        if price_reliability == 'high' and price_discrepancy < 2:
            return 'stable'
        elif price_reliability in ['high', 'medium'] and price_discrepancy < 5:
            return 'moderate'
        elif price_discrepancy < 10:
            return 'volatile'
        else:
            return 'unreliable'
    
    def _get_fallback_prices(self, symbol: str) -> Dict:
        """Get fallback prices when synchronization fails"""
        return {
            'symbol': symbol,
            'current_price': 0,
            'price_change_24h': 0,
            'volume_24h': 0,
            'last_signal_price': 0,
            'avg_entry_price': 0,
            'price_discrepancy_percent': 0,
            'price_reliability': 'unknown',
            'signal_count': 0,
            'last_updated': timezone.now().isoformat(),
            'data_source': 'fallback',
            'price_status': 'unavailable',
            'error': 'Price synchronization failed'
        }
    
    def update_signal_prices(self, signal_id: int) -> bool:
        """Update prices for a specific signal"""
        try:
            from apps.signals.models import TradingSignal
            
            signal = TradingSignal.objects.get(id=signal_id)
            symbol = signal.symbol.symbol
            
            # Get synchronized prices
            sync_prices = self.get_synchronized_prices(symbol)
            
            if sync_prices.get('current_price', 0) > 0:
                # Update signal with current price if it's significantly different
                current_price = Decimal(str(sync_prices['current_price']))
                
                if signal.entry_price and abs(float(current_price - signal.entry_price) / float(signal.entry_price)) > 0.01:
                    # Price changed by more than 1%, update the signal
                    signal.entry_price = current_price
                    
                    # Recalculate targets based on new entry price
                    if signal.signal_type.name in ['BUY', 'STRONG_BUY']:
                        signal.target_price = current_price * Decimal('1.05')
                        signal.stop_loss = current_price * Decimal('0.97')
                    else:
                        signal.target_price = current_price * Decimal('0.95')
                        signal.stop_loss = current_price * Decimal('1.03')
                    
                    # Recalculate risk-reward ratio
                    risk = abs(float(signal.entry_price - signal.stop_loss))
                    reward = abs(float(signal.target_price - signal.entry_price))
                    signal.risk_reward_ratio = reward / risk if risk > 0 else 0
                    
                    signal.save()
                    logger.info(f"Updated signal {signal_id} prices for {symbol}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating signal prices for signal {signal_id}: {e}")
            return False
    
    def get_price_summary(self, symbols: list = None) -> Dict:
        """Get price summary for multiple symbols"""
        try:
            if not symbols:
                # Get all symbols with recent signals
                from apps.trading.models import Symbol
                symbols = list(Symbol.objects.values_list('symbol', flat=True))
            
            summary = {
                'total_symbols': len(symbols),
                'synchronized_symbols': 0,
                'price_alerts': [],
                'last_updated': timezone.now().isoformat()
            }
            
            for symbol in symbols:
                try:
                    sync_data = self.get_synchronized_prices(symbol)
                    
                    if sync_data.get('data_source') == 'synchronized':
                        summary['synchronized_symbols'] += 1
                    
                    # Check for price alerts
                    if 'price_alert' in sync_data:
                        summary['price_alerts'].append({
                            'symbol': symbol,
                            'alert': sync_data['price_alert']
                        })
                        
                except Exception as e:
                    logger.warning(f"Error processing symbol {symbol}: {e}")
                    continue
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting price summary: {e}")
            return {'error': str(e)}


# Global instance
price_sync_service = PriceSyncService()

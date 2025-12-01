"""
Fixed Backtesting Service for Accurate Stop Loss Verification
This service ensures accurate verification of stop loss hits using proper Futures data and UTC timezone handling.
"""

import logging
from datetime import datetime, timezone as dt_timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from apps.trading.models import Symbol
from apps.data.models import MarketData
from apps.signals.models import TradingSignal

logger = logging.getLogger(__name__)

class FixedBacktestingService:
    """Fixed backtesting service with accurate stop loss verification using Futures data"""

    def __init__(self):
        self.take_profit_percentage = 0.15  # 15% take profit
        self.stop_loss_percentage = 0.08    # 8% stop loss

    def verify_signal_execution(self, signal: TradingSignal) -> Dict:
        """
        Verify signal execution using accurate Futures data and proper timezone handling
        
        Args:
            signal: TradingSignal to verify
            
        Returns:
            Dict with execution details
        """
        try:
            # Ensure signal timestamp is UTC
            signal_date = signal.created_at
            if signal_date.tzinfo is None:
                signal_date = signal_date.replace(tzinfo=dt_timezone.utc)
            
            # Get the exact day's data (UTC day boundary)
            day_start = signal_date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            # Fetch market data for the signal day
            market_data = MarketData.objects.filter(
                symbol=signal.symbol,
                timestamp__gte=day_start,
                timestamp__lt=day_end,
                timeframe='1d'  # Use daily candles for verification
            ).first()
            
            if not market_data:
                logger.error(f"No market data found for {signal.symbol.symbol} on {signal_date.date()}")
                return {
                    'executed': False,
                    'reason': 'No market data',
                    'execution_price': None,
                    'execution_time': None,
                    'status': 'NOT_EXECUTED'
                }
            
            # Verify stop loss and take profit using the day's OHLC
            entry_price = float(signal.entry_price)
            stop_loss = float(signal.stop_loss)
            target_price = float(signal.target_price)
            
            day_high = float(market_data.high_price)
            day_low = float(market_data.low_price)
            day_close = float(market_data.close_price)
            
            logger.info(f"Verifying signal {signal.id}: Entry=${entry_price:.2f}, SL=${stop_loss:.2f}, Target=${target_price:.2f}")
            logger.info(f"Day OHLC: O=${market_data.open_price} H=${day_high:.2f} L=${day_low:.2f} C=${day_close:.2f}")
            
            # Check execution based on signal type
            if signal.signal_type in ['BUY', 'STRONG_BUY']:
                # For buy signals: check if target hit first, then stop loss
                if day_high >= target_price:
                    return {
                        'executed': True,
                        'reason': 'Target hit',
                        'execution_price': target_price,
                        'execution_time': market_data.timestamp,
                        'status': 'TARGET_HIT',
                        'pnl': (target_price - entry_price) / entry_price * 100
                    }
                elif day_low <= stop_loss:
                    return {
                        'executed': True,
                        'reason': 'Stop loss hit',
                        'execution_price': stop_loss,
                        'execution_time': market_data.timestamp,
                        'status': 'STOP_LOSS_HIT',
                        'pnl': (stop_loss - entry_price) / entry_price * 100
                    }
                else:
                    # No execution, close at end of day
                    return {
                        'executed': True,
                        'reason': 'End of day close',
                        'execution_price': day_close,
                        'execution_time': market_data.timestamp,
                        'status': 'END_OF_DAY',
                        'pnl': (day_close - entry_price) / entry_price * 100
                    }
                    
            else:  # SELL or STRONG_SELL
                # For sell signals: check if target hit first, then stop loss
                if day_low <= target_price:
                    return {
                        'executed': True,
                        'reason': 'Target hit',
                        'execution_price': target_price,
                        'execution_time': market_data.timestamp,
                        'status': 'TARGET_HIT',
                        'pnl': (entry_price - target_price) / entry_price * 100
                    }
                elif day_high >= stop_loss:
                    return {
                        'executed': True,
                        'reason': 'Stop loss hit',
                        'execution_price': stop_loss,
                        'execution_time': market_data.timestamp,
                        'status': 'STOP_LOSS_HIT',
                        'pnl': (entry_price - stop_loss) / entry_price * 100
                    }
                else:
                    # No execution, close at end of day
                    return {
                        'executed': True,
                        'reason': 'End of day close',
                        'execution_price': day_close,
                        'execution_time': market_data.timestamp,
                        'status': 'END_OF_DAY',
                        'pnl': (entry_price - day_close) / entry_price * 100
                    }
                    
        except Exception as e:
            logger.error(f"Error verifying signal execution: {e}")
            return {
                'executed': False,
                'reason': f'Error: {str(e)}',
                'execution_price': None,
                'execution_time': None,
                'status': 'ERROR'
            }

    def verify_all_signals(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Verify all signals for a symbol in a date range
        
        Args:
            symbol: Symbol to verify
            start_date: Start date (UTC)
            end_date: End date (UTC)
            
        Returns:
            List of verification results
        """
        try:
            # Ensure dates are UTC
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=dt_timezone.utc)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=dt_timezone.utc)
            
            # Get signals in date range
            signals = TradingSignal.objects.filter(
                symbol=symbol,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).order_by('created_at')
            
            results = []
            for signal in signals:
                verification = self.verify_signal_execution(signal)
                verification['signal_id'] = signal.id
                verification['signal_date'] = signal.created_at
                verification['signal_type'] = signal.signal_type
                verification['entry_price'] = float(signal.entry_price)
                verification['stop_loss'] = float(signal.stop_loss)
                verification['target_price'] = float(signal.target_price)
                results.append(verification)
            
            return results
            
        except Exception as e:
            logger.error(f"Error verifying signals: {e}")
            return []

    def verify_specific_signal(self, signal_id: int) -> Dict:
        """
        Verify a specific signal by ID
        
        Args:
            signal_id: ID of the signal to verify
            
        Returns:
            Verification result
        """
        try:
            signal = TradingSignal.objects.get(id=signal_id)
            verification = self.verify_signal_execution(signal)
            verification['signal_id'] = signal.id
            verification['signal_date'] = signal.created_at
            verification['signal_type'] = signal.signal_type
            verification['entry_price'] = float(signal.entry_price)
            verification['stop_loss'] = float(signal.stop_loss)
            verification['target_price'] = float(signal.target_price)
            return verification
            
        except TradingSignal.DoesNotExist:
            return {
                'executed': False,
                'reason': 'Signal not found',
                'execution_price': None,
                'execution_time': None,
                'status': 'NOT_FOUND'
            }
        except Exception as e:
            logger.error(f"Error verifying specific signal: {e}")
            return {
                'executed': False,
                'reason': f'Error: {str(e)}',
                'execution_price': None,
                'execution_time': None,
                'status': 'ERROR'
            }



































"""
Upgraded Backtesting Service with Enhanced Signal Management
- 7-day signal expiration window
- Fixed 60% take profit of capital
- Maximum 40% stop loss of capital
"""

import logging
from datetime import datetime, timezone as dt_timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
import pandas as pd

from apps.trading.models import Symbol
from apps.data.models import MarketData
from apps.signals.models import TradingSignal

logger = logging.getLogger(__name__)

class UpgradedBacktestingService:
    """Upgraded backtesting service with enhanced signal management"""

    def __init__(self):
        # Your specific requirements
        self.signal_expiration_days = 7  # 7-day signal expiration
        self.take_profit_percentage = 0.60  # 60% take profit of capital
        self.stop_loss_percentage = 0.40    # 40% maximum stop loss of capital
        
        # Capital management
        self.initial_capital = Decimal('10000')  # Starting capital
        self.position_size_percentage = Decimal('0.10')  # 10% of capital per trade

    def simulate_signal_execution(self, signal: TradingSignal, historical_data: pd.DataFrame) -> Dict:
        """
        Simulate execution of a single signal with upgraded logic
        
        Args:
            signal: TradingSignal to simulate
            historical_data: Historical price data
            
        Returns:
            Dict with execution details
        """
        try:
            # Ensure signal timestamp is UTC
            signal_time = signal.created_at
            if signal_time.tzinfo is None:
                signal_time = signal_time.replace(tzinfo=dt_timezone.utc)
            
            # Calculate position size based on capital
            current_capital = self.initial_capital  # In real implementation, track current capital
            position_size = current_capital * self.position_size_percentage
            
            entry_price = float(signal.entry_price)
            signal_type = signal.signal_type.upper()
            
            # Calculate take profit and stop loss based on capital percentages
            if signal_type in ['BUY', 'STRONG_BUY']:
                # For buy signals: TP = entry + (60% of capital), SL = entry - (40% of capital)
                take_profit_price = entry_price + (entry_price * self.take_profit_percentage)
                stop_loss_price = entry_price - (entry_price * self.stop_loss_percentage)
            else:  # SELL or STRONG_SELL
                # For sell signals: TP = entry - (60% of capital), SL = entry + (40% of capital)
                take_profit_price = entry_price - (entry_price * self.take_profit_percentage)
                stop_loss_price = entry_price + (entry_price * self.stop_loss_percentage)
            
            # 7-day execution window
            execution_window = timedelta(days=self.signal_expiration_days)
            end_time = signal_time + execution_window
            
            logger.info(f"Signal {signal.id}: Entry=${entry_price:.2f}, TP=${take_profit_price:.2f}, SL=${stop_loss_price:.2f}")
            logger.info(f"Execution window: {signal_time.date()} to {end_time.date()}")
            
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
                    'take_profit_price': take_profit_price,
                    'stop_loss_price': stop_loss_price,
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
                    # Check take profit first (higher priority)
                    if high_price >= take_profit_price:
                        execution_price = take_profit_price
                        execution_time = timestamp
                        execution_status = 'TAKE_PROFIT_HIT'
                        break
                    # Then check stop loss
                    elif low_price <= stop_loss_price:
                        execution_price = stop_loss_price
                        execution_time = timestamp
                        execution_status = 'STOP_LOSS_HIT'
                        break
                else:  # SELL or STRONG_SELL
                    # Check take profit first (lower price for sell)
                    if low_price <= take_profit_price:
                        execution_price = take_profit_price
                        execution_time = timestamp
                        execution_status = 'TAKE_PROFIT_HIT'
                        break
                    # Then check stop loss
                    elif high_price >= stop_loss_price:
                        execution_price = stop_loss_price
                        execution_time = timestamp
                        execution_status = 'STOP_LOSS_HIT'
                        break
            
            # If no TP/SL hit within 7 days, mark as expired
            if execution_price is None:
                return {
                    'signal_id': signal.id,
                    'is_executed': False,
                    'execution_status': 'EXPIRED_7_DAYS',
                    'executed_at': None,
                    'execution_price': None,
                    'take_profit_price': take_profit_price,
                    'stop_loss_price': stop_loss_price,
                    'profit_loss_percentage': 0.0,
                    'profit_loss_amount': 0.0,
                    'capital_used': 0.0,
                    'reason': f'Signal expired after {self.signal_expiration_days} days without execution'
                }
            
            # Calculate profit/loss
            if signal_type in ['BUY', 'STRONG_BUY']:
                profit_loss_percentage = (execution_price - entry_price) / entry_price * 100
                profit_loss_amount = (execution_price - entry_price) * (position_size / entry_price)
            else:  # SELL or STRONG_SELL
                profit_loss_percentage = (entry_price - execution_price) / entry_price * 100
                profit_loss_amount = (entry_price - execution_price) * (position_size / entry_price)
            
            return {
                'signal_id': signal.id,
                'is_executed': True,
                'execution_status': execution_status,
                'executed_at': execution_time,
                'execution_price': execution_price,
                'take_profit_price': take_profit_price,
                'stop_loss_price': stop_loss_price,
                'profit_loss_percentage': profit_loss_percentage,
                'profit_loss_amount': float(profit_loss_amount),
                'capital_used': float(position_size),
                'reason': f'Executed via {execution_status.lower().replace("_", " ")}'
            }
            
        except Exception as e:
            logger.error(f"Error simulating signal execution for signal {signal.id}: {e}")
            return {
                'signal_id': signal.id,
                'is_executed': False,
                'execution_status': 'ERROR',
                'executed_at': None,
                'execution_price': None,
                'take_profit_price': None,
                'stop_loss_price': None,
                'profit_loss_percentage': 0.0,
                'profit_loss_amount': 0.0,
                'capital_used': 0.0,
                'reason': f'Error: {str(e)}'
            }

    def backtest_signals(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> Dict:
        """
        Backtest all signals for a symbol in a date range with upgraded logic
        
        Args:
            symbol: Symbol to backtest
            start_date: Start date (UTC)
            end_date: End date (UTC)
            
        Returns:
            Dict with backtest results
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
            extended_end_date = end_date + timedelta(days=self.signal_expiration_days)
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
            
            # Simulate each signal
            results = []
            executed_count = 0
            expired_count = 0
            total_profit_loss = 0.0
            total_capital_used = 0.0
            winning_trades = 0
            
            for signal in signals:
                result = self.simulate_signal_execution(signal, historical_data)
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
                'backtest_settings': {
                    'signal_expiration_days': self.signal_expiration_days,
                    'take_profit_percentage': self.take_profit_percentage,
                    'stop_loss_percentage': self.stop_loss_percentage,
                    'position_size_percentage': float(self.position_size_percentage)
                }
            }
            
        except Exception as e:
            logger.error(f"Error backtesting signals for {symbol.symbol}: {e}")
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

    def _get_historical_data(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get historical data for backtesting"""
        try:
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

    def get_backtest_summary(self, backtest_results: Dict) -> Dict:
        """Generate a summary of backtest results"""
        try:
            total_signals = backtest_results['total_signals']
            executed_signals = backtest_results['executed_signals']
            expired_signals = backtest_results['expired_signals']
            total_profit_loss = backtest_results['total_profit_loss']
            win_rate = backtest_results['win_rate']
            
            # Calculate additional metrics
            execution_rate = (executed_signals / total_signals * 100) if total_signals > 0 else 0
            expiration_rate = (expired_signals / total_signals * 100) if total_signals > 0 else 0
            
            # Calculate average profit per trade
            avg_profit_per_trade = (total_profit_loss / executed_signals) if executed_signals > 0 else 0
            
            return {
                'symbol': backtest_results['symbol'],
                'period': f"{backtest_results.get('start_date', 'N/A')} to {backtest_results.get('end_date', 'N/A')}",
                'total_signals': total_signals,
                'executed_signals': executed_signals,
                'expired_signals': expired_signals,
                'execution_rate': execution_rate,
                'expiration_rate': expiration_rate,
                'total_profit_loss': total_profit_loss,
                'win_rate': win_rate,
                'avg_profit_per_trade': avg_profit_per_trade,
                'backtest_settings': backtest_results.get('backtest_settings', {}),
                'summary_text': self._generate_summary_text(backtest_results)
            }
            
        except Exception as e:
            logger.error(f"Error generating backtest summary: {e}")
            return {'error': f'Summary generation failed: {str(e)}'}

    def _generate_summary_text(self, results: Dict) -> str:
        """Generate human-readable summary text"""
        try:
            symbol = results['symbol']
            total = results['total_signals']
            executed = results['executed_signals']
            expired = results['expired_signals']
            profit_loss = results['total_profit_loss']
            win_rate = results['win_rate']
            
            summary = f"""
Backtest Results for {symbol}:
• Total Signals: {total}
• Executed Signals: {executed} ({executed/total*100:.1f}% execution rate)
• Expired Signals: {expired} ({expired/total*100:.1f}% expiration rate)
• Total P&L: ${profit_loss:.2f}
• Win Rate: {win_rate:.1f}%

Settings Applied:
• Signal Expiration: {self.signal_expiration_days} days
• Take Profit: {self.take_profit_percentage*100:.0f}% of capital
• Stop Loss: {self.stop_loss_percentage*100:.0f}% of capital
            """.strip()
            
            return summary
            
        except Exception as e:
            return f"Error generating summary: {str(e)}"

# Create global instance
upgraded_backtesting_service = UpgradedBacktestingService()




























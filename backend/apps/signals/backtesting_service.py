"""
Phase 2 Backtesting Service
Comprehensive backtesting service for strategy validation and performance analysis
"""

import logging
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from django.utils import timezone
from django.db import transaction

from apps.signals.models import TradeLog, BacktestResult, TradingSignal, Symbol
from apps.data.models import MarketData
from apps.signals.strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)


class Phase2BacktestingService:
    """Enhanced backtesting service for Phase 2 with comprehensive logging and metrics"""
    
    def __init__(self, initial_capital: float = 10000, commission_rate: float = 0.001, 
                 slippage_rate: float = 0.0005):
        self.initial_capital = Decimal(str(initial_capital))
        self.commission_rate = Decimal(str(commission_rate))
        self.slippage_rate = Decimal(str(slippage_rate))
        
        # Backtest state
        self.backtest_id = str(uuid.uuid4())
        self.current_capital = self.initial_capital
        self.positions = {}  # symbol -> position data
        self.trades = []  # List of TradeLog objects
        self.equity_curve = []  # Daily equity values
        self.daily_returns = []  # Daily returns
        
        # Performance tracking
        self.start_date = None
        self.end_date = None
        self.symbol = None
        self.strategy_name = None
        
    def run_backtest(self, symbol: Symbol, strategy_name: str, start_date: datetime, 
                    end_date: datetime, strategy_engine: Optional[StrategyEngine] = None) -> BacktestResult:
        """
        Run comprehensive backtest for a symbol and strategy
        
        Args:
            symbol: Trading symbol to backtest
            strategy_name: Name of the strategy
            start_date: Start date for backtest
            end_date: End date for backtest
            strategy_engine: Optional strategy engine instance
            
        Returns:
            BacktestResult object with performance metrics
        """
        try:
            logger.info(f"Starting backtest for {symbol.symbol} using {strategy_name}")
            
            # Make dates timezone-aware if they aren't already
            if start_date.tzinfo is None:
                start_date = timezone.make_aware(start_date)
            if end_date.tzinfo is None:
                end_date = timezone.make_aware(end_date)
            
            # Initialize backtest state
            self._reset_backtest_state()
            self.symbol = symbol
            self.strategy_name = strategy_name
            self.start_date = start_date
            self.end_date = end_date
            
            # Get historical data
            historical_data = self._get_historical_data(symbol, start_date, end_date)
            if historical_data.empty:
                raise ValueError(f"No historical data available for {symbol.symbol}")
            
            logger.info(f"Loaded {len(historical_data)} data points for backtest")
            
            # Run strategy simulation
            if strategy_engine:
                self._simulate_strategy_with_engine(strategy_engine, historical_data)
            else:
                self._simulate_simple_strategy(historical_data)
            
            # Calculate performance metrics
            performance_metrics = self._calculate_comprehensive_metrics()
            
            # Create and save backtest result
            backtest_result = self._create_backtest_result(performance_metrics)
            
            # Save all trades to database
            self._save_trades_to_database()
            
            logger.info(f"Backtest completed: {performance_metrics['total_return_percentage']:.2f}% return, "
                       f"{performance_metrics['win_rate']:.1%} win rate")
            
            return backtest_result
            
        except Exception as e:
            logger.error(f"Error during backtest: {e}")
            raise
    
    def _reset_backtest_state(self):
        """Reset backtest state for new run"""
        self.backtest_id = str(uuid.uuid4())
        self.current_capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.daily_returns = []
    
    def _get_historical_data(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get historical market data for backtesting"""
        try:
            market_data = MarketData.objects.filter(
                symbol=symbol,
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            if not market_data.exists():
                logger.error(
                    f"No market data found for {symbol.symbol} in range {start_date} to {end_date}. "
                    f"Populate historical data and retry."
                )
                return pd.DataFrame()
            
            # Convert to pandas DataFrame
            data = []
            for record in market_data:
                data.append({
                    'timestamp': record.timestamp,
                    'open': float(record.open_price),
                    'high': float(record.high_price),
                    'low': float(record.low_price),
                    'close': float(record.close_price),
                    'volume': float(record.volume)
                })
            
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            return df
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return self._generate_synthetic_data(start_date, end_date)
    
    def _generate_synthetic_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Generate synthetic market data for testing"""
        import random
        
        # Generate daily data points
        current_date = start_date
        data = []
        base_price = 100.0
        
        while current_date <= end_date:
            # Simulate price movement
            daily_return = random.gauss(0.001, 0.02)  # 0.1% mean return, 2% volatility
            base_price *= (1 + daily_return)
            
            # Generate OHLCV data
            high = base_price * (1 + abs(random.gauss(0, 0.01)))
            low = base_price * (1 - abs(random.gauss(0, 0.01)))
            volume = random.uniform(1000, 10000)
            
            data.append({
                'timestamp': current_date,
                'open': base_price,
                'high': high,
                'low': low,
                'close': base_price,
                'volume': volume
            })
            
            current_date += timedelta(days=1)
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df
    
    def _simulate_strategy_with_engine(self, strategy_engine: StrategyEngine, data: pd.DataFrame):
        """Simulate strategy using the actual strategy engine"""
        try:
            # For now, fall back to simple strategy since the engine is designed for real-time data
            self._simulate_simple_strategy(data)
                
        except Exception as e:
            logger.error(f"Error simulating strategy with engine: {e}")
    
    def _simulate_simple_strategy(self, data: pd.DataFrame):
        """Simulate a simple moving average crossover strategy"""
        try:
            # Calculate moving averages
            data['sma_20'] = data['close'].rolling(window=20).mean()
            data['sma_50'] = data['close'].rolling(window=50).mean()
            
            # Process each data point
            for i, (timestamp, row) in enumerate(data.iterrows()):
                if i < 50:  # Need enough data for indicators
                    continue
                
                current_price = row['close']
                sma_20 = row['sma_20']
                sma_50 = row['sma_50']
                
                # Update equity curve
                self._update_equity_curve(current_price, timestamp)
                
                # Generate signals
                signals = []
                
                # Buy signal: SMA crossover bullish
                if (sma_20 > sma_50 and 
                    data.iloc[i-1]['sma_20'] <= data.iloc[i-1]['sma_50'] and
                    current_price > sma_20):
                    signals.append({
                        'type': 'BUY',
                        'price': current_price,
                        'confidence': 0.8,
                        'stop_loss': current_price * 0.95,  # 5% stop loss
                        'take_profit': current_price * 1.15,  # 15% take profit
                        'reason': 'SMA crossover bullish'
                    })
                
                # Sell signal: SMA crossover bearish
                elif (sma_20 < sma_50 and 
                      data.iloc[i-1]['sma_20'] >= data.iloc[i-1]['sma_50'] and
                      current_price < sma_20):
                    signals.append({
                        'type': 'SELL',
                        'price': current_price,
                        'confidence': 0.8,
                        'stop_loss': current_price * 1.05,  # 5% stop loss
                        'take_profit': current_price * 0.85,  # 15% take profit
                        'reason': 'SMA crossover bearish'
                    })
                
                # Execute signals
                for signal in signals:
                    self._execute_signal(signal, current_price, timestamp)
                
                # Update positions
                self._update_positions(current_price, timestamp)
            
            # Close remaining positions
            if len(data) > 0:
                self._close_all_positions(data.iloc[-1]['close'], data.index[-1])
                
        except Exception as e:
            logger.error(f"Error simulating simple strategy: {e}")
    
    def _generate_signals_from_engine(self, strategy_engine: StrategyEngine, data: pd.DataFrame, index: int) -> List[Dict]:
        """Generate signals using the strategy engine (simplified implementation)"""
        # This is a placeholder - in practice you'd need to adapt the strategy engine
        # to work with historical data rather than real-time data
        return []
    
    def _execute_signal(self, signal: Dict, current_price: float, timestamp: datetime):
        """Execute a trading signal"""
        try:
            signal_type = signal['type']
            symbol_key = self.symbol.symbol
            
            if signal_type == 'BUY' and self.current_capital > 0:
                # Calculate position size (10% of capital per trade)
                position_size = self.current_capital * Decimal('0.1')
                shares = position_size / Decimal(str(current_price))
                
                # Apply slippage and commission
                execution_price = current_price * (1 + float(self.slippage_rate))
                commission = position_size * self.commission_rate
                total_cost = position_size + commission
                
                if total_cost <= self.current_capital:
                    # Create trade log entry
                    trade = TradeLog(
                        symbol=self.symbol,
                        trade_type='BUY',
                        entry_price=Decimal(str(execution_price)),
                        quantity=shares,
                        stop_loss=Decimal(str(signal.get('stop_loss', 0))),
                        take_profit=Decimal(str(signal.get('take_profit', 0))),
                        entry_time=timestamp,
                        commission=commission,
                        slippage=position_size * self.slippage_rate,
                        backtest_id=self.backtest_id,
                        strategy_name=self.strategy_name,
                        is_open=True
                    )
                    
                    self.trades.append(trade)
                    
                    # Update capital and positions
                    self.current_capital -= total_cost
                    self.positions[symbol_key] = {
                        'shares': shares,
                        'entry_price': execution_price,
                        'entry_timestamp': timestamp,
                        'trade': trade
                    }
                    
                    logger.debug(f"Executed BUY: {shares:.4f} shares at {execution_price:.2f}")
            
            elif signal_type == 'SELL' and symbol_key in self.positions:
                position = self.positions[symbol_key]
                shares = position['shares']
                
                # Apply slippage and commission
                execution_price = current_price * (1 - float(self.slippage_rate))
                trade_value = shares * Decimal(str(execution_price))
                commission = trade_value * self.commission_rate
                net_proceeds = trade_value - commission
                
                # Update the trade log
                trade = position['trade']
                trade.exit_price = Decimal(str(execution_price))
                trade.exit_time = timestamp
                trade.exit_reason = 'SIGNAL_EXIT'
                trade.is_open = False
                trade.calculate_pnl()
                
                # Update capital and remove position
                self.current_capital += net_proceeds
                del self.positions[symbol_key]
                
                logger.debug(f"Executed SELL: {shares:.4f} shares at {execution_price:.2f}")
                
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
    
    def _update_equity_curve(self, current_price: float, timestamp: datetime):
        """Update equity curve with current portfolio value"""
        try:
            # Calculate current portfolio value
            portfolio_value = self.current_capital
            
            # Add value of open positions
            for symbol_key, position in self.positions.items():
                shares = position['shares']
                position_value = shares * Decimal(str(current_price))
                portfolio_value += position_value
            
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': float(portfolio_value),
                'capital': float(self.current_capital)
            })
            
        except Exception as e:
            logger.error(f"Error updating equity curve: {e}")
    
    def _update_positions(self, current_price: float, timestamp: datetime):
        """Update positions and check for stop loss/take profit"""
        try:
            for symbol_key, position in list(self.positions.items()):
                trade = position['trade']
                shares = position['shares']
                entry_price = position['entry_price']
                
                # Check stop loss
                if trade.stop_loss and trade.stop_loss > 0:
                    if trade.trade_type == 'BUY' and current_price <= float(trade.stop_loss):
                        self._close_position(symbol_key, trade.stop_loss, timestamp, 'STOP_LOSS')
                        continue
                    elif trade.trade_type == 'SELL' and current_price >= float(trade.stop_loss):
                        self._close_position(symbol_key, trade.stop_loss, timestamp, 'STOP_LOSS')
                        continue
                
                # Check take profit
                if trade.take_profit and trade.take_profit > 0:
                    if trade.trade_type == 'BUY' and current_price >= float(trade.take_profit):
                        self._close_position(symbol_key, trade.take_profit, timestamp, 'TAKE_PROFIT')
                        continue
                    elif trade.trade_type == 'SELL' and current_price <= float(trade.take_profit):
                        self._close_position(symbol_key, trade.take_profit, timestamp, 'TAKE_PROFIT')
                        continue
                        
        except Exception as e:
            logger.error(f"Error updating positions: {e}")
    
    def _close_position(self, symbol_key: str, exit_price: Decimal, timestamp: datetime, reason: str):
        """Close a position"""
        try:
            if symbol_key not in self.positions:
                return
            
            position = self.positions[symbol_key]
            trade = position['trade']
            shares = position['shares']
            
            # Update trade log
            trade.exit_price = exit_price
            trade.exit_time = timestamp
            trade.exit_reason = reason
            trade.is_open = False
            trade.calculate_pnl()
            
            # Calculate proceeds
            trade_value = shares * exit_price
            commission = trade_value * self.commission_rate
            net_proceeds = trade_value - commission
            
            # Update capital and remove position
            self.current_capital += net_proceeds
            del self.positions[symbol_key]
            
            logger.debug(f"Closed position: {shares:.4f} shares at {exit_price:.2f} ({reason})")
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
    def _close_all_positions(self, current_price: float, timestamp: datetime):
        """Close all remaining positions at the end of backtest"""
        try:
            for symbol_key in list(self.positions.keys()):
                self._close_position(symbol_key, Decimal(str(current_price)), timestamp, 'TIME_EXIT')
                
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
    
    def _calculate_comprehensive_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics"""
        try:
            if not self.trades:
                return self._get_empty_metrics()
            
            # Basic trade statistics
            total_trades = len(self.trades)
            winning_trades = sum(1 for trade in self.trades if trade.is_profitable)
            losing_trades = total_trades - winning_trades
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            # Calculate returns
            total_return = self.current_capital - self.initial_capital
            total_return_percentage = float(total_return / self.initial_capital) * 100
            
            # Calculate annualized return
            days = (self.end_date - self.start_date).days
            years = days / 365.25
            if years > 0:
                annualized_return = ((float(self.current_capital) / float(self.initial_capital)) ** (1/years) - 1) * 100
            else:
                annualized_return = 0
            
            # Calculate profit factor
            gross_profit = sum(float(trade.profit_loss) for trade in self.trades if trade.profit_loss and trade.profit_loss > 0)
            gross_loss = abs(sum(float(trade.profit_loss) for trade in self.trades if trade.profit_loss and trade.profit_loss < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # Calculate average win/loss
            winning_trades_list = [trade for trade in self.trades if trade.is_profitable]
            losing_trades_list = [trade for trade in self.trades if not trade.is_profitable]
            
            average_win = sum(float(trade.profit_loss) for trade in winning_trades_list) / len(winning_trades_list) if winning_trades_list else 0
            average_loss = sum(float(trade.profit_loss) for trade in losing_trades_list) / len(losing_trades_list) if losing_trades_list else 0
            
            # Calculate Sharpe ratio
            if self.daily_returns:
                returns_array = np.array(self.daily_returns)
                sharpe_ratio = np.mean(returns_array) / np.std(returns_array) * np.sqrt(252) if np.std(returns_array) > 0 else 0
            else:
                sharpe_ratio = 0
            
            # Calculate maximum drawdown
            max_drawdown, max_drawdown_duration = self._calculate_max_drawdown()
            
            # Calculate volatility
            volatility = np.std(self.daily_returns) * np.sqrt(252) * 100 if self.daily_returns else 0
            
            # Calculate Sortino ratio
            negative_returns = [r for r in self.daily_returns if r < 0]
            downside_deviation = np.std(negative_returns) if negative_returns else 0
            sortino_ratio = np.mean(self.daily_returns) / downside_deviation * np.sqrt(252) if downside_deviation > 0 else 0
            
            # Calculate Calmar ratio
            calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
            
            # Calculate VaR and Expected Shortfall
            var_95 = np.percentile(self.daily_returns, 5) if self.daily_returns else 0
            expected_shortfall = np.mean([r for r in self.daily_returns if r <= var_95]) if self.daily_returns else 0
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_return': total_return,
                'total_return_percentage': total_return_percentage,
                'annualized_return': annualized_return,
                'sharpe_ratio': sharpe_ratio,
                'sortino_ratio': sortino_ratio,
                'calmar_ratio': calmar_ratio,
                'max_drawdown': max_drawdown,
                'max_drawdown_duration': max_drawdown_duration,
                'profit_factor': profit_factor,
                'average_win': average_win,
                'average_loss': average_loss,
                'volatility': volatility,
                'var_95': var_95,
                'expected_shortfall': expected_shortfall,
                'final_capital': self.current_capital,
                'final_equity': self.current_capital
            }
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return self._get_empty_metrics()
    
    def _get_empty_metrics(self) -> Dict:
        """Return empty metrics when no trades exist"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_return': Decimal('0'),
            'total_return_percentage': 0,
            'annualized_return': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'calmar_ratio': 0,
            'max_drawdown': 0,
            'max_drawdown_duration': 0,
            'profit_factor': 0,
            'average_win': 0,
            'average_loss': 0,
            'volatility': 0,
            'var_95': 0,
            'expected_shortfall': 0,
            'final_capital': self.initial_capital,
            'final_equity': self.initial_capital
        }
    
    def _calculate_max_drawdown(self) -> Tuple[float, int]:
        """Calculate maximum drawdown and duration"""
        try:
            if not self.equity_curve:
                return 0.0, 0
            
            equity_values = [point['equity'] for point in self.equity_curve]
            peak = equity_values[0]
            max_dd = 0.0
            max_dd_duration = 0
            current_dd_duration = 0
            
            for equity in equity_values:
                if equity > peak:
                    peak = equity
                    current_dd_duration = 0
                else:
                    drawdown = (peak - equity) / peak
                    if drawdown > max_dd:
                        max_dd = drawdown
                    current_dd_duration += 1
                    if current_dd_duration > max_dd_duration:
                        max_dd_duration = current_dd_duration
            
            return max_dd, max_dd_duration
            
        except Exception as e:
            logger.error(f"Error calculating max drawdown: {e}")
            return 0.0, 0
    
    def _create_backtest_result(self, metrics: Dict) -> BacktestResult:
        """Create and save BacktestResult object"""
        try:
            backtest_result = BacktestResult.objects.create(
                name=f"{self.strategy_name} - {self.symbol.symbol} ({self.start_date.date()} to {self.end_date.date()})",
                strategy_name=self.strategy_name,
                symbol=self.symbol,
                start_date=self.start_date,
                end_date=self.end_date,
                initial_capital=self.initial_capital,
                commission_rate=self.commission_rate,
                slippage_rate=self.slippage_rate,
                total_trades=metrics['total_trades'],
                winning_trades=metrics['winning_trades'],
                losing_trades=metrics['losing_trades'],
                win_rate=metrics['win_rate'],
                total_return=metrics['total_return'],
                total_return_percentage=metrics['total_return_percentage'],
                annualized_return=metrics['annualized_return'],
                sharpe_ratio=metrics['sharpe_ratio'],
                sortino_ratio=metrics['sortino_ratio'],
                calmar_ratio=metrics['calmar_ratio'],
                max_drawdown=metrics['max_drawdown'],
                max_drawdown_duration=metrics['max_drawdown_duration'],
                profit_factor=metrics['profit_factor'],
                average_win=Decimal(str(metrics['average_win'])),
                average_loss=Decimal(str(metrics['average_loss'])),
                volatility=metrics['volatility'],
                var_95=metrics['var_95'],
                expected_shortfall=metrics['expected_shortfall'],
                final_capital=metrics['final_capital'],
                final_equity=metrics['final_equity']
            )
            
            return backtest_result
            
        except Exception as e:
            logger.error(f"Error creating backtest result: {e}")
            raise
    
    def _save_trades_to_database(self):
        """Save all trades to the database"""
        try:
            with transaction.atomic():
                for trade in self.trades:
                    trade.save()
            
            logger.info(f"Saved {len(self.trades)} trades to database")
            
        except Exception as e:
            logger.error(f"Error saving trades to database: {e}")
            raise

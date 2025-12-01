"""
Phase 2 Performance Metrics Service
Comprehensive performance analysis and reporting service
"""

import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from django.db.models import Q, Avg, Count, Sum, Max, Min
from django.utils import timezone

from apps.signals.models import TradeLog, BacktestResult, TradingSignal
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


class PerformanceMetricsService:
    """Comprehensive performance metrics calculation and analysis service"""
    
    def __init__(self):
        self.logger = logger
    
    def calculate_strategy_performance(self, strategy_name: str, 
                                     start_date: Optional[datetime] = None,
                                     end_date: Optional[datetime] = None) -> Dict:
        """
        Calculate comprehensive performance metrics for a specific strategy
        
        Args:
            strategy_name: Name of the strategy to analyze
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dictionary with comprehensive performance metrics
        """
        try:
            # Get all backtests for this strategy
            queryset = BacktestResult.objects.filter(strategy_name=strategy_name)
            
            if start_date:
                queryset = queryset.filter(start_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(end_date__lte=end_date)
            
            backtests = list(queryset)
            
            if not backtests:
                return self._get_empty_performance_metrics()
            
            # Calculate aggregate metrics
            total_backtests = len(backtests)
            profitable_backtests = sum(1 for bt in backtests if bt.is_profitable)
            
            # Returns
            returns = [bt.total_return_percentage for bt in backtests if bt.total_return_percentage is not None]
            avg_return = np.mean(returns) if returns else 0
            median_return = np.median(returns) if returns else 0
            std_return = np.std(returns) if returns else 0
            
            # Win rates
            win_rates = [bt.win_rate for bt in backtests if bt.win_rate is not None]
            avg_win_rate = np.mean(win_rates) if win_rates else 0
            
            # Sharpe ratios
            sharpe_ratios = [bt.sharpe_ratio for bt in backtests if bt.sharpe_ratio is not None]
            avg_sharpe = np.mean(sharpe_ratios) if sharpe_ratios else 0
            
            # Drawdowns
            drawdowns = [bt.max_drawdown for bt in backtests if bt.max_drawdown is not None]
            avg_drawdown = np.mean(drawdowns) if drawdowns else 0
            max_drawdown = np.max(drawdowns) if drawdowns else 0
            
            # Profit factors
            profit_factors = [bt.profit_factor for bt in backtests if bt.profit_factor is not None]
            avg_profit_factor = np.mean(profit_factors) if profit_factors else 0
            
            # Trade statistics
            total_trades = sum(bt.total_trades for bt in backtests)
            avg_trades_per_backtest = total_trades / total_backtests if total_backtests > 0 else 0
            
            # Risk metrics
            volatilities = [bt.volatility for bt in backtests if bt.volatility is not None]
            avg_volatility = np.mean(volatilities) if volatilities else 0
            
            # Calculate consistency metrics
            positive_periods = sum(1 for ret in returns if ret > 0)
            consistency_ratio = positive_periods / len(returns) if returns else 0
            
            # Calculate risk-adjusted metrics
            risk_adjusted_return = avg_return / (1 + abs(avg_drawdown)) if avg_drawdown != 0 else avg_return
            
            return {
                'strategy_name': strategy_name,
                'total_backtests': total_backtests,
                'profitable_backtests': profitable_backtests,
                'profitability_ratio': profitable_backtests / total_backtests if total_backtests > 0 else 0,
                
                # Return metrics
                'avg_return': avg_return,
                'median_return': median_return,
                'std_return': std_return,
                'min_return': np.min(returns) if returns else 0,
                'max_return': np.max(returns) if returns else 0,
                
                # Performance metrics
                'avg_win_rate': avg_win_rate,
                'avg_sharpe_ratio': avg_sharpe,
                'avg_profit_factor': avg_profit_factor,
                'avg_drawdown': avg_drawdown,
                'max_drawdown': max_drawdown,
                'avg_volatility': avg_volatility,
                
                # Trade metrics
                'total_trades': total_trades,
                'avg_trades_per_backtest': avg_trades_per_backtest,
                
                # Risk metrics
                'consistency_ratio': consistency_ratio,
                'risk_adjusted_return': risk_adjusted_return,
                
                # Analysis period
                'analysis_start': min(bt.start_date for bt in backtests) if backtests else None,
                'analysis_end': max(bt.end_date for bt in backtests) if backtests else None,
                
                # Performance rating
                'performance_rating': self._calculate_performance_rating(avg_return, avg_sharpe, avg_drawdown, consistency_ratio)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating strategy performance: {e}")
            return self._get_empty_performance_metrics()
    
    def calculate_symbol_performance(self, symbol: Symbol,
                                   start_date: Optional[datetime] = None,
                                   end_date: Optional[datetime] = None) -> Dict:
        """
        Calculate performance metrics for a specific symbol across all strategies
        
        Args:
            symbol: Symbol to analyze
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dictionary with symbol performance metrics
        """
        try:
            # Get all backtests for this symbol
            queryset = BacktestResult.objects.filter(symbol=symbol)
            
            if start_date:
                queryset = queryset.filter(start_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(end_date__lte=end_date)
            
            backtests = list(queryset)
            
            if not backtests:
                return self._get_empty_performance_metrics()
            
            # Group by strategy
            strategy_performance = {}
            for backtest in backtests:
                strategy_name = backtest.strategy_name
                if strategy_name not in strategy_performance:
                    strategy_performance[strategy_name] = []
                strategy_performance[strategy_name].append(backtest)
            
            # Calculate metrics for each strategy
            strategy_metrics = {}
            for strategy_name, strategy_backtests in strategy_performance.items():
                strategy_metrics[strategy_name] = self._calculate_backtest_group_metrics(strategy_backtests)
            
            # Calculate overall symbol metrics
            all_returns = [bt.total_return_percentage for bt in backtests if bt.total_return_percentage is not None]
            all_win_rates = [bt.win_rate for bt in backtests if bt.win_rate is not None]
            all_sharpe_ratios = [bt.sharpe_ratio for bt in backtests if bt.sharpe_ratio is not None]
            
            return {
                'symbol': {
                    'symbol': symbol.symbol,
                    'name': symbol.name
                },
                'total_backtests': len(backtests),
                'strategies_tested': len(strategy_performance),
                'avg_return': np.mean(all_returns) if all_returns else 0,
                'avg_win_rate': np.mean(all_win_rates) if all_win_rates else 0,
                'avg_sharpe_ratio': np.mean(all_sharpe_ratios) if all_sharpe_ratios else 0,
                'strategy_performance': strategy_metrics,
                'best_strategy': max(strategy_metrics.keys(), 
                                   key=lambda k: strategy_metrics[k]['avg_return']) if strategy_metrics else None,
                'worst_strategy': min(strategy_metrics.keys(), 
                                    key=lambda k: strategy_metrics[k]['avg_return']) if strategy_metrics else None
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating symbol performance: {e}")
            return self._get_empty_performance_metrics()
    
    def calculate_portfolio_performance(self, start_date: Optional[datetime] = None,
                                      end_date: Optional[datetime] = None) -> Dict:
        """
        Calculate overall portfolio performance across all strategies and symbols
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dictionary with portfolio performance metrics
        """
        try:
            # Get all backtests
            queryset = BacktestResult.objects.all()
            
            if start_date:
                queryset = queryset.filter(start_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(end_date__lte=end_date)
            
            backtests = list(queryset)
            
            if not backtests:
                return self._get_empty_performance_metrics()
            
            # Calculate overall metrics
            total_backtests = len(backtests)
            profitable_backtests = sum(1 for bt in backtests if bt.is_profitable)
            
            # Returns
            returns = [bt.total_return_percentage for bt in backtests if bt.total_return_percentage is not None]
            avg_return = np.mean(returns) if returns else 0
            median_return = np.median(returns) if returns else 0
            
            # Win rates
            win_rates = [bt.win_rate for bt in backtests if bt.win_rate is not None]
            avg_win_rate = np.mean(win_rates) if win_rates else 0
            
            # Sharpe ratios
            sharpe_ratios = [bt.sharpe_ratio for bt in backtests if bt.sharpe_ratio is not None]
            avg_sharpe = np.mean(sharpe_ratios) if sharpe_ratios else 0
            
            # Drawdowns
            drawdowns = [bt.max_drawdown for bt in backtests if bt.max_drawdown is not None]
            avg_drawdown = np.mean(drawdowns) if drawdowns else 0
            
            # Strategy analysis
            strategy_counts = {}
            strategy_returns = {}
            
            for backtest in backtests:
                strategy_name = backtest.strategy_name
                if strategy_name not in strategy_counts:
                    strategy_counts[strategy_name] = 0
                    strategy_returns[strategy_name] = []
                
                strategy_counts[strategy_name] += 1
                if backtest.total_return_percentage is not None:
                    strategy_returns[strategy_name].append(backtest.total_return_percentage)
            
            # Symbol analysis
            symbol_counts = {}
            symbol_returns = {}
            
            for backtest in backtests:
                symbol_name = backtest.symbol.symbol
                if symbol_name not in symbol_counts:
                    symbol_counts[symbol_name] = 0
                    symbol_returns[symbol_name] = []
                
                symbol_counts[symbol_name] += 1
                if backtest.total_return_percentage is not None:
                    symbol_returns[symbol_name].append(backtest.total_return_percentage)
            
            # Calculate strategy performance
            strategy_performance = {}
            for strategy_name, strategy_return_list in strategy_returns.items():
                strategy_performance[strategy_name] = {
                    'count': strategy_counts[strategy_name],
                    'avg_return': np.mean(strategy_return_list),
                    'total_return': np.sum(strategy_return_list)
                }
            
            # Calculate symbol performance
            symbol_performance = {}
            for symbol_name, symbol_return_list in symbol_returns.items():
                symbol_performance[symbol_name] = {
                    'count': symbol_counts[symbol_name],
                    'avg_return': np.mean(symbol_return_list),
                    'total_return': np.sum(symbol_return_list)
                }
            
            return {
                'total_backtests': total_backtests,
                'profitable_backtests': profitable_backtests,
                'profitability_ratio': profitable_backtests / total_backtests if total_backtests > 0 else 0,
                
                # Overall metrics
                'avg_return': avg_return,
                'median_return': median_return,
                'avg_win_rate': avg_win_rate,
                'avg_sharpe_ratio': avg_sharpe,
                'avg_drawdown': avg_drawdown,
                
                # Strategy analysis
                'total_strategies': len(strategy_performance),
                'strategy_performance': strategy_performance,
                'best_strategy': max(strategy_performance.keys(), 
                                   key=lambda k: strategy_performance[k]['avg_return']) if strategy_performance else None,
                
                # Symbol analysis
                'total_symbols': len(symbol_performance),
                'symbol_performance': symbol_performance,
                'best_symbol': max(symbol_performance.keys(), 
                                 key=lambda k: symbol_performance[k]['avg_return']) if symbol_performance else None,
                
                # Analysis period
                'analysis_start': min(bt.start_date for bt in backtests) if backtests else None,
                'analysis_end': max(bt.end_date for bt in backtests) if backtests else None
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio performance: {e}")
            return self._get_empty_performance_metrics()
    
    def get_performance_trends(self, days: int = 30) -> Dict:
        """
        Get performance trends over the last N days
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend analysis
        """
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Get recent backtests
            recent_backtests = BacktestResult.objects.filter(
                created_at__gte=start_date
            ).order_by('created_at')
            
            if not recent_backtests.exists():
                return {'trends': [], 'summary': 'No recent backtests'}
            
            # Group by day
            daily_performance = {}
            for backtest in recent_backtests:
                day = backtest.created_at.date()
                if day not in daily_performance:
                    daily_performance[day] = []
                daily_performance[day].append(backtest)
            
            # Calculate daily metrics
            trends = []
            for day, day_backtests in sorted(daily_performance.items()):
                returns = [bt.total_return_percentage for bt in day_backtests if bt.total_return_percentage is not None]
                win_rates = [bt.win_rate for bt in day_backtests if bt.win_rate is not None]
                
                trends.append({
                    'date': day.isoformat(),
                    'backtests_count': len(day_backtests),
                    'avg_return': np.mean(returns) if returns else 0,
                    'avg_win_rate': np.mean(win_rates) if win_rates else 0,
                    'total_trades': sum(bt.total_trades for bt in day_backtests)
                })
            
            # Calculate trend summary
            if trends:
                recent_returns = [t['avg_return'] for t in trends[-7:]]  # Last 7 days
                overall_returns = [t['avg_return'] for t in trends]
                
                trend_direction = 'improving' if np.mean(recent_returns) > np.mean(overall_returns) else 'declining'
                
                return {
                    'trends': trends,
                    'summary': {
                        'trend_direction': trend_direction,
                        'recent_avg_return': np.mean(recent_returns),
                        'overall_avg_return': np.mean(overall_returns),
                        'days_analyzed': len(trends)
                    }
                }
            else:
                return {'trends': [], 'summary': 'No data available'}
                
        except Exception as e:
            self.logger.error(f"Error calculating performance trends: {e}")
            return {'trends': [], 'summary': 'Error calculating trends'}
    
    def _calculate_backtest_group_metrics(self, backtests: List[BacktestResult]) -> Dict:
        """Calculate metrics for a group of backtests"""
        if not backtests:
            return {}
        
        returns = [bt.total_return_percentage for bt in backtests if bt.total_return_percentage is not None]
        win_rates = [bt.win_rate for bt in backtests if bt.win_rate is not None]
        sharpe_ratios = [bt.sharpe_ratio for bt in backtests if bt.sharpe_ratio is not None]
        
        return {
            'count': len(backtests),
            'avg_return': np.mean(returns) if returns else 0,
            'avg_win_rate': np.mean(win_rates) if win_rates else 0,
            'avg_sharpe_ratio': np.mean(sharpe_ratios) if sharpe_ratios else 0,
            'total_trades': sum(bt.total_trades for bt in backtests)
        }
    
    def _calculate_performance_rating(self, avg_return: float, avg_sharpe: float, 
                                    avg_drawdown: float, consistency: float) -> str:
        """Calculate overall performance rating"""
        score = 0
        
        # Return score (0-40 points)
        if avg_return > 20:
            score += 40
        elif avg_return > 10:
            score += 30
        elif avg_return > 5:
            score += 20
        elif avg_return > 0:
            score += 10
        
        # Sharpe ratio score (0-30 points)
        if avg_sharpe > 2:
            score += 30
        elif avg_sharpe > 1.5:
            score += 25
        elif avg_sharpe > 1:
            score += 20
        elif avg_sharpe > 0.5:
            score += 15
        elif avg_sharpe > 0:
            score += 10
        
        # Drawdown score (0-20 points)
        if avg_drawdown < 5:
            score += 20
        elif avg_drawdown < 10:
            score += 15
        elif avg_drawdown < 15:
            score += 10
        elif avg_drawdown < 20:
            score += 5
        
        # Consistency score (0-10 points)
        if consistency > 0.8:
            score += 10
        elif consistency > 0.6:
            score += 8
        elif consistency > 0.4:
            score += 5
        elif consistency > 0.2:
            score += 3
        
        # Rating based on total score
        if score >= 90:
            return 'Excellent'
        elif score >= 80:
            return 'Very Good'
        elif score >= 70:
            return 'Good'
        elif score >= 60:
            return 'Average'
        elif score >= 50:
            return 'Below Average'
        else:
            return 'Poor'
    
    def _get_empty_performance_metrics(self) -> Dict:
        """Return empty performance metrics structure"""
        return {
            'total_backtests': 0,
            'profitable_backtests': 0,
            'profitability_ratio': 0,
            'avg_return': 0,
            'avg_win_rate': 0,
            'avg_sharpe_ratio': 0,
            'avg_drawdown': 0,
            'performance_rating': 'No Data'
        }


"""
Coin Performance Analyzer
Analyzes each signal individually and calculates total profit percentage per coin
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q

from apps.trading.models import Symbol
from apps.signals.models import TradingSignal
from apps.data.models import MarketData

logger = logging.getLogger(__name__)

class CoinPerformanceAnalyzer:
    """Analyzes individual signals and calculates profit percentage per coin"""
    
    def __init__(self):
        self.analysis_date = timezone.now()
    
    def analyze_coin_signals(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> Dict:
        """Analyze all signals for a specific coin with individual status"""
        try:
            # Get all backtesting signals for this symbol
            signals = TradingSignal.objects.filter(
                symbol=symbol,
                metadata__is_backtesting=True,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).select_related('signal_type').order_by('created_at')
            
            if not signals.exists():
                return self._empty_coin_analysis(symbol)
            
            # Analyze each signal individually
            signal_details = []
            total_investment = Decimal('0')
            total_profit_loss = Decimal('0')
            
            for signal in signals:
                signal_analysis = self._analyze_individual_signal(signal)
                signal_details.append(signal_analysis)
                
                # Calculate total investment and profit/loss
                if signal.entry_price:
                    total_investment += signal.entry_price
                
                if signal.profit_loss:
                    total_profit_loss += signal.profit_loss
            
            # Calculate total profit percentage
            total_profit_percentage = 0
            if total_investment > 0:
                total_profit_percentage = (total_profit_loss / total_investment) * 100
            
            # Count signal statuses
            profit_count = sum(1 for s in signal_details if s['status'] == 'PROFIT')
            loss_count = sum(1 for s in signal_details if s['status'] == 'LOSS')
            not_opened_count = sum(1 for s in signal_details if s['status'] == 'NOT_OPENED')
            
            return {
                'symbol': symbol.symbol,
                'symbol_name': symbol.name,
                'analysis_date': self.analysis_date.strftime('%Y-%m-%d %H:%M:%S'),
                'period': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'days': (end_date - start_date).days
                },
                'total_summary': {
                    'total_signals': len(signal_details),
                    'profit_signals': profit_count,
                    'loss_signals': loss_count,
                    'not_opened_signals': not_opened_count,
                    'total_investment': float(total_investment),
                    'total_profit_loss': float(total_profit_loss),
                    'total_profit_percentage': round(float(total_profit_percentage), 2)
                },
                'individual_signals': signal_details
            }
            
        except Exception as e:
            logger.error(f"Error analyzing coin signals for {symbol.symbol}: {e}")
            return self._empty_coin_analysis(symbol)
    
    def _analyze_individual_signal(self, signal: TradingSignal) -> Dict:
        """Analyze individual signal status"""
        try:
            # Determine signal status
            if not signal.is_executed:
                status = 'NOT_OPENED'
                profit_loss_amount = 0
                profit_loss_percentage = 0
            elif signal.profit_loss is not None:
                if signal.profit_loss > 0:
                    status = 'PROFIT'
                else:
                    status = 'LOSS'
                profit_loss_amount = float(signal.profit_loss)
                
                # Calculate profit/loss percentage
                if signal.entry_price and signal.entry_price > 0:
                    profit_loss_percentage = (signal.profit_loss / signal.entry_price) * 100
                else:
                    profit_loss_percentage = 0
            else:
                status = 'UNKNOWN'
                profit_loss_amount = 0
                profit_loss_percentage = 0
            
            return {
                'signal_id': signal.id,
                'date': signal.created_at.strftime('%Y-%m-%d'),
                'time': signal.created_at.strftime('%H:%M:%S'),
                'signal_type': signal.signal_type.name if signal.signal_type else 'N/A',
                'entry_price': float(signal.entry_price) if signal.entry_price else 0,
                'target_price': float(signal.target_price) if signal.target_price else 0,
                'stop_loss': float(signal.stop_loss) if signal.stop_loss else 0,
                'execution_price': float(signal.execution_price) if signal.execution_price else 0,
                'is_executed': signal.is_executed,
                'status': status,
                'profit_loss_amount': profit_loss_amount,
                'profit_loss_percentage': round(profit_loss_percentage, 2),
                'confidence_score': float(signal.confidence_score) if signal.confidence_score else 0,
                'risk_reward_ratio': float(signal.risk_reward_ratio) if signal.risk_reward_ratio else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing individual signal {signal.id}: {e}")
            return {
                'signal_id': signal.id,
                'date': signal.created_at.strftime('%Y-%m-%d'),
                'time': signal.created_at.strftime('%H:%M:%S'),
                'signal_type': 'ERROR',
                'entry_price': 0,
                'target_price': 0,
                'stop_loss': 0,
                'execution_price': 0,
                'is_executed': False,
                'status': 'ERROR',
                'profit_loss_amount': 0,
                'profit_loss_percentage': 0,
                'confidence_score': 0,
                'risk_reward_ratio': 0
            }
    
    def _empty_coin_analysis(self, symbol: Symbol) -> Dict:
        """Return empty analysis for coin with no signals"""
        return {
            'symbol': symbol.symbol,
            'symbol_name': symbol.name,
            'analysis_date': self.analysis_date.strftime('%Y-%m-%d %H:%M:%S'),
            'period': {'start_date': '', 'end_date': '', 'days': 0},
            'total_summary': {
                'total_signals': 0,
                'profit_signals': 0,
                'loss_signals': 0,
                'not_opened_signals': 0,
                'total_investment': 0,
                'total_profit_loss': 0,
                'total_profit_percentage': 0
            },
            'individual_signals': []
        }
    
    def analyze_multiple_coins(self, symbols: List[Symbol], start_date: datetime, end_date: datetime) -> List[Dict]:
        """Analyze multiple coins and return their performance"""
        try:
            analyses = []
            
            for symbol in symbols:
                analysis = self.analyze_coin_signals(symbol, start_date, end_date)
                analyses.append(analysis)
            
            # Sort by total profit percentage (descending)
            analyses.sort(key=lambda x: x['total_summary']['total_profit_percentage'], reverse=True)
            
            return analyses
            
        except Exception as e:
            logger.error(f"Error analyzing multiple coins: {e}")
            return []
    
    def get_strategy_quality_rating(self, analysis: Dict) -> Dict:
        """Get strategy quality rating based on analysis"""
        try:
            summary = analysis['total_summary']
            total_signals = summary['total_signals']
            
            if total_signals == 0:
                return {
                    'quality_score': 0,
                    'quality_rating': 'No Data',
                    'recommendation': 'No signals generated for analysis'
                }
            
            # Calculate metrics
            profit_rate = (summary['profit_signals'] / total_signals * 100) if total_signals > 0 else 0
            execution_rate = ((summary['profit_signals'] + summary['loss_signals']) / total_signals * 100) if total_signals > 0 else 0
            profit_percentage = summary['total_profit_percentage']
            
            # Calculate quality score (0-100)
            quality_score = 0
            
            # Execution rate component (30% weight)
            quality_score += min(execution_rate, 100) * 0.3
            
            # Profit rate component (40% weight)
            quality_score += min(profit_rate, 100) * 0.4
            
            # Profitability component (30% weight)
            if profit_percentage > 0:
                quality_score += min(profit_percentage * 2, 30)  # Cap at 30 points
            
            quality_score = min(quality_score, 100)
            
            # Get rating and recommendation
            quality_rating = self._get_quality_rating(quality_score)
            recommendation = self._get_strategy_recommendation(quality_score, profit_percentage)
            
            return {
                'quality_score': round(quality_score, 2),
                'quality_rating': quality_rating,
                'recommendation': recommendation,
                'metrics': {
                    'profit_rate': round(profit_rate, 2),
                    'execution_rate': round(execution_rate, 2),
                    'profit_percentage': round(profit_percentage, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating strategy quality: {e}")
            return {
                'quality_score': 0,
                'quality_rating': 'Error',
                'recommendation': 'Error calculating strategy quality',
                'metrics': {'profit_rate': 0, 'execution_rate': 0, 'profit_percentage': 0}
            }
    
    def _get_quality_rating(self, score: float) -> str:
        """Get quality rating based on score"""
        if score >= 80:
            return "Excellent"
        elif score >= 70:
            return "Good"
        elif score >= 60:
            return "Fair"
        elif score >= 40:
            return "Poor"
        else:
            return "Very Poor"
    
    def _get_strategy_recommendation(self, score: float, profit_percentage: float) -> str:
        """Get strategy recommendation based on quality score and profit percentage"""
        if score >= 80 and profit_percentage > 10:
            return "Strategy is performing excellently. Consider increasing position sizes."
        elif score >= 70 and profit_percentage > 5:
            return "Strategy is performing well. Monitor and continue using."
        elif score >= 60 and profit_percentage > 0:
            return "Strategy needs improvement. Review entry/exit criteria."
        elif score >= 40:
            return "Strategy requires significant optimization. Consider major changes."
        else:
            return "Strategy is not profitable. Major overhaul required."


"""
Timeframe Analysis Service for Trading Signals

This service analyzes different timeframes to identify optimal entry points
and provides detailed analysis for backtesting and trading decisions.
"""

import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import numpy as np

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator

logger = logging.getLogger(__name__)


class TimeframeAnalysisService:
    """Service for analyzing different timeframes and identifying entry points"""
    
    def __init__(self):
        self.timeframes = {
            '1M': timedelta(minutes=1),
            '5M': timedelta(minutes=5),
            '15M': timedelta(minutes=15),
            '30M': timedelta(minutes=30),
            '1H': timedelta(hours=1),
            '4H': timedelta(hours=4),
            '1D': timedelta(days=1),
            '1W': timedelta(weeks=1),
            '1MONTH': timedelta(days=30),
        }
        
        self.entry_point_patterns = {
            'SUPPORT_BREAK': self._analyze_support_break,
            'RESISTANCE_BREAK': self._analyze_resistance_break,
            'SUPPORT_BOUNCE': self._analyze_support_bounce,
            'RESISTANCE_REJECTION': self._analyze_resistance_rejection,
            'BREAKOUT': self._analyze_breakout,
            'BREAKDOWN': self._analyze_breakdown,
            'MEAN_REVERSION': self._analyze_mean_reversion,
            'TREND_FOLLOWING': self._analyze_trend_following,
            'CONSOLIDATION_BREAK': self._analyze_consolidation_break,
            'VOLUME_SPIKE': self._analyze_volume_spike,
            'PATTERN_COMPLETION': self._analyze_pattern_completion,
            'INDICATOR_CROSSOVER': self._analyze_indicator_crossover,
        }
    
    def analyze_timeframe(self, symbol: Symbol, timeframe: str, current_price: float) -> Dict:
        """
        Analyze a specific timeframe for entry opportunities
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe to analyze (1M, 5M, 1H, etc.)
            current_price: Current market price
            
        Returns:
            Dict containing timeframe analysis and entry points
        """
        try:
            logger.info(f"Analyzing {timeframe} timeframe for {symbol.symbol}")
            
            # Get market data for the specified timeframe
            market_data = self._get_timeframe_data(symbol, timeframe)
            if not market_data:
                return self._get_empty_analysis(timeframe)
            
            # Analyze price action and patterns
            price_analysis = self._analyze_price_action(market_data, current_price)
            
            # Identify entry points
            entry_points = self._identify_entry_points(market_data, price_analysis, current_price)
            
            # Calculate timeframe-specific metrics
            timeframe_metrics = self._calculate_timeframe_metrics(market_data, timeframe)
            
            analysis = {
                'timeframe': timeframe,
                'symbol': symbol.symbol,
                'current_price': current_price,
                'analysis_timestamp': timezone.now().isoformat(),
                'price_analysis': price_analysis,
                'entry_points': entry_points,
                'timeframe_metrics': timeframe_metrics,
                'recommended_timeframe': self._get_recommended_timeframe(entry_points),
                'entry_confidence': self._calculate_entry_confidence(entry_points, timeframe_metrics)
            }
            
            logger.info(f"Completed {timeframe} analysis for {symbol.symbol}: {len(entry_points)} entry points found")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing {timeframe} timeframe for {symbol.symbol}: {e}")
            return self._get_empty_analysis(timeframe)
    
    def get_multi_timeframe_analysis(self, symbol: Symbol, current_price: float) -> Dict:
        """
        Get analysis across multiple timeframes for comprehensive entry point identification
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            
        Returns:
            Dict containing analysis for all timeframes
        """
        try:
            logger.info(f"Starting multi-timeframe analysis for {symbol.symbol}")
            
            multi_timeframe_analysis = {}
            all_entry_points = []
            
            # Analyze each timeframe
            for timeframe in ['15M', '1H', '4H', '1D']:
                analysis = self.analyze_timeframe(symbol, timeframe, current_price)
                multi_timeframe_analysis[timeframe] = analysis
                
                # Collect entry points from all timeframes
                if analysis.get('entry_points'):
                    all_entry_points.extend(analysis['entry_points'])
            
            # Find confluence points across timeframes
            confluence_analysis = self._analyze_timeframe_confluence(multi_timeframe_analysis, current_price)
            
            # Generate final recommendation
            final_recommendation = self._generate_final_recommendation(
                multi_timeframe_analysis, 
                confluence_analysis, 
                current_price
            )
            
            result = {
                'symbol': symbol.symbol,
                'current_price': current_price,
                'analysis_timestamp': timezone.now().isoformat(),
                'timeframe_analyses': multi_timeframe_analysis,
                'confluence_analysis': confluence_analysis,
                'final_recommendation': final_recommendation,
                'total_entry_points': len(all_entry_points),
                'high_confidence_entries': len([ep for ep in all_entry_points if ep.get('confidence', 0) > 0.8])
            }
            
            logger.info(f"Multi-timeframe analysis completed for {symbol.symbol}: {len(all_entry_points)} total entry points")
            return result
            
        except Exception as e:
            logger.error(f"Error in multi-timeframe analysis for {symbol.symbol}: {e}")
            return {'error': str(e)}
    
    def _get_timeframe_data(self, symbol: Symbol, timeframe: str) -> Optional[List[Dict]]:
        """Get market data for specific timeframe"""
        try:
            # Calculate lookback period based on timeframe
            if timeframe == '1M':
                lookback = 100  # 100 minutes
            elif timeframe == '5M':
                lookback = 200   # 200 5-minute candles
            elif timeframe == '15M':
                lookback = 300   # 300 15-minute candles
            elif timeframe == '30M':
                lookback = 400   # 400 30-minute candles
            elif timeframe == '1H':
                lookback = 500   # 500 hourly candles
            elif timeframe == '4H':
                lookback = 300   # 300 4-hour candles
            elif timeframe == '1D':
                lookback = 200   # 200 daily candles
            else:
                lookback = 100
            
            # Get market data for specific timeframe
            market_data = MarketData.objects.filter(
                symbol=symbol,
                timeframe=timeframe.lower()
            ).order_by('-timestamp')[:lookback]
            
            if not market_data:
                return None
            
            # Convert to list of dicts
            data_list = []
            for data in reversed(market_data):  # Oldest first
                data_list.append({
                    'timestamp': data.timestamp,
                    'open': float(data.open_price),
                    'high': float(data.high_price),
                    'low': float(data.low_price),
                    'close': float(data.close_price),
                    'volume': float(data.volume)
                })
            
            return data_list
            
        except Exception as e:
            logger.error(f"Error getting timeframe data for {symbol.symbol} {timeframe}: {e}")
            return None
    
    def _analyze_price_action(self, market_data: List[Dict], current_price: float) -> Dict:
        """Analyze price action patterns"""
        try:
            if not market_data or len(market_data) < 20:
                return {}
            
            closes = [d['close'] for d in market_data]
            highs = [d['high'] for d in market_data]
            lows = [d['low'] for d in market_data]
            volumes = [d['volume'] for d in market_data]
            
            # Calculate basic metrics
            sma_20 = np.mean(closes[-20:])
            sma_50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma_20
            
            # Trend analysis
            trend = 'BULLISH' if sma_20 > sma_50 else 'BEARISH' if sma_20 < sma_50 else 'SIDEWAYS'
            
            # Volatility analysis
            volatility = np.std(closes[-20:]) / np.mean(closes[-20:])
            
            # Support and resistance levels
            support_levels = self._find_support_levels(lows, closes)
            resistance_levels = self._find_resistance_levels(highs, closes)
            
            # Volume analysis
            avg_volume = np.mean(volumes[-20:])
            current_volume = volumes[-1] if volumes else 0
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            return {
                'trend': trend,
                'sma_20': sma_20,
                'sma_50': sma_50,
                'volatility': volatility,
                'support_levels': support_levels,
                'resistance_levels': resistance_levels,
                'volume_ratio': volume_ratio,
                'price_position': (current_price - min(lows)) / (max(highs) - min(lows)) if max(highs) > min(lows) else 0.5
            }
            
        except Exception as e:
            logger.error(f"Error analyzing price action: {e}")
            return {}
    
    def _identify_entry_points(self, market_data: List[Dict], price_analysis: Dict, current_price: float) -> List[Dict]:
        """Identify potential entry points based on analysis"""
        entry_points = []
        
        try:
            # Support and resistance breakouts
            if price_analysis.get('support_levels'):
                for support in price_analysis['support_levels']:
                    if current_price < support * 0.98:  # 2% below support
                        entry_point = self._analyze_support_break(support, current_price, price_analysis)
                        if entry_point:
                            entry_points.append(entry_point)
            
            if price_analysis.get('resistance_levels'):
                for resistance in price_analysis['resistance_levels']:
                    if current_price > resistance * 1.02:  # 2% above resistance
                        entry_point = self._analyze_resistance_break(resistance, current_price, price_analysis)
                        if entry_point:
                            entry_points.append(entry_point)
            
            # Trend following opportunities
            if price_analysis.get('trend') == 'BULLISH':
                entry_point = self._analyze_trend_following('BULLISH', current_price, price_analysis)
                if entry_point:
                    entry_points.append(entry_point)
            
            # Mean reversion opportunities
            if price_analysis.get('price_position', 0.5) > 0.8:  # Near highs
                entry_point = self._analyze_mean_reversion('BEARISH', current_price, price_analysis)
                if entry_point:
                    entry_points.append(entry_point)
            elif price_analysis.get('price_position', 0.5) < 0.2:  # Near lows
                entry_point = self._analyze_mean_reversion('BULLISH', current_price, price_analysis)
                if entry_point:
                    entry_points.append(entry_point)
            
            # Volume-based entries
            if price_analysis.get('volume_ratio', 1) > 1.5:  # High volume
                entry_point = self._analyze_volume_spike(current_price, price_analysis)
                if entry_point:
                    entry_points.append(entry_point)
            
            # Support bounce opportunities
            if price_analysis.get('support_levels'):
                for support in price_analysis['support_levels']:
                    if abs(current_price - support) / support < 0.02:  # Within 2% of support
                        entry_point = self._analyze_support_bounce(support, current_price, price_analysis)
                        if entry_point:
                            entry_points.append(entry_point)
            
            # Resistance rejection opportunities
            if price_analysis.get('resistance_levels'):
                for resistance in price_analysis['resistance_levels']:
                    if abs(current_price - resistance) / resistance < 0.02:  # Within 2% of resistance
                        entry_point = self._analyze_resistance_rejection(resistance, current_price, price_analysis)
                        if entry_point:
                            entry_points.append(entry_point)
            
            # Breakout opportunities
            if price_analysis.get('resistance_levels'):
                entry_point = self._analyze_breakout(current_price, price_analysis)
                if entry_point:
                    entry_points.append(entry_point)
            
            # Breakdown opportunities
            if price_analysis.get('support_levels'):
                entry_point = self._analyze_breakdown(current_price, price_analysis)
                if entry_point:
                    entry_points.append(entry_point)
            
            # Consolidation break opportunities
            if price_analysis.get('volatility', 0) < 0.02:  # Low volatility
                entry_point = self._analyze_consolidation_break(current_price, price_analysis)
                if entry_point:
                    entry_points.append(entry_point)
            
            # Pattern completion opportunities
            entry_point = self._analyze_pattern_completion(current_price, price_analysis)
            if entry_point:
                entry_points.append(entry_point)
            
            # Indicator crossover opportunities
            entry_point = self._analyze_indicator_crossover(current_price, price_analysis)
            if entry_point:
                entry_points.append(entry_point)
            
        except Exception as e:
            logger.error(f"Error identifying entry points: {e}")
        
        return entry_points
    
    def _analyze_support_break(self, support_level: float, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze support break entry point"""
        try:
            break_strength = (support_level - current_price) / support_level
            
            if break_strength > 0.02:  # 2% break
                return {
                    'type': 'SUPPORT_BREAK',
                    'level': support_level,
                    'current_price': current_price,
                    'break_strength': break_strength,
                    'entry_zone_low': current_price * 0.99,
                    'entry_zone_high': current_price * 1.01,
                    'confidence': min(0.9, 0.7 + break_strength * 10),
                    'stop_loss': current_price * 1.05,  # 5% above entry for SELL
                    'target': current_price * 0.85,  # 15% below entry for profit
                    'details': {
                        'break_percentage': f"{break_strength:.2%}",
                        'volume_confirmation': price_analysis.get('volume_ratio', 1) > 1.2,
                        'trend_confirmation': price_analysis.get('trend') == 'BEARISH'
                    }
                }
        except Exception as e:
            logger.error(f"Error analyzing support break: {e}")
        return None
    
    def _analyze_resistance_break(self, resistance_level: float, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze resistance break entry point"""
        try:
            break_strength = (current_price - resistance_level) / resistance_level
            
            if break_strength > 0.02:  # 2% break
                return {
                    'type': 'RESISTANCE_BREAK',
                    'level': resistance_level,
                    'current_price': current_price,
                    'break_strength': break_strength,
                    'entry_zone_low': current_price * 0.99,
                    'entry_zone_high': current_price * 1.01,
                    'confidence': min(0.9, 0.7 + break_strength * 10),
                    'stop_loss': current_price * 0.95,  # 5% below entry for BUY
                    'target': current_price * 1.15,  # 15% above entry for profit
                    'details': {
                        'break_percentage': f"{break_strength:.2%}",
                        'volume_confirmation': price_analysis.get('volume_ratio', 1) > 1.2,
                        'trend_confirmation': price_analysis.get('trend') == 'BULLISH'
                    }
                }
        except Exception as e:
            logger.error(f"Error analyzing resistance break: {e}")
        return None
    
    def _analyze_trend_following(self, trend: str, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze trend following entry point"""
        try:
            if trend == 'BULLISH':
                return {
                    'type': 'TREND_FOLLOWING',
                    'trend': trend,
                    'current_price': current_price,
                    'entry_zone_low': current_price * 0.995,
                    'entry_zone_high': current_price * 1.005,
                    'confidence': 0.75,
                    'stop_loss': current_price * 0.95,  # 5% below entry
                    'target': current_price * 1.15,  # 15% above entry
                    'details': {
                        'sma_20': price_analysis.get('sma_20'),
                        'sma_50': price_analysis.get('sma_50'),
                        'volume_confirmation': price_analysis.get('volume_ratio', 1) > 1.0
                    }
                }
        except Exception as e:
            logger.error(f"Error analyzing trend following: {e}")
        return None
    
    def _analyze_mean_reversion(self, direction: str, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze mean reversion entry point"""
        try:
            sma_20 = price_analysis.get('sma_20', current_price)
            deviation = abs(current_price - sma_20) / sma_20
            
            if deviation > 0.05:  # 5% deviation from mean
                if direction == 'BULLISH':
                    return {
                        'type': 'MEAN_REVERSION',
                        'direction': direction,
                        'current_price': current_price,
                        'mean_price': sma_20,
                        'deviation': deviation,
                        'entry_zone_low': current_price * 0.995,
                        'entry_zone_high': current_price * 1.005,
                        'confidence': min(0.85, 0.6 + deviation * 5),
                    'stop_loss': current_price * 0.95,  # 5% below entry for BUY
                    'target': current_price * 1.15,  # 15% above entry for profit
                        'details': {
                            'deviation_percentage': f"{deviation:.2%}",
                            'mean_price': sma_20,
                            'reversion_target': sma_20
                        }
                    }
                elif direction == 'BEARISH':
                    return {
                        'type': 'MEAN_REVERSION',
                        'direction': direction,
                        'current_price': current_price,
                        'mean_price': sma_20,
                        'deviation': deviation,
                        'entry_zone_low': current_price * 0.995,
                        'entry_zone_high': current_price * 1.005,
                        'confidence': min(0.85, 0.6 + deviation * 5),
                        'stop_loss': current_price * 1.05,  # 5% above entry for SELL
                        'target': current_price * 0.85,  # 15% below entry for profit
                        'details': {
                            'deviation_percentage': f"{deviation:.2%}",
                            'mean_price': sma_20,
                            'reversion_target': sma_20
                        }
                    }
        except Exception as e:
            logger.error(f"Error analyzing mean reversion: {e}")
        return None
    
    def _analyze_volume_spike(self, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze volume spike entry point"""
        try:
            volume_ratio = price_analysis.get('volume_ratio', 1)
            
            if volume_ratio > 1.5:
                return {
                    'type': 'VOLUME_SPIKE',
                    'current_price': current_price,
                    'volume_ratio': volume_ratio,
                    'entry_zone_low': current_price * 0.995,
                    'entry_zone_high': current_price * 1.005,
                    'confidence': min(0.8, 0.5 + (volume_ratio - 1) * 0.6),
                    'stop_loss': current_price * 0.95,  # 5% below entry
                    'target': current_price * 1.15,  # 15% above entry
                    'details': {
                        'volume_multiplier': f"{volume_ratio:.1f}x",
                        'trend': price_analysis.get('trend', 'UNKNOWN')
                    }
                }
        except Exception as e:
            logger.error(f"Error analyzing volume spike: {e}")
        return None
    
    def _analyze_support_bounce(self, support_level: float, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze support bounce entry point"""
        try:
            if current_price >= support_level * 0.98 and current_price <= support_level * 1.02:
                return {
                    'type': 'SUPPORT_BOUNCE',
                    'support_level': support_level,
                    'current_price': current_price,
                    'entry_zone_low': support_level * 0.995,
                    'entry_zone_high': support_level * 1.005,
                    'confidence': 0.8,
                    'stop_loss': current_price * 0.95,  # 5% below entry for BUY
                    'target': current_price * 1.15,  # 15% above entry for profit
                    'details': {
                        'support_level': support_level,
                        'bounce_strength': 'Strong' if price_analysis.get('volume_ratio', 1) > 1.2 else 'Moderate'
                    }
                }
        except Exception as e:
            logger.error(f"Error analyzing support bounce: {e}")
        return None
    
    def _analyze_resistance_rejection(self, resistance_level: float, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze resistance rejection entry point"""
        try:
            if current_price <= resistance_level * 1.02 and current_price >= resistance_level * 0.98:
                return {
                    'type': 'RESISTANCE_REJECTION',
                    'resistance_level': resistance_level,
                    'current_price': current_price,
                    'entry_zone_low': resistance_level * 0.995,
                    'entry_zone_high': resistance_level * 1.005,
                    'confidence': 0.75,
                    'stop_loss': current_price * 1.05,  # 5% above entry for SELL
                    'target': current_price * 0.85,  # 15% below entry for profit
                    'details': {
                        'resistance_level': resistance_level,
                        'rejection_strength': 'Strong' if price_analysis.get('volume_ratio', 1) > 1.2 else 'Moderate'
                    }
                }
        except Exception as e:
            logger.error(f"Error analyzing resistance rejection: {e}")
        return None
    
    def _analyze_breakout(self, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze breakout entry point"""
        try:
            resistance_levels = price_analysis.get('resistance_levels', [])
            if resistance_levels and current_price > max(resistance_levels) * 1.01:
                return {
                    'type': 'BREAKOUT',
                    'breakout_level': max(resistance_levels),
                    'current_price': current_price,
                    'entry_zone_low': current_price * 0.995,
                    'entry_zone_high': current_price * 1.005,
                    'confidence': 0.85,
                    'stop_loss': current_price * 0.95,  # 5% below entry for BUY
                    'target': current_price * 1.15,  # 15% above entry for profit
                    'details': {
                        'breakout_level': max(resistance_levels),
                        'breakout_strength': 'Strong' if price_analysis.get('volume_ratio', 1) > 1.5 else 'Moderate'
                    }
                }
        except Exception as e:
            logger.error(f"Error analyzing breakout: {e}")
        return None
    
    def _analyze_breakdown(self, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze breakdown entry point"""
        try:
            support_levels = price_analysis.get('support_levels', [])
            if support_levels and current_price < min(support_levels) * 0.99:
                return {
                    'type': 'BREAKDOWN',
                    'breakdown_level': min(support_levels),
                    'current_price': current_price,
                    'entry_zone_low': current_price * 0.995,
                    'entry_zone_high': current_price * 1.005,
                    'confidence': 0.85,
                    'stop_loss': current_price * 1.05,  # 5% above entry for SELL
                    'target': current_price * 0.85,  # 15% below entry for profit
                    'details': {
                        'breakdown_level': min(support_levels),
                        'breakdown_strength': 'Strong' if price_analysis.get('volume_ratio', 1) > 1.5 else 'Moderate'
                    }
                }
        except Exception as e:
            logger.error(f"Error analyzing breakdown: {e}")
        return None
    
    def _analyze_consolidation_break(self, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze consolidation break entry point"""
        try:
            volatility = price_analysis.get('volatility', 0)
            if volatility < 0.02:  # Low volatility indicates consolidation
                return {
                    'type': 'CONSOLIDATION_BREAK',
                    'current_price': current_price,
                    'entry_zone_low': current_price * 0.995,
                    'entry_zone_high': current_price * 1.005,
                    'confidence': 0.7,
                    'stop_loss': current_price * 0.95,  # 5% below entry
                    'target': current_price * 1.15,  # 15% above entry
                    'details': {
                        'consolidation_volatility': f"{volatility:.3f}",
                        'break_direction': 'Up' if price_analysis.get('trend') == 'BULLISH' else 'Down'
                    }
                }
        except Exception as e:
            logger.error(f"Error analyzing consolidation break: {e}")
        return None
    
    def _analyze_pattern_completion(self, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze pattern completion entry point"""
        try:
            # Simple pattern detection (can be enhanced)
            return {
                'type': 'PATTERN_COMPLETION',
                'current_price': current_price,
                'entry_zone_low': current_price * 0.995,
                'entry_zone_high': current_price * 1.005,
                'confidence': 0.7,
                'stop_loss': current_price * 0.95,  # 5% below entry
                'target': current_price * 1.15,  # 15% above entry
                'details': {
                    'pattern_type': 'Generic',
                    'completion_strength': 'Moderate'
                }
            }
        except Exception as e:
            logger.error(f"Error analyzing pattern completion: {e}")
        return None
    
    def _analyze_indicator_crossover(self, current_price: float, price_analysis: Dict) -> Optional[Dict]:
        """Analyze indicator crossover entry point"""
        try:
            return {
                'type': 'INDICATOR_CROSSOVER',
                'current_price': current_price,
                'entry_zone_low': current_price * 0.995,
                'entry_zone_high': current_price * 1.005,
                'confidence': 0.75,
                'stop_loss': current_price * 0.95,  # 5% below entry
                'target': current_price * 1.15,  # 15% above entry
                'details': {
                    'indicator_type': 'Moving Average',
                    'crossover_strength': 'Moderate'
                }
            }
        except Exception as e:
            logger.error(f"Error analyzing indicator crossover: {e}")
        return None
    
    def _find_support_levels(self, lows: List[float], closes: List[float]) -> List[float]:
        """Find support levels using pivot points"""
        try:
            if len(lows) < 20:
                return []
            
            support_levels = []
            for i in range(2, len(lows) - 2):
                if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
                    lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                    support_levels.append(lows[i])
            
            # Return unique levels within 1% of each other
            unique_levels = []
            for level in sorted(support_levels):
                if not any(abs(level - existing) / existing < 0.01 for existing in unique_levels):
                    unique_levels.append(level)
            
            return unique_levels[-3:]  # Return last 3 support levels
            
        except Exception as e:
            logger.error(f"Error finding support levels: {e}")
            return []
    
    def _find_resistance_levels(self, highs: List[float], closes: List[float]) -> List[float]:
        """Find resistance levels using pivot points"""
        try:
            if len(highs) < 20:
                return []
            
            resistance_levels = []
            for i in range(2, len(highs) - 2):
                if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
                    highs[i] > highs[i+1] and highs[i] > highs[i+2]):
                    resistance_levels.append(highs[i])
            
            # Return unique levels within 1% of each other
            unique_levels = []
            for level in sorted(resistance_levels):
                if not any(abs(level - existing) / existing < 0.01 for existing in unique_levels):
                    unique_levels.append(level)
            
            return unique_levels[-3:]  # Return last 3 resistance levels
            
        except Exception as e:
            logger.error(f"Error finding resistance levels: {e}")
            return []
    
    def _calculate_timeframe_metrics(self, market_data: List[Dict], timeframe: str) -> Dict:
        """Calculate timeframe-specific metrics"""
        try:
            if not market_data:
                return {}
            
            closes = [d['close'] for d in market_data]
            volumes = [d['volume'] for d in market_data]
            
            # Calculate returns for different periods (guard zero/short samples)
            returns = {}
            for period in [5, 10, 20]:
                if len(closes) >= period and closes[-period] != 0:
                    returns[f'{period}_period'] = (closes[-1] - closes[-period]) / closes[-period]
            
            # Calculate volatility
            if len(closes) >= 20:
                volatility = np.std(closes[-20:]) / np.mean(closes[-20:])
            else:
                volatility = 0
            
            # Volume profile
            avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else (np.mean(volumes) if len(volumes) > 0 else 0)
            volume_trend = ((volumes[-1] - volumes[-5]) / volumes[-5]) if len(volumes) >= 5 and volumes[-5] != 0 and volumes[-5] > 0 else 0
            
            return {
                'returns': returns,
                'volatility': volatility,
                'avg_volume': avg_volume,
                'volume_trend': volume_trend,
                'data_points': len(market_data)
            }
            
        except Exception as e:
            logger.error(f"Error calculating timeframe metrics: {e}")
            return {}
    
    def _analyze_timeframe_confluence(self, multi_timeframe_analysis: Dict, current_price: float) -> Dict:
        """Analyze confluence across different timeframes"""
        try:
            confluence_points = []
            bullish_count = 0
            bearish_count = 0
            
            for timeframe, analysis in multi_timeframe_analysis.items():
                if analysis.get('entry_points'):
                    for entry_point in analysis['entry_points']:
                        if entry_point.get('confidence', 0) > 0.7:
                            if entry_point.get('type') in ['RESISTANCE_BREAK', 'TREND_FOLLOWING']:
                                bullish_count += 1
                            elif entry_point.get('type') in ['SUPPORT_BREAK', 'MEAN_REVERSION']:
                                bearish_count += 1
                            
                            confluence_points.append({
                                'timeframe': timeframe,
                                'entry_point': entry_point,
                                'confidence': entry_point.get('confidence', 0)
                            })
            
            # Determine overall bias
            if bullish_count > bearish_count:
                overall_bias = 'BULLISH'
            elif bearish_count > bullish_count:
                overall_bias = 'BEARISH'
            else:
                overall_bias = 'NEUTRAL'
            
            return {
                'confluence_points': confluence_points,
                'bullish_signals': bullish_count,
                'bearish_signals': bearish_count,
                'overall_bias': overall_bias,
                'total_confluence': len(confluence_points)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing timeframe confluence: {e}")
            return {}
    
    def _get_recommended_timeframe(self, entry_points: List[Dict]) -> str:
        """Get recommended timeframe based on entry points"""
        if not entry_points:
            return '1H'
        
        # Count entry points by timeframe
        timeframe_counts = {}
        for entry_point in entry_points:
            timeframe = entry_point.get('timeframe', '1H')
            timeframe_counts[timeframe] = timeframe_counts.get(timeframe, 0) + 1
        
        # Return timeframe with most entry points
        if timeframe_counts:
            return max(timeframe_counts, key=timeframe_counts.get)
        
        return '1H'
    
    def _calculate_entry_confidence(self, entry_points: List[Dict], timeframe_metrics: Dict) -> float:
        """Calculate overall entry confidence"""
        if not entry_points:
            return 0.0
        
        # Average confidence of all entry points
        avg_confidence = sum(ep.get('confidence', 0) for ep in entry_points) / len(entry_points)
        
        # Adjust based on timeframe metrics
        volatility = timeframe_metrics.get('volatility', 0)
        volume_trend = timeframe_metrics.get('volume_trend', 0)
        
        # Higher volatility and volume trend increase confidence
        confidence_adjustment = min(0.1, volatility * 2 + abs(volume_trend) * 0.1)
        
        return min(1.0, avg_confidence + confidence_adjustment)
    
    def _generate_final_recommendation(self, multi_timeframe_analysis: Dict, confluence_analysis: Dict, current_price: float) -> Dict:
        """Generate final trading recommendation"""
        try:
            overall_bias = confluence_analysis.get('overall_bias', 'NEUTRAL')
            total_confluence = confluence_analysis.get('total_confluence', 0)
            
            if total_confluence == 0:
                return {
                    'action': 'WAIT',
                    'reason': 'No clear entry points identified',
                    'confidence': 0.0
                }
            
            # Determine action based on bias and confluence
            if overall_bias == 'BULLISH' and total_confluence >= 2:
                action = 'BUY'
                reason = f'Strong bullish confluence across {total_confluence} timeframes'
            elif overall_bias == 'BEARISH' and total_confluence >= 2:
                action = 'SELL'
                reason = f'Strong bearish confluence across {total_confluence} timeframes'
            else:
                action = 'WAIT'
                reason = f'Mixed signals across timeframes (bias: {overall_bias})'
            
            # Calculate overall confidence
            confidence = min(0.95, 0.5 + (total_confluence * 0.1))
            
            return {
                'action': action,
                'reason': reason,
                'confidence': confidence,
                'overall_bias': overall_bias,
                'confluence_count': total_confluence,
                'recommended_entry_price': current_price,
                'stop_loss': current_price * 0.60 if action == 'BUY' else current_price * 1.40,
                'target': current_price * 1.60 if action == 'BUY' else current_price * 0.40
            }
            
        except Exception as e:
            logger.error(f"Error generating final recommendation: {e}")
            return {'action': 'ERROR', 'reason': str(e), 'confidence': 0.0}
    
    def _get_empty_analysis(self, timeframe: str) -> Dict:
        """Return empty analysis structure"""
        return {
            'timeframe': timeframe,
            'entry_points': [],
            'timeframe_metrics': {},
            'recommended_timeframe': timeframe,
            'entry_confidence': 0.0
        }

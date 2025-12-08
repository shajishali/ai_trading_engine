"""
Phase 5.3: Multi-Timeframe Entry Point Detection Service
Implements multi-timeframe entry point detection using SMC patterns
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q
from django.db import transaction

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import ChartImage, ChartPattern, EntryPoint

logger = logging.getLogger(__name__)


class MultiTimeframeEntryDetectionService:
    """Service for detecting entry points across multiple timeframes using SMC strategy"""
    
    def __init__(self):
        # Multi-timeframe configuration
        self.timeframes = ['1D', '4H', '1H', '15M']
        self.timeframe_weights = {
            '1D': 0.4,   # Higher timeframe gets more weight
            '4H': 0.3,   # Structure analysis
            '1H': 0.2,   # Entry precision
            '15M': 0.1   # Final confirmation
        }
        
        # Entry point configuration
        self.entry_config = {
            'min_confidence': 0.6,           # Minimum confidence for entry
            'min_timeframe_agreement': 3,    # Minimum timeframes that must agree
            'risk_reward_min': 1.5,         # Minimum risk-reward ratio
            'max_entry_age_hours': 4,       # Maximum age for valid entry
            'volume_confirmation': True,    # Require volume confirmation
            'pattern_confirmation': True     # Require pattern confirmation
        }
        
        # Strategy-specific parameters
        self.strategy_config = {
            'rsi_long_range': (20, 50),      # RSI range for long entries
            'rsi_short_range': (50, 80),     # RSI range for short entries
            'macd_confirmation': True,        # Require MACD confirmation
            'pivot_alignment': True,         # Require pivot point alignment
            'candlestick_confirmation': True  # Require candlestick confirmation
        }
    
    def detect_entry_points_for_symbol(self, symbol: Symbol) -> List[EntryPoint]:
        """
        Detect entry points for a specific symbol using multi-timeframe analysis
        
        Args:
            symbol: Trading symbol to analyze
            
        Returns:
            List of detected entry points
        """
        try:
            logger.info(f"Detecting entry points for {symbol.symbol}")
            
            # Get market data for all timeframes
            timeframe_data = self._get_market_data_for_timeframes(symbol)
            if not timeframe_data:
                logger.warning(f"No market data available for {symbol.symbol}")
                return []
            
            # Analyze each timeframe
            timeframe_analysis = {}
            for timeframe in self.timeframes:
                analysis = self._analyze_timeframe(symbol, timeframe, timeframe_data.get(timeframe))
                if analysis:
                    timeframe_analysis[timeframe] = analysis
            
            if len(timeframe_analysis) < 2:
                logger.warning(f"Insufficient timeframe data for {symbol.symbol}")
                return []
            
            # Detect entry points using multi-timeframe analysis
            entry_points = self._detect_multi_timeframe_entries(symbol, timeframe_analysis)
            
            logger.info(f"Detected {len(entry_points)} entry points for {symbol.symbol}")
            return entry_points
            
        except Exception as e:
            logger.error(f"Error detecting entry points for {symbol.symbol}: {e}")
            return []
    
    def detect_entry_points_for_chart(self, chart_image: ChartImage) -> List[EntryPoint]:
        """
        Detect entry points for a specific chart image
        
        Args:
            chart_image: ChartImage instance to analyze
            
        Returns:
            List of detected entry points
        """
        try:
            logger.info(f"Detecting entry points for chart {chart_image.id}")
            
            # Get patterns for this chart
            patterns = ChartPattern.objects.filter(
                chart_image=chart_image,
                confidence_score__gte=self.entry_config['min_confidence']
            ).order_by('-confidence_score')
            
            if not patterns.exists():
                logger.info(f"No high-confidence patterns found for chart {chart_image.id}")
                return []
            
            # Get market data for this chart
            market_data = self._get_market_data_for_chart(chart_image)
            if not market_data:
                logger.warning(f"No market data available for chart {chart_image.id}")
                return []
            
            # Get technical indicators
            indicators = self._get_technical_indicators(chart_image.symbol, chart_image.timeframe)
            
            # Detect entry points based on patterns and indicators
            entry_points = self._detect_entry_points_from_patterns(
                chart_image, patterns, market_data, indicators
            )
            
            logger.info(f"Detected {len(entry_points)} entry points for chart {chart_image.id}")
            return entry_points
            
        except Exception as e:
            logger.error(f"Error detecting entry points for chart {chart_image.id}: {e}")
            return []
    
    def _get_market_data_for_timeframes(self, symbol: Symbol) -> Dict[str, List[Dict]]:
        """Get market data for all timeframes"""
        try:
            timeframe_data = {}
            
            for timeframe in self.timeframes:
                # Calculate time range based on timeframe
                if timeframe == '1D':
                    lookback_days = 30
                elif timeframe == '4H':
                    lookback_days = 7
                elif timeframe == '1H':
                    lookback_days = 3
                else:  # 15M
                    lookback_days = 1
                
                start_time = timezone.now() - timedelta(days=lookback_days)
                
                market_data = MarketData.objects.filter(
                    symbol=symbol,
                    timestamp__gte=start_time
                ).order_by('timestamp')
                
                if market_data.exists():
                    data_list = []
                    for data in market_data:
                        data_list.append({
                            'timestamp': data.timestamp,
                            'open': float(data.open_price),
                            'high': float(data.high_price),
                            'low': float(data.low_price),
                            'close': float(data.close_price),
                            'volume': float(data.volume)
                        })
                    timeframe_data[timeframe] = data_list
            
            return timeframe_data
            
        except Exception as e:
            logger.error(f"Error getting market data for timeframes: {e}")
            return {}
    
    def _analyze_timeframe(self, symbol: Symbol, timeframe: str, market_data: List[Dict]) -> Optional[Dict]:
        """Analyze a specific timeframe for entry opportunities"""
        try:
            if not market_data or len(market_data) < 10:
                return None
            
            df = pd.DataFrame(market_data)
            
            analysis = {
                'timeframe': timeframe,
                'symbol': symbol.symbol,
                'current_price': df.iloc[-1]['close'],
                'trend': self._determine_trend(df),
                'structure': self._analyze_structure(df),
                'patterns': self._get_timeframe_patterns(symbol, timeframe),
                'indicators': self._get_technical_indicators(symbol, timeframe),
                'support_resistance': self._calculate_support_resistance(df),
                'volume_analysis': self._analyze_volume(df)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing timeframe {timeframe}: {e}")
            return None
    
    def _detect_multi_timeframe_entries(self, symbol: Symbol, timeframe_analysis: Dict[str, Dict]) -> List[EntryPoint]:
        """Detect entry points using multi-timeframe analysis"""
        try:
            entry_points = []
            
            # Get the primary timeframe (1H for entry precision)
            primary_timeframe = '1H'
            if primary_timeframe not in timeframe_analysis:
                logger.warning(f"Primary timeframe {primary_timeframe} not available")
                return []
            
            primary_analysis = timeframe_analysis[primary_timeframe]
            current_price = primary_analysis['current_price']
            
            # Determine overall market bias from higher timeframes
            market_bias = self._determine_market_bias(timeframe_analysis)
            
            # Look for entry opportunities based on market bias
            if market_bias == 'BULLISH':
                entry_points.extend(self._detect_bullish_entries(symbol, timeframe_analysis, current_price))
            elif market_bias == 'BEARISH':
                entry_points.extend(self._detect_bearish_entries(symbol, timeframe_analysis, current_price))
            
            # Filter and validate entry points
            validated_entries = self._validate_entry_points(entry_points, timeframe_analysis)
            
            return validated_entries
            
        except Exception as e:
            logger.error(f"Error in multi-timeframe entry detection: {e}")
            return []
    
    def _detect_bullish_entries(self, symbol: Symbol, timeframe_analysis: Dict[str, Dict], current_price: float) -> List[EntryPoint]:
        """Detect bullish entry points"""
        try:
            entry_points = []
            
            # Check for bullish CHoCH in 4H timeframe
            if '4H' in timeframe_analysis:
                choch_patterns = [p for p in timeframe_analysis['4H']['patterns'] 
                                if p.pattern_type == 'CHOCH' and p.confidence_score >= 0.7]
                
                if choch_patterns:
                    # Check for BOS confirmation in 1H timeframe
                    if '1H' in timeframe_analysis:
                        bos_patterns = [p for p in timeframe_analysis['1H']['patterns'] 
                                      if p.pattern_type == 'BOS' and p.confidence_score >= 0.7]
                        
                        if bos_patterns:
                            # Check for entry confirmation in 15M timeframe
                            if '15M' in timeframe_analysis:
                                entry_confirmation = self._check_entry_confirmation(
                                    timeframe_analysis['15M'], 'BUY'
                                )
                                
                                if entry_confirmation['confirmed']:
                                    # Create bullish entry point
                                    entry_point = self._create_entry_point(
                                        symbol=symbol,
                                        entry_type='BUY',
                                        entry_price=current_price,
                                        confidence_score=entry_confirmation['confidence'],
                                        timeframe_analysis=timeframe_analysis,
                                        pattern_context='CHOCH_BOS_CONFIRMATION'
                                    )
                                    
                                    if entry_point:
                                        entry_points.append(entry_point)
            
            # Check for Order Block entries
            order_block_entries = self._detect_order_block_entries(symbol, timeframe_analysis, current_price, 'BUY')
            entry_points.extend(order_block_entries)
            
            # Check for FVG entries
            fvg_entries = self._detect_fvg_entries(symbol, timeframe_analysis, current_price, 'BUY')
            entry_points.extend(fvg_entries)
            
            return entry_points
            
        except Exception as e:
            logger.error(f"Error detecting bullish entries: {e}")
            return []
    
    def _detect_bearish_entries(self, symbol: Symbol, timeframe_analysis: Dict[str, Dict], current_price: float) -> List[EntryPoint]:
        """Detect bearish entry points"""
        try:
            entry_points = []
            
            # Check for bearish CHoCH in 4H timeframe
            if '4H' in timeframe_analysis:
                choch_patterns = [p for p in timeframe_analysis['4H']['patterns'] 
                                if p.pattern_type == 'CHOCH' and p.confidence_score >= 0.7]
                
                if choch_patterns:
                    # Check for BOS confirmation in 1H timeframe
                    if '1H' in timeframe_analysis:
                        bos_patterns = [p for p in timeframe_analysis['1H']['patterns'] 
                                      if p.pattern_type == 'BOS' and p.confidence_score >= 0.7]
                        
                        if bos_patterns:
                            # Check for entry confirmation in 15M timeframe
                            if '15M' in timeframe_analysis:
                                entry_confirmation = self._check_entry_confirmation(
                                    timeframe_analysis['15M'], 'SELL'
                                )
                                
                                if entry_confirmation['confirmed']:
                                    # Create bearish entry point
                                    entry_point = self._create_entry_point(
                                        symbol=symbol,
                                        entry_type='SELL',
                                        entry_price=current_price,
                                        confidence_score=entry_confirmation['confidence'],
                                        timeframe_analysis=timeframe_analysis,
                                        pattern_context='CHOCH_BOS_CONFIRMATION'
                                    )
                                    
                                    if entry_point:
                                        entry_points.append(entry_point)
            
            # Check for Order Block entries
            order_block_entries = self._detect_order_block_entries(symbol, timeframe_analysis, current_price, 'SELL')
            entry_points.extend(order_block_entries)
            
            # Check for FVG entries
            fvg_entries = self._detect_fvg_entries(symbol, timeframe_analysis, current_price, 'SELL')
            entry_points.extend(fvg_entries)
            
            return entry_points
            
        except Exception as e:
            logger.error(f"Error detecting bearish entries: {e}")
            return []
    
    def _detect_order_block_entries(self, symbol: Symbol, timeframe_analysis: Dict[str, Dict], 
                                  current_price: float, entry_type: str) -> List[EntryPoint]:
        """Detect Order Block entry points"""
        try:
            entry_points = []
            
            # Look for Order Blocks in 1H timeframe
            if '1H' in timeframe_analysis:
                order_blocks = [p for p in timeframe_analysis['1H']['patterns'] 
                              if p.pattern_type == 'ORDER_BLOCK' and p.confidence_score >= 0.7]
                
                for order_block in order_blocks:
                    # Check if price is near the order block
                    block_low = float(order_block.pattern_price_low)
                    block_high = float(order_block.pattern_price_high)
                    
                    if entry_type == 'BUY' and block_low <= current_price <= block_high * 1.01:
                        # Check for retest confirmation
                        retest_confirmation = self._check_order_block_retest(
                            timeframe_analysis['1H'], order_block, 'BUY'
                        )
                        
                        if retest_confirmation['confirmed']:
                            entry_point = self._create_entry_point(
                                symbol=symbol,
                                entry_type='BUY',
                                entry_price=current_price,
                                confidence_score=retest_confirmation['confidence'],
                                timeframe_analysis=timeframe_analysis,
                                pattern_context='ORDER_BLOCK_RETEST'
                            )
                            
                            if entry_point:
                                entry_points.append(entry_point)
                    
                    elif entry_type == 'SELL' and block_low * 0.99 <= current_price <= block_high:
                        # Check for retest confirmation
                        retest_confirmation = self._check_order_block_retest(
                            timeframe_analysis['1H'], order_block, 'SELL'
                        )
                        
                        if retest_confirmation['confirmed']:
                            entry_point = self._create_entry_point(
                                symbol=symbol,
                                entry_type='SELL',
                                entry_price=current_price,
                                confidence_score=retest_confirmation['confidence'],
                                timeframe_analysis=timeframe_analysis,
                                pattern_context='ORDER_BLOCK_RETEST'
                            )
                            
                            if entry_point:
                                entry_points.append(entry_point)
            
            return entry_points
            
        except Exception as e:
            logger.error(f"Error detecting order block entries: {e}")
            return []
    
    def _detect_fvg_entries(self, symbol: Symbol, timeframe_analysis: Dict[str, Dict], 
                          current_price: float, entry_type: str) -> List[EntryPoint]:
        """Detect Fair Value Gap entry points"""
        try:
            entry_points = []
            
            # Look for FVG in 1H timeframe
            if '1H' in timeframe_analysis:
                fvg_patterns = [p for p in timeframe_analysis['1H']['patterns'] 
                             if p.pattern_type == 'FAIR_VALUE_GAP' and p.confidence_score >= 0.7]
                
                for fvg in fvg_patterns:
                    fvg_low = float(fvg.pattern_price_low)
                    fvg_high = float(fvg.pattern_price_high)
                    
                    if entry_type == 'BUY' and fvg_low <= current_price <= fvg_high:
                        # Check for FVG retest
                        fvg_confirmation = self._check_fvg_retest(
                            timeframe_analysis['1H'], fvg, 'BUY'
                        )
                        
                        if fvg_confirmation['confirmed']:
                            entry_point = self._create_entry_point(
                                symbol=symbol,
                                entry_type='BUY',
                                entry_price=current_price,
                                confidence_score=fvg_confirmation['confidence'],
                                timeframe_analysis=timeframe_analysis,
                                pattern_context='FVG_RETEST'
                            )
                            
                            if entry_point:
                                entry_points.append(entry_point)
                    
                    elif entry_type == 'SELL' and fvg_low <= current_price <= fvg_high:
                        # Check for FVG retest
                        fvg_confirmation = self._check_fvg_retest(
                            timeframe_analysis['1H'], fvg, 'SELL'
                        )
                        
                        if fvg_confirmation['confirmed']:
                            entry_point = self._create_entry_point(
                                symbol=symbol,
                                entry_type='SELL',
                                entry_price=current_price,
                                confidence_score=fvg_confirmation['confidence'],
                                timeframe_analysis=timeframe_analysis,
                                pattern_context='FVG_RETEST'
                            )
                            
                            if entry_point:
                                entry_points.append(entry_point)
            
            return entry_points
            
        except Exception as e:
            logger.error(f"Error detecting FVG entries: {e}")
            return []
    
    def _check_entry_confirmation(self, timeframe_analysis: Dict, entry_type: str) -> Dict[str, any]:
        """Check for entry confirmation in a timeframe"""
        try:
            confirmation_score = 0.0
            confirmed = False
            
            # Check RSI confirmation
            if 'indicators' in timeframe_analysis and 'RSI' in timeframe_analysis['indicators']:
                rsi = timeframe_analysis['indicators']['RSI']
                if entry_type == 'BUY' and self.strategy_config['rsi_long_range'][0] <= rsi <= self.strategy_config['rsi_long_range'][1]:
                    confirmation_score += 0.3
                elif entry_type == 'SELL' and self.strategy_config['rsi_short_range'][0] <= rsi <= self.strategy_config['rsi_short_range'][1]:
                    confirmation_score += 0.3
            
            # Check MACD confirmation
            if 'indicators' in timeframe_analysis and 'MACD' in timeframe_analysis['indicators']:
                macd_data = timeframe_analysis['indicators']['MACD']
                if entry_type == 'BUY' and macd_data.get('macd', 0) > macd_data.get('signal', 0):
                    confirmation_score += 0.3
                elif entry_type == 'SELL' and macd_data.get('macd', 0) < macd_data.get('signal', 0):
                    confirmation_score += 0.3
            
            # Check candlestick confirmation
            if 'patterns' in timeframe_analysis:
                candlestick_patterns = [p for p in timeframe_analysis['patterns'] 
                                      if p.pattern_type in ['BULLISH_ENGULFING', 'BEARISH_ENGULFING', 'HAMMER', 'DOJI']]
                
                if candlestick_patterns:
                    for pattern in candlestick_patterns:
                        if entry_type == 'BUY' and pattern.pattern_type in ['BULLISH_ENGULFING', 'HAMMER']:
                            confirmation_score += 0.2
                        elif entry_type == 'SELL' and pattern.pattern_type in ['BEARISH_ENGULFING', 'DOJI']:
                            confirmation_score += 0.2
            
            # Check volume confirmation
            if 'volume_analysis' in timeframe_analysis:
                volume_ratio = timeframe_analysis['volume_analysis'].get('volume_ratio', 1.0)
                if volume_ratio >= 1.2:  # 20% above average
                    confirmation_score += 0.2
            
            # Determine if confirmed
            confirmed = confirmation_score >= 0.6
            
            return {
                'confirmed': confirmed,
                'confidence': min(0.95, confirmation_score),
                'score_breakdown': {
                    'rsi': 0.3 if 'RSI' in timeframe_analysis.get('indicators', {}) else 0,
                    'macd': 0.3 if 'MACD' in timeframe_analysis.get('indicators', {}) else 0,
                    'candlestick': 0.2 if candlestick_patterns else 0,
                    'volume': 0.2 if volume_ratio >= 1.2 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error checking entry confirmation: {e}")
            return {'confirmed': False, 'confidence': 0.0}
    
    def _create_entry_point(self, symbol: Symbol, entry_type: str, entry_price: float,
                          confidence_score: float, timeframe_analysis: Dict[str, Dict],
                          pattern_context: str) -> Optional[EntryPoint]:
        """Create an entry point with risk management"""
        try:
            # Calculate stop loss and take profit
            risk_management = self._calculate_risk_management(
                entry_type, entry_price, timeframe_analysis
            )
            
            if not risk_management:
                return None
            
            # Check risk-reward ratio
            risk_reward_ratio = risk_management['risk_reward_ratio']
            if risk_reward_ratio < self.entry_config['risk_reward_min']:
                logger.info(f"Risk-reward ratio {risk_reward_ratio:.2f} below minimum {self.entry_config['risk_reward_min']}")
                return None
            
            # Determine confidence level
            if confidence_score >= 0.9:
                confidence_level = 'VERY_HIGH'
            elif confidence_score >= 0.8:
                confidence_level = 'HIGH'
            elif confidence_score >= 0.7:
                confidence_level = 'MEDIUM'
            else:
                confidence_level = 'LOW'
            
            # Get market structure context
            market_structure = self._get_market_structure_context(timeframe_analysis)
            
            # Create entry point
            entry_point = EntryPoint(
                chart_image=None,  # Will be set when saving
                entry_type=entry_type,
                entry_price=Decimal(str(entry_price)),
                confidence_level=confidence_level,
                confidence_score=confidence_score,
                stop_loss=Decimal(str(risk_management['stop_loss'])),
                take_profit=Decimal(str(risk_management['take_profit'])),
                risk_reward_ratio=risk_reward_ratio,
                entry_x=0.5,  # Center of chart
                entry_y=0.5,  # Center of chart
                market_structure=market_structure,
                timeframe_context=pattern_context,
                is_validated=False
            )
            
            return entry_point
            
        except Exception as e:
            logger.error(f"Error creating entry point: {e}")
            return None
    
    def _calculate_risk_management(self, entry_type: str, entry_price: float, 
                                 timeframe_analysis: Dict[str, Dict]) -> Optional[Dict[str, float]]:
        """Calculate stop loss and take profit based on support/resistance levels"""
        try:
            # Get support and resistance levels from 1H timeframe
            if '1H' not in timeframe_analysis:
                return None
            
            support_resistance = timeframe_analysis['1H'].get('support_resistance', {})
            supports = support_resistance.get('supports', [])
            resistances = support_resistance.get('resistances', [])
            
            if entry_type == 'BUY':
                # Find nearest support below entry price
                valid_supports = [s for s in supports if s < entry_price]
                if not valid_supports:
                    return None
                
                stop_loss = max(valid_supports) * 0.995  # 0.5% below support
                
                # Find nearest resistance above entry price
                valid_resistances = [r for r in resistances if r > entry_price]
                if not valid_resistances:
                    # Use 2% target if no resistance
                    take_profit = entry_price * 1.02
                else:
                    take_profit = min(valid_resistances) * 0.995  # 0.5% below resistance
            
            else:  # SELL
                # Find nearest resistance above entry price
                valid_resistances = [r for r in resistances if r > entry_price]
                if not valid_resistances:
                    return None
                
                stop_loss = min(valid_resistances) * 1.005  # 0.5% above resistance
                
                # Find nearest support below entry price
                valid_supports = [s for s in supports if s < entry_price]
                if not valid_supports:
                    # Use 2% target if no support
                    take_profit = entry_price * 0.98
                else:
                    take_profit = max(valid_supports) * 1.005  # 0.5% above support
            
            # Calculate risk-reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            return {
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'risk_reward_ratio': risk_reward_ratio
            }
            
        except Exception as e:
            logger.error(f"Error calculating risk management: {e}")
            return None
    
    def _determine_market_bias(self, timeframe_analysis: Dict[str, Dict]) -> str:
        """Determine overall market bias from higher timeframes"""
        try:
            bias_scores = {'BULLISH': 0, 'BEARISH': 0, 'NEUTRAL': 0}
            
            # Weight higher timeframes more heavily
            for timeframe, analysis in timeframe_analysis.items():
                weight = self.timeframe_weights.get(timeframe, 0.1)
                trend = analysis.get('trend', 'NEUTRAL')
                
                if trend == 'BULLISH':
                    bias_scores['BULLISH'] += weight
                elif trend == 'BEARISH':
                    bias_scores['BEARISH'] += weight
                else:
                    bias_scores['NEUTRAL'] += weight
            
            # Determine overall bias
            max_bias = max(bias_scores.items(), key=lambda x: x[1])
            
            if max_bias[1] >= 0.5:  # 50% threshold
                return max_bias[0]
            else:
                return 'NEUTRAL'
                
        except Exception as e:
            logger.error(f"Error determining market bias: {e}")
            return 'NEUTRAL'
    
    def _determine_trend(self, df: pd.DataFrame) -> str:
        """Determine trend direction from price data"""
        try:
            if len(df) < 20:
                return 'NEUTRAL'
            
            # Calculate moving averages
            sma_20 = df['close'].rolling(window=20).mean()
            sma_50 = df['close'].rolling(window=min(50, len(df))).mean()
            
            current_price = df.iloc[-1]['close']
            current_sma_20 = sma_20.iloc[-1]
            current_sma_50 = sma_50.iloc[-1]
            
            # Determine trend
            if current_price > current_sma_20 > current_sma_50:
                return 'BULLISH'
            elif current_price < current_sma_20 < current_sma_50:
                return 'BEARISH'
            else:
                return 'NEUTRAL'
                
        except Exception as e:
            logger.error(f"Error determining trend: {e}")
            return 'NEUTRAL'
    
    def _analyze_structure(self, df: pd.DataFrame) -> Dict[str, any]:
        """Analyze market structure"""
        try:
            if len(df) < 20:
                return {}
            
            # Calculate recent highs and lows
            recent_highs = df['high'].rolling(window=10).max()
            recent_lows = df['low'].rolling(window=10).min()
            
            # Determine structure
            current_high = recent_highs.iloc[-1]
            current_low = recent_lows.iloc[-1]
            
            # Check for higher highs and higher lows (uptrend)
            if len(df) >= 20:
                prev_high = recent_highs.iloc[-10]
                prev_low = recent_lows.iloc[-10]
                
                if current_high > prev_high and current_low > prev_low:
                    structure = 'UPTREND'
                elif current_high < prev_high and current_low < prev_low:
                    structure = 'DOWNTREND'
                else:
                    structure = 'SIDEWAYS'
            else:
                structure = 'SIDEWAYS'
            
            return {
                'structure': structure,
                'current_high': current_high,
                'current_low': current_low
            }
            
        except Exception as e:
            logger.error(f"Error analyzing structure: {e}")
            return {}
    
    def _get_timeframe_patterns(self, symbol: Symbol, timeframe: str) -> List[ChartPattern]:
        """Get patterns for a specific timeframe"""
        try:
            patterns = ChartPattern.objects.filter(
                chart_image__symbol=symbol,
                chart_image__timeframe=timeframe,
                confidence_score__gte=0.6
            ).order_by('-confidence_score')
            
            return list(patterns)
            
        except Exception as e:
            logger.error(f"Error getting timeframe patterns: {e}")
            return []
    
    def _get_technical_indicators(self, symbol: Symbol, timeframe: str) -> Dict[str, float]:
        """Get technical indicators for a symbol and timeframe"""
        try:
            indicators = {}
            
            # Get latest indicators
            latest_indicators = TechnicalIndicator.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:10]
            
            for indicator in latest_indicators:
                indicators[indicator.indicator_type] = float(indicator.value)
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error getting technical indicators: {e}")
            return {}
    
    def _calculate_support_resistance(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """Calculate support and resistance levels"""
        try:
            if len(df) < 20:
                return {'supports': [], 'resistances': []}
            
            # Calculate pivot points
            highs = df['high'].rolling(window=5).max()
            lows = df['low'].rolling(window=5).min()
            
            # Find significant levels
            supports = []
            resistances = []
            
            for i in range(5, len(df)):
                if df.iloc[i]['low'] == lows.iloc[i]:
                    supports.append(df.iloc[i]['low'])
                
                if df.iloc[i]['high'] == highs.iloc[i]:
                    resistances.append(df.iloc[i]['high'])
            
            return {
                'supports': supports[-5:],  # Last 5 supports
                'resistances': resistances[-5:]  # Last 5 resistances
            }
            
        except Exception as e:
            logger.error(f"Error calculating support/resistance: {e}")
            return {'supports': [], 'resistances': []}
    
    def _analyze_volume(self, df: pd.DataFrame) -> Dict[str, float]:
        """Analyze volume characteristics"""
        try:
            if len(df) < 10:
                return {'volume_ratio': 1.0}
            
            # Calculate average volume
            avg_volume = df['volume'].rolling(window=10).mean().iloc[-1]
            current_volume = df.iloc[-1]['volume']
            
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            return {
                'volume_ratio': volume_ratio,
                'current_volume': current_volume,
                'avg_volume': avg_volume
            }
            
        except Exception as e:
            logger.error(f"Error analyzing volume: {e}")
            return {'volume_ratio': 1.0}
    
    def _get_market_structure_context(self, timeframe_analysis: Dict[str, Dict]) -> str:
        """Get market structure context"""
        try:
            contexts = []
            
            for timeframe, analysis in timeframe_analysis.items():
                structure = analysis.get('structure', {}).get('structure', 'UNKNOWN')
                trend = analysis.get('trend', 'UNKNOWN')
                contexts.append(f"{timeframe}:{structure}:{trend}")
            
            return "|".join(contexts)
            
        except Exception as e:
            logger.error(f"Error getting market structure context: {e}")
            return "UNKNOWN"
    
    def _validate_entry_points(self, entry_points: List[EntryPoint], 
                             timeframe_analysis: Dict[str, Dict]) -> List[EntryPoint]:
        """Validate entry points based on multi-timeframe agreement"""
        try:
            validated_entries = []
            
            for entry_point in entry_points:
                # Check if entry meets minimum requirements
                if entry_point.confidence_score >= self.entry_config['min_confidence']:
                    # Check timeframe agreement
                    agreement_count = 0
                    
                    for timeframe, analysis in timeframe_analysis.items():
                        trend = analysis.get('trend', 'NEUTRAL')
                        
                        if entry_point.entry_type == 'BUY' and trend == 'BULLISH':
                            agreement_count += 1
                        elif entry_point.entry_type == 'SELL' and trend == 'BEARISH':
                            agreement_count += 1
                    
                    # Check if minimum timeframes agree
                    if agreement_count >= self.entry_config['min_timeframe_agreement']:
                        validated_entries.append(entry_point)
            
            return validated_entries
            
        except Exception as e:
            logger.error(f"Error validating entry points: {e}")
            return []
    
    def _check_order_block_retest(self, timeframe_analysis: Dict, order_block: ChartPattern, entry_type: str) -> Dict[str, any]:
        """Check for Order Block retest confirmation"""
        try:
            # This would implement specific Order Block retest logic
            # For now, return a basic confirmation
            return {
                'confirmed': True,
                'confidence': order_block.confidence_score * 0.9
            }
            
        except Exception as e:
            logger.error(f"Error checking order block retest: {e}")
            return {'confirmed': False, 'confidence': 0.0}
    
    def _check_fvg_retest(self, timeframe_analysis: Dict, fvg: ChartPattern, entry_type: str) -> Dict[str, any]:
        """Check for FVG retest confirmation"""
        try:
            # This would implement specific FVG retest logic
            # For now, return a basic confirmation
            return {
                'confirmed': True,
                'confidence': fvg.confidence_score * 0.9
            }
            
        except Exception as e:
            logger.error(f"Error checking FVG retest: {e}")
            return {'confirmed': False, 'confidence': 0.0}
    
    def _get_market_data_for_chart(self, chart_image: ChartImage) -> Optional[List[Dict]]:
        """Get market data for a specific chart image"""
        try:
            market_data = MarketData.objects.filter(
                symbol=chart_image.symbol,
                timestamp__gte=chart_image.start_time,
                timestamp__lte=chart_image.end_time
            ).order_by('timestamp')
            
            if not market_data.exists():
                return None
            
            data_list = []
            for data in market_data:
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
            logger.error(f"Error getting market data for chart {chart_image.id}: {e}")
            return None
    
    def _detect_entry_points_from_patterns(self, chart_image: ChartImage, patterns: List[ChartPattern],
                                        market_data: List[Dict], indicators: Dict[str, float]) -> List[EntryPoint]:
        """Detect entry points from patterns and indicators"""
        try:
            entry_points = []
            
            for pattern in patterns:
                # Determine entry type based on pattern
                if pattern.pattern_type in ['BOS', 'CHOCH', 'ORDER_BLOCK', 'FAIR_VALUE_GAP']:
                    # Determine if bullish or bearish based on pattern characteristics
                    entry_type = self._determine_entry_type_from_pattern(pattern, market_data)
                    
                    if entry_type:
                        # Check entry confirmation
                        confirmation = self._check_entry_confirmation_from_indicators(
                            indicators, entry_type
                        )
                        
                        if confirmation['confirmed']:
                            # Create entry point
                            entry_point = self._create_entry_point_from_pattern(
                                chart_image, pattern, entry_type, confirmation['confidence']
                            )
                            
                            if entry_point:
                                entry_points.append(entry_point)
            
            return entry_points
            
        except Exception as e:
            logger.error(f"Error detecting entry points from patterns: {e}")
            return []
    
    def _determine_entry_type_from_pattern(self, pattern: ChartPattern, market_data: List[Dict]) -> Optional[str]:
        """Determine entry type from pattern"""
        try:
            # This would implement specific logic to determine entry type
            # For now, return a basic determination
            if pattern.pattern_type in ['BOS', 'CHOCH']:
                # Analyze pattern characteristics to determine direction
                return 'BUY'  # Simplified for now
            elif pattern.pattern_type in ['ORDER_BLOCK', 'FAIR_VALUE_GAP']:
                return 'BUY'  # Simplified for now
            
            return None
            
        except Exception as e:
            logger.error(f"Error determining entry type from pattern: {e}")
            return None
    
    def _check_entry_confirmation_from_indicators(self, indicators: Dict[str, float], entry_type: str) -> Dict[str, any]:
        """Check entry confirmation from technical indicators"""
        try:
            confirmation_score = 0.0
            
            # Check RSI
            if 'RSI' in indicators:
                rsi = indicators['RSI']
                if entry_type == 'BUY' and 20 <= rsi <= 50:
                    confirmation_score += 0.4
                elif entry_type == 'SELL' and 50 <= rsi <= 80:
                    confirmation_score += 0.4
            
            # Check MACD
            if 'MACD' in indicators:
                macd = indicators['MACD']
                if entry_type == 'BUY' and macd > 0:
                    confirmation_score += 0.3
                elif entry_type == 'SELL' and macd < 0:
                    confirmation_score += 0.3
            
            # Check Moving Average
            if 'SMA' in indicators and 'EMA' in indicators:
                sma = indicators['SMA']
                ema = indicators['EMA']
                if entry_type == 'BUY' and ema > sma:
                    confirmation_score += 0.3
                elif entry_type == 'SELL' and ema < sma:
                    confirmation_score += 0.3
            
            confirmed = confirmation_score >= 0.6
            
            return {
                'confirmed': confirmed,
                'confidence': min(0.95, confirmation_score)
            }
            
        except Exception as e:
            logger.error(f"Error checking entry confirmation from indicators: {e}")
            return {'confirmed': False, 'confidence': 0.0}
    
    def _create_entry_point_from_pattern(self, chart_image: ChartImage, pattern: ChartPattern,
                                       entry_type: str, confidence_score: float) -> Optional[EntryPoint]:
        """Create entry point from pattern"""
        try:
            # Calculate coordinates based on pattern
            entry_x = (pattern.x_start + pattern.x_end) / 2
            entry_y = (pattern.y_start + pattern.y_end) / 2
            
            # Determine confidence level
            if confidence_score >= 0.9:
                confidence_level = 'VERY_HIGH'
            elif confidence_score >= 0.8:
                confidence_level = 'HIGH'
            elif confidence_score >= 0.7:
                confidence_level = 'MEDIUM'
            else:
                confidence_level = 'LOW'
            
            # Create entry point
            entry_point = EntryPoint(
                chart_image=chart_image,
                pattern=pattern,
                entry_type=entry_type,
                entry_price=pattern.pattern_price_low,  # Use pattern price
                confidence_level=confidence_level,
                confidence_score=confidence_score,
                entry_x=entry_x,
                entry_y=entry_y,
                market_structure=f"{pattern.pattern_type}_PATTERN",
                timeframe_context=chart_image.timeframe,
                is_validated=False
            )
            
            return entry_point
            
        except Exception as e:
            logger.error(f"Error creating entry point from pattern: {e}")
            return None


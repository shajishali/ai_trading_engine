"""
Phase 5.2: SMC Pattern Recognition & Labeling Service
Implements Smart Money Concepts pattern detection and labeling
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
from apps.data.models import MarketData
from apps.signals.models import ChartImage, ChartPattern, EntryPoint

logger = logging.getLogger(__name__)


class SMCPatternRecognitionService:
    """Service for detecting and labeling Smart Money Concepts patterns"""
    
    def __init__(self):
        # SMC Pattern Detection Parameters
        self.bos_config = {
            'min_structure_break': 0.001,  # 0.1% minimum break
            'confirmation_candles': 2,      # Candles to confirm BOS
            'volume_multiplier': 1.2,       # Volume should be 1.2x average
            'lookback_periods': 20          # Periods to look back for structure
        }
        
        self.choch_config = {
            'min_reversal_strength': 0.002,  # 0.2% minimum reversal
            'confirmation_candles': 3,       # Candles to confirm CHoCH
            'volume_confirmation': True,     # Require volume confirmation
            'lookback_periods': 50           # Periods to look back for trend
        }
        
        self.order_block_config = {
            'min_block_size': 0.001,        # 0.1% minimum block size
            'max_block_age': 20,            # Maximum periods for valid block
            'volume_threshold': 1.5,        # Volume threshold for block
            'retest_confirmation': True     # Require retest confirmation
        }
        
        self.fvg_config = {
            'min_gap_size': 0.0005,         # 0.05% minimum gap size
            'max_gap_age': 10,              # Maximum periods for valid FVG
            'volume_confirmation': True,    # Require volume confirmation
            'retest_threshold': 0.3         # 30% retest threshold
        }
        
        self.liquidity_sweep_config = {
            'sweep_threshold': 0.0005,      # 0.05% sweep threshold
            'volume_spike': 1.8,            # Volume spike requirement
            'rejection_confirmation': True, # Require rejection confirmation
            'lookback_periods': 15          # Periods to look back for liquidity
        }
    
    def detect_patterns_for_chart(self, chart_image: ChartImage) -> Dict[str, List[ChartPattern]]:
        """
        Detect all SMC patterns for a specific chart image
        
        Args:
            chart_image: ChartImage instance to analyze
            
        Returns:
            Dictionary with detected patterns by type
        """
        try:
            logger.info(f"Detecting SMC patterns for {chart_image.symbol.symbol} - {chart_image.timeframe}")
            
            # Get market data for the chart
            market_data = self._get_market_data_for_chart(chart_image)
            if not market_data or len(market_data) < 20:
                logger.warning(f"Insufficient market data for pattern detection")
                return {}
            
            detected_patterns = {
                'bos': [],
                'choch': [],
                'order_blocks': [],
                'fvg': [],
                'liquidity_sweeps': []
            }
            
            # Detect BOS patterns
            bos_patterns = self._detect_bos_patterns(chart_image, market_data)
            detected_patterns['bos'] = bos_patterns
            
            # Detect CHoCH patterns
            choch_patterns = self._detect_choch_patterns(chart_image, market_data)
            detected_patterns['choch'] = choch_patterns
            
            # Detect Order Blocks
            order_block_patterns = self._detect_order_blocks(chart_image, market_data)
            detected_patterns['order_blocks'] = order_block_patterns
            
            # Detect Fair Value Gaps
            fvg_patterns = self._detect_fvg_patterns(chart_image, market_data)
            detected_patterns['fvg'] = fvg_patterns
            
            # Detect Liquidity Sweeps
            liquidity_patterns = self._detect_liquidity_sweeps(chart_image, market_data)
            detected_patterns['liquidity_sweeps'] = liquidity_patterns
            
            total_patterns = sum(len(patterns) for patterns in detected_patterns.values())
            logger.info(f"Detected {total_patterns} SMC patterns for {chart_image.symbol.symbol} - {chart_image.timeframe}")
            
            return detected_patterns
            
        except Exception as e:
            logger.error(f"Error detecting patterns for chart {chart_image.id}: {e}")
            return {}
    
    def detect_patterns_for_symbol(self, symbol: Symbol, timeframe: str = '1H') -> Dict[str, int]:
        """
        Detect SMC patterns for all charts of a specific symbol
        
        Args:
            symbol: Trading symbol
            timeframe: Chart timeframe
            
        Returns:
            Dictionary with pattern detection statistics
        """
        try:
            logger.info(f"Detecting SMC patterns for {symbol.symbol} - {timeframe}")
            
            # Get all chart images for the symbol and timeframe
            chart_images = ChartImage.objects.filter(
                symbol=symbol,
                timeframe=timeframe,
                is_training_data=True
            ).order_by('-created_at')
            
            if not chart_images.exists():
                logger.warning(f"No chart images found for {symbol.symbol} - {timeframe}")
                return {'charts_processed': 0, 'patterns_detected': 0}
            
            stats = {
                'charts_processed': 0,
                'patterns_detected': 0,
                'bos_count': 0,
                'choch_count': 0,
                'order_blocks_count': 0,
                'fvg_count': 0,
                'liquidity_sweeps_count': 0
            }
            
            for chart_image in chart_images:
                try:
                    # Detect patterns for this chart
                    patterns = self.detect_patterns_for_chart(chart_image)
                    
                    stats['charts_processed'] += 1
                    
                    # Count patterns by type
                    for pattern_type, pattern_list in patterns.items():
                        count = len(pattern_list)
                        stats['patterns_detected'] += count
                        
                        if pattern_type == 'bos':
                            stats['bos_count'] += count
                        elif pattern_type == 'choch':
                            stats['choch_count'] += count
                        elif pattern_type == 'order_blocks':
                            stats['order_blocks_count'] += count
                        elif pattern_type == 'fvg':
                            stats['fvg_count'] += count
                        elif pattern_type == 'liquidity_sweeps':
                            stats['liquidity_sweeps_count'] += count
                    
                except Exception as e:
                    logger.error(f"Error processing chart {chart_image.id}: {e}")
            
            logger.info(f"SMC pattern detection completed for {symbol.symbol}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error detecting patterns for {symbol.symbol}: {e}")
            return {'charts_processed': 0, 'patterns_detected': 0}
    
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
    
    def _detect_bos_patterns(self, chart_image: ChartImage, market_data: List[Dict]) -> List[ChartPattern]:
        """Detect Break of Structure (BOS) patterns"""
        try:
            patterns = []
            df = pd.DataFrame(market_data)
            
            if len(df) < self.bos_config['lookback_periods']:
                return patterns
            
            # Calculate structure levels
            highs = df['high'].rolling(window=self.bos_config['lookback_periods']).max()
            lows = df['low'].rolling(window=self.bos_config['lookback_periods']).min()
            
            # Detect bullish BOS (break above previous high)
            for i in range(self.bos_config['lookback_periods'], len(df)):
                current_high = df.iloc[i]['high']
                previous_high = highs.iloc[i-1]
                
                if current_high > previous_high * (1 + self.bos_config['min_structure_break']):
                    # Check volume confirmation
                    avg_volume = df['volume'].rolling(window=10).mean().iloc[i]
                    current_volume = df.iloc[i]['volume']
                    
                    if current_volume >= avg_volume * self.bos_config['volume_multiplier']:
                        # Calculate confidence score
                        break_strength = (current_high - previous_high) / previous_high
                        volume_ratio = current_volume / avg_volume
                        confidence_score = min(0.95, (break_strength * 10 + volume_ratio * 0.1))
                        
                        # Calculate coordinates
                        x_pos = i / len(df)
                        y_pos = (current_high - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                        
                        pattern = ChartPattern(
                            chart_image=chart_image,
                            pattern_type='BOS',
                            confidence_score=confidence_score,
                            x_start=x_pos - 0.05,
                            y_start=y_pos,
                            x_end=x_pos + 0.05,
                            y_end=y_pos,
                            strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                            pattern_price_low=Decimal(str(previous_high)),
                            pattern_price_high=Decimal(str(current_high)),
                            is_validated=False
                        )
                        patterns.append(pattern)
            
            # Detect bearish BOS (break below previous low)
            for i in range(self.bos_config['lookback_periods'], len(df)):
                current_low = df.iloc[i]['low']
                previous_low = lows.iloc[i-1]
                
                if current_low < previous_low * (1 - self.bos_config['min_structure_break']):
                    # Check volume confirmation
                    avg_volume = df['volume'].rolling(window=10).mean().iloc[i]
                    current_volume = df.iloc[i]['volume']
                    
                    if current_volume >= avg_volume * self.bos_config['volume_multiplier']:
                        # Calculate confidence score
                        break_strength = (previous_low - current_low) / previous_low
                        volume_ratio = current_volume / avg_volume
                        confidence_score = min(0.95, (break_strength * 10 + volume_ratio * 0.1))
                        
                        # Calculate coordinates
                        x_pos = i / len(df)
                        y_pos = (current_low - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                        
                        pattern = ChartPattern(
                            chart_image=chart_image,
                            pattern_type='BOS',
                            confidence_score=confidence_score,
                            x_start=x_pos - 0.05,
                            y_start=y_pos,
                            x_end=x_pos + 0.05,
                            y_end=y_pos,
                            strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                            pattern_price_low=Decimal(str(current_low)),
                            pattern_price_high=Decimal(str(previous_low)),
                            is_validated=False
                        )
                        patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting BOS patterns: {e}")
            return []
    
    def _detect_choch_patterns(self, chart_image: ChartImage, market_data: List[Dict]) -> List[ChartPattern]:
        """Detect Change of Character (CHoCH) patterns"""
        try:
            patterns = []
            df = pd.DataFrame(market_data)
            
            if len(df) < self.choch_config['lookback_periods']:
                return patterns
            
            # Calculate trend direction
            sma_short = df['close'].rolling(window=10).mean()
            sma_long = df['close'].rolling(window=20).mean()
            
            # Detect bullish CHoCH (downtrend to uptrend)
            for i in range(self.choch_config['lookback_periods'], len(df)):
                # Check if we're transitioning from downtrend to uptrend
                if (i >= 20 and 
                    sma_short.iloc[i-5] < sma_long.iloc[i-5] and  # Was in downtrend
                    sma_short.iloc[i] > sma_long.iloc[i]):        # Now in uptrend
                    
                    # Check for significant reversal
                    recent_low = df['low'].iloc[i-10:i].min()
                    current_price = df.iloc[i]['close']
                    reversal_strength = (current_price - recent_low) / recent_low
                    
                    if reversal_strength >= self.choch_config['min_reversal_strength']:
                        # Check volume confirmation
                        avg_volume = df['volume'].rolling(window=10).mean().iloc[i]
                        current_volume = df.iloc[i]['volume']
                        
                        if current_volume >= avg_volume * 1.2:
                            # Calculate confidence score
                            confidence_score = min(0.95, reversal_strength * 20 + (current_volume / avg_volume) * 0.1)
                            
                            # Calculate coordinates
                            x_pos = i / len(df)
                            y_pos = (current_price - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                            
                            pattern = ChartPattern(
                                chart_image=chart_image,
                                pattern_type='CHOCH',
                                confidence_score=confidence_score,
                                x_start=x_pos - 0.1,
                                y_start=y_pos,
                                x_end=x_pos + 0.1,
                                y_end=y_pos,
                                strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                                pattern_price_low=Decimal(str(recent_low)),
                                pattern_price_high=Decimal(str(current_price)),
                                is_validated=False
                            )
                            patterns.append(pattern)
            
            # Detect bearish CHoCH (uptrend to downtrend)
            for i in range(self.choch_config['lookback_periods'], len(df)):
                # Check if we're transitioning from uptrend to downtrend
                if (i >= 20 and 
                    sma_short.iloc[i-5] > sma_long.iloc[i-5] and  # Was in uptrend
                    sma_short.iloc[i] < sma_long.iloc[i]):        # Now in downtrend
                    
                    # Check for significant reversal
                    recent_high = df['high'].iloc[i-10:i].max()
                    current_price = df.iloc[i]['close']
                    reversal_strength = (recent_high - current_price) / recent_high
                    
                    if reversal_strength >= self.choch_config['min_reversal_strength']:
                        # Check volume confirmation
                        avg_volume = df['volume'].rolling(window=10).mean().iloc[i]
                        current_volume = df.iloc[i]['volume']
                        
                        if current_volume >= avg_volume * 1.2:
                            # Calculate confidence score
                            confidence_score = min(0.95, reversal_strength * 20 + (current_volume / avg_volume) * 0.1)
                            
                            # Calculate coordinates
                            x_pos = i / len(df)
                            y_pos = (current_price - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                            
                            pattern = ChartPattern(
                                chart_image=chart_image,
                                pattern_type='CHOCH',
                                confidence_score=confidence_score,
                                x_start=x_pos - 0.1,
                                y_start=y_pos,
                                x_end=x_pos + 0.1,
                                y_end=y_pos,
                                strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                                pattern_price_low=Decimal(str(current_price)),
                                pattern_price_high=Decimal(str(recent_high)),
                                is_validated=False
                            )
                            patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting CHoCH patterns: {e}")
            return []
    
    def _detect_order_blocks(self, chart_image: ChartImage, market_data: List[Dict]) -> List[ChartPattern]:
        """Detect Order Block patterns"""
        try:
            patterns = []
            df = pd.DataFrame(market_data)
            
            if len(df) < 20:
                return patterns
            
            # Detect bullish order blocks (after strong move up)
            for i in range(10, len(df) - 5):
                # Look for strong bullish candle followed by consolidation
                current_candle = df.iloc[i]
                prev_candle = df.iloc[i-1]
                
                # Check for strong bullish candle
                candle_size = (current_candle['close'] - current_candle['open']) / current_candle['open']
                if candle_size > 0.02:  # 2% minimum candle size
                    
                    # Check for volume confirmation
                    avg_volume = df['volume'].rolling(window=10).mean().iloc[i]
                    if current_candle['volume'] >= avg_volume * self.order_block_config['volume_threshold']:
                        
                        # Look for consolidation after the move
                        consolidation_start = i + 1
                        consolidation_end = min(i + 10, len(df))
                        
                        # Check if price consolidates in the range
                        consolidation_range = df.iloc[consolidation_start:consolidation_end]
                        if len(consolidation_range) >= 3:
                            range_high = consolidation_range['high'].max()
                            range_low = consolidation_range['low'].min()
                            range_size = (range_high - range_low) / range_low
                            
                            if range_size < 0.01:  # Less than 1% range
                                # Calculate confidence score
                                volume_ratio = current_candle['volume'] / avg_volume
                                consolidation_score = 1 - range_size * 100
                                confidence_score = min(0.95, (volume_ratio * 0.3 + consolidation_score * 0.7))
                                
                                # Calculate coordinates
                                x_start = consolidation_start / len(df)
                                x_end = consolidation_end / len(df)
                                y_start = (range_low - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                                y_end = (range_high - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                                
                                pattern = ChartPattern(
                                    chart_image=chart_image,
                                    pattern_type='ORDER_BLOCK',
                                    confidence_score=confidence_score,
                                    x_start=x_start,
                                    y_start=y_start,
                                    x_end=x_end,
                                    y_end=y_end,
                                    strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                                    pattern_price_low=Decimal(str(range_low)),
                                    pattern_price_high=Decimal(str(range_high)),
                                    is_validated=False
                                )
                                patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting Order Blocks: {e}")
            return []
    
    def _detect_fvg_patterns(self, chart_image: ChartImage, market_data: List[Dict]) -> List[ChartPattern]:
        """Detect Fair Value Gap (FVG) patterns"""
        try:
            patterns = []
            df = pd.DataFrame(market_data)
            
            if len(df) < 10:
                return patterns
            
            # Detect bullish FVG (gap up)
            for i in range(2, len(df)):
                prev_candle = df.iloc[i-1]
                current_candle = df.iloc[i]
                
                # Check for gap up
                gap_size = (current_candle['low'] - prev_candle['high']) / prev_candle['high']
                
                if gap_size > self.fvg_config['min_gap_size']:
                    # Check volume confirmation
                    avg_volume = df['volume'].rolling(window=10).mean().iloc[i]
                    if current_candle['volume'] >= avg_volume * 1.2:
                        
                        # Calculate confidence score
                        volume_ratio = current_candle['volume'] / avg_volume
                        gap_score = min(1.0, gap_size * 200)  # Scale gap size
                        confidence_score = min(0.95, (gap_score * 0.6 + volume_ratio * 0.4))
                        
                        # Calculate coordinates
                        x_pos = i / len(df)
                        y_start = (prev_candle['high'] - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                        y_end = (current_candle['low'] - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                        
                        pattern = ChartPattern(
                            chart_image=chart_image,
                            pattern_type='FAIR_VALUE_GAP',
                            confidence_score=confidence_score,
                            x_start=x_pos - 0.05,
                            y_start=y_start,
                            x_end=x_pos + 0.05,
                            y_end=y_end,
                            strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                            pattern_price_low=Decimal(str(prev_candle['high'])),
                            pattern_price_high=Decimal(str(current_candle['low'])),
                            is_validated=False
                        )
                        patterns.append(pattern)
            
            # Detect bearish FVG (gap down)
            for i in range(2, len(df)):
                prev_candle = df.iloc[i-1]
                current_candle = df.iloc[i]
                
                # Check for gap down
                gap_size = (prev_candle['low'] - current_candle['high']) / prev_candle['low']
                
                if gap_size > self.fvg_config['min_gap_size']:
                    # Check volume confirmation
                    avg_volume = df['volume'].rolling(window=10).mean().iloc[i]
                    if current_candle['volume'] >= avg_volume * 1.2:
                        
                        # Calculate confidence score
                        volume_ratio = current_candle['volume'] / avg_volume
                        gap_score = min(1.0, gap_size * 200)  # Scale gap size
                        confidence_score = min(0.95, (gap_score * 0.6 + volume_ratio * 0.4))
                        
                        # Calculate coordinates
                        x_pos = i / len(df)
                        y_start = (current_candle['high'] - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                        y_end = (prev_candle['low'] - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                        
                        pattern = ChartPattern(
                            chart_image=chart_image,
                            pattern_type='FAIR_VALUE_GAP',
                            confidence_score=confidence_score,
                            x_start=x_pos - 0.05,
                            y_start=y_start,
                            x_end=x_pos + 0.05,
                            y_end=y_end,
                            strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                            pattern_price_low=Decimal(str(current_candle['high'])),
                            pattern_price_high=Decimal(str(prev_candle['low'])),
                            is_validated=False
                        )
                        patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting FVG patterns: {e}")
            return []
    
    def _detect_liquidity_sweeps(self, chart_image: ChartImage, market_data: List[Dict]) -> List[ChartPattern]:
        """Detect Liquidity Sweep patterns"""
        try:
            patterns = []
            df = pd.DataFrame(market_data)
            
            if len(df) < self.liquidity_sweep_config['lookback_periods']:
                return patterns
            
            # Detect bullish liquidity sweep (sweep below support then reversal)
            for i in range(self.liquidity_sweep_config['lookback_periods'], len(df)):
                # Find recent support level
                lookback_data = df.iloc[i-self.liquidity_sweep_config['lookback_periods']:i]
                support_level = lookback_data['low'].min()
                
                current_candle = df.iloc[i]
                
                # Check for sweep below support
                sweep_size = (support_level - current_candle['low']) / support_level
                
                if sweep_size > self.liquidity_sweep_config['sweep_threshold']:
                    # Check for volume spike
                    avg_volume = df['volume'].rolling(window=10).mean().iloc[i]
                    volume_ratio = current_candle['volume'] / avg_volume
                    
                    if volume_ratio >= self.liquidity_sweep_config['volume_spike']:
                        # Check for rejection (close above support)
                        if current_candle['close'] > support_level:
                            # Calculate confidence score
                            sweep_score = min(1.0, sweep_size * 200)
                            rejection_score = (current_candle['close'] - support_level) / support_level
                            confidence_score = min(0.95, (sweep_score * 0.4 + rejection_score * 100 * 0.4 + volume_ratio * 0.2))
                            
                            # Calculate coordinates
                            x_pos = i / len(df)
                            y_pos = (current_candle['low'] - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                            
                            pattern = ChartPattern(
                                chart_image=chart_image,
                                pattern_type='LIQUIDITY_SWEEP',
                                confidence_score=confidence_score,
                                x_start=x_pos - 0.05,
                                y_start=y_pos,
                                x_end=x_pos + 0.05,
                                y_end=y_pos,
                                strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                                pattern_price_low=Decimal(str(current_candle['low'])),
                                pattern_price_high=Decimal(str(support_level)),
                                is_validated=False
                            )
                            patterns.append(pattern)
            
            # Detect bearish liquidity sweep (sweep above resistance then reversal)
            for i in range(self.liquidity_sweep_config['lookback_periods'], len(df)):
                # Find recent resistance level
                lookback_data = df.iloc[i-self.liquidity_sweep_config['lookback_periods']:i]
                resistance_level = lookback_data['high'].max()
                
                current_candle = df.iloc[i]
                
                # Check for sweep above resistance
                sweep_size = (current_candle['high'] - resistance_level) / resistance_level
                
                if sweep_size > self.liquidity_sweep_config['sweep_threshold']:
                    # Check for volume spike
                    avg_volume = df['volume'].rolling(window=10).mean().iloc[i]
                    volume_ratio = current_candle['volume'] / avg_volume
                    
                    if volume_ratio >= self.liquidity_sweep_config['volume_spike']:
                        # Check for rejection (close below resistance)
                        if current_candle['close'] < resistance_level:
                            # Calculate confidence score
                            sweep_score = min(1.0, sweep_size * 200)
                            rejection_score = (resistance_level - current_candle['close']) / resistance_level
                            confidence_score = min(0.95, (sweep_score * 0.4 + rejection_score * 100 * 0.4 + volume_ratio * 0.2))
                            
                            # Calculate coordinates
                            x_pos = i / len(df)
                            y_pos = (current_candle['high'] - chart_image.price_range_low) / (chart_image.price_range_high - chart_image.price_range_low)
                            
                            pattern = ChartPattern(
                                chart_image=chart_image,
                                pattern_type='LIQUIDITY_SWEEP',
                                confidence_score=confidence_score,
                                x_start=x_pos - 0.05,
                                y_start=y_pos,
                                x_end=x_pos + 0.05,
                                y_end=y_pos,
                                strength='STRONG' if confidence_score > 0.8 else 'MODERATE',
                                pattern_price_low=Decimal(str(resistance_level)),
                                pattern_price_high=Decimal(str(current_candle['high'])),
                                is_validated=False
                            )
                            patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting Liquidity Sweeps: {e}")
            return []
    
    def save_patterns_to_database(self, patterns: Dict[str, List[ChartPattern]]) -> int:
        """
        Save detected patterns to database
        
        Args:
            patterns: Dictionary of patterns by type
            
        Returns:
            Number of patterns saved
        """
        try:
            saved_count = 0
            
            with transaction.atomic():
                for pattern_type, pattern_list in patterns.items():
                    for pattern in pattern_list:
                        try:
                            pattern.save()
                            saved_count += 1
                        except Exception as e:
                            logger.error(f"Error saving pattern: {e}")
            
            logger.info(f"Saved {saved_count} patterns to database")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving patterns to database: {e}")
            return 0


"""
Smart Money Concepts (SMC) Strategy
Implements Break of Structure (BOS) and Change of Character (CHoCH) with advanced entry logic
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q

from apps.signals.models import TradingSignal, SignalType
from apps.trading.models import Symbol
from apps.data.models import TechnicalIndicator, MarketData
from apps.signals.advanced_indicators import AdvancedIndicatorsService

logger = logging.getLogger(__name__)


class SmartMoneyConceptsStrategy:
    """
    Smart Money Concepts (SMC) Strategy
    
    Implements:
    - Break of Structure (BOS) detection
    - Change of Character (CHoCH) identification
    - Fair Value Gap (FVG) analysis
    - Liquidity Sweep detection
    - Order Block identification
    - Market Structure analysis
    """
    
    def __init__(self):
        self.name = "SmartMoneyConceptsStrategy"
        self.min_confidence_threshold = 0.75
        self.min_risk_reward_ratio = 3.0
        
        # Initialize advanced indicators service
        self.advanced_indicators = AdvancedIndicatorsService()
        
        # SMC parameters
        self.structure_lookback = 50  # Look back 50 candles for structure
        self.bos_confirmation_candles = 3  # Candles to confirm BOS
        self.choch_confirmation_candles = 2  # Candles to confirm CHoCH
        self.liquidity_sweep_threshold = 0.001  # 0.1% threshold for liquidity sweep
        
    def generate_signals(self, symbol: Symbol) -> List[TradingSignal]:
        """Generate SMC-based trading signals"""
        signals = []
        
        try:
            # Get market data
            market_data = self._get_market_data(symbol, self.structure_lookback)
            if len(market_data) < 20:
                return signals
            
            # Analyze market structure
            market_structure = self._analyze_market_structure(market_data)
            
            # Detect Break of Structure (BOS)
            bos_signals = self._detect_bos(symbol, market_data, market_structure)
            signals.extend(bos_signals)
            
            # Detect Change of Character (CHoCH)
            choch_signals = self._detect_choch(symbol, market_data, market_structure)
            signals.extend(choch_signals)
            
            # Detect Order Blocks
            order_block_signals = self._detect_order_blocks(symbol, market_data, market_structure)
            signals.extend(order_block_signals)
            
            # Detect Liquidity Sweeps
            liquidity_signals = self._detect_liquidity_sweeps(symbol, market_data, market_structure)
            signals.extend(liquidity_signals)
            
            # Combine with Fair Value Gaps
            fvg_signals = self._detect_fvg_entries(symbol, market_data, market_structure)
            signals.extend(fvg_signals)
            
            logger.info(f"Generated {len(signals)} SMC signals for {symbol.symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error generating SMC signals for {symbol.symbol}: {e}")
            return []
    
    def _get_market_data(self, symbol: Symbol, lookback: int) -> List[Dict]:
        """Get market data for analysis"""
        try:
            market_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:lookback]
            
            return [{
                'timestamp': data.timestamp,
                'open': float(data.open_price),
                'high': float(data.high_price),
                'low': float(data.low_price),
                'close': float(data.close_price),
                'volume': float(data.volume)
            } for data in market_data]
        except Exception as e:
            logger.error(f"Error getting market data for {symbol.symbol}: {e}")
            return []
    
    def _analyze_market_structure(self, market_data: List[Dict]) -> Dict:
        """Analyze market structure for SMC"""
        try:
            df = pd.DataFrame(market_data)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Find swing highs and lows
            swing_highs = self._find_swing_highs(df)
            swing_lows = self._find_swing_lows(df)
            
            # Determine current trend
            current_trend = self._determine_trend(swing_highs, swing_lows)
            
            # Find recent structure breaks
            recent_breaks = self._find_recent_structure_breaks(df, swing_highs, swing_lows)
            
            return {
                'swing_highs': swing_highs,
                'swing_lows': swing_lows,
                'current_trend': current_trend,
                'recent_breaks': recent_breaks,
                'latest_high': swing_highs[-1] if swing_highs else None,
                'latest_low': swing_lows[-1] if swing_lows else None
            }
            
        except Exception as e:
            logger.error(f"Error analyzing market structure: {e}")
            return {}
    
    def _detect_bos(self, symbol: Symbol, market_data: List[Dict], structure: Dict) -> List[TradingSignal]:
        """Detect Break of Structure (BOS) signals"""
        signals = []
        
        try:
            if not structure.get('recent_breaks'):
                return signals
            
            df = pd.DataFrame(market_data)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            for break_info in structure['recent_breaks']:
                if break_info['type'] == 'BOS':
                    # Check if BOS is confirmed
                    if self._confirm_bos(df, break_info):
                        signal = self._create_bos_signal(symbol, break_info, df)
                        if signal:
                            signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting BOS for {symbol.symbol}: {e}")
            return []
    
    def _detect_choch(self, symbol: Symbol, market_data: List[Dict], structure: Dict) -> List[TradingSignal]:
        """Detect Change of Character (CHoCH) signals"""
        signals = []
        
        try:
            if not structure.get('recent_breaks'):
                return signals
            
            df = pd.DataFrame(market_data)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            for break_info in structure['recent_breaks']:
                if break_info['type'] == 'CHoCH':
                    # Check if CHoCH is confirmed
                    if self._confirm_choch(df, break_info):
                        signal = self._create_choch_signal(symbol, break_info, df)
                        if signal:
                            signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting CHoCH for {symbol.symbol}: {e}")
            return []
    
    def _detect_order_blocks(self, symbol: Symbol, market_data: List[Dict], structure: Dict) -> List[TradingSignal]:
        """Detect Order Block signals"""
        signals = []
        
        try:
            df = pd.DataFrame(market_data)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Find order blocks (strong moves followed by consolidation)
            order_blocks = self._find_order_blocks(df)
            
            for ob in order_blocks:
                if self._validate_order_block(df, ob):
                    signal = self._create_order_block_signal(symbol, ob, df)
                    if signal:
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting Order Blocks for {symbol.symbol}: {e}")
            return []
    
    def _detect_liquidity_sweeps(self, symbol: Symbol, market_data: List[Dict], structure: Dict) -> List[TradingSignal]:
        """Detect Liquidity Sweep signals"""
        signals = []
        
        try:
            df = pd.DataFrame(market_data)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Find liquidity sweeps (false breakouts)
            liquidity_sweeps = self._find_liquidity_sweeps(df, structure)
            
            for sweep in liquidity_sweeps:
                if self._validate_liquidity_sweep(df, sweep):
                    signal = self._create_liquidity_sweep_signal(symbol, sweep, df)
                    if signal:
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting Liquidity Sweeps for {symbol.symbol}: {e}")
            return []
    
    def _detect_fvg_entries(self, symbol: Symbol, market_data: List[Dict], structure: Dict) -> List[TradingSignal]:
        """Detect Fair Value Gap entry signals"""
        signals = []
        
        try:
            # Get FVG data from advanced indicators
            fvg_data = self.advanced_indicators.calculate_fair_value_gap(symbol)
            
            if not fvg_data or not fvg_data.get('latest_fvg'):
                return signals
            
            latest_fvg = fvg_data['latest_fvg']
            current_price = market_data[-1]['close']
            
            # Check if price is approaching FVG
            if self._is_price_approaching_fvg(current_price, latest_fvg):
                signal = self._create_fvg_signal(symbol, latest_fvg, current_price)
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting FVG entries for {symbol.symbol}: {e}")
            return []
    
    def _find_swing_highs(self, df: pd.DataFrame) -> List[Dict]:
        """Find swing highs in the data"""
        swing_highs = []
        
        for i in range(5, len(df) - 5):
            current_high = df.iloc[i]['high']
            
            # Check if it's a swing high
            is_swing_high = True
            for j in range(1, 6):
                if (df.iloc[i-j]['high'] >= current_high or 
                    df.iloc[i+j]['high'] >= current_high):
                    is_swing_high = False
                    break
            
            if is_swing_high:
                swing_highs.append({
                    'index': i,
                    'price': current_high,
                    'timestamp': df.iloc[i]['timestamp']
                })
        
        return swing_highs
    
    def _find_swing_lows(self, df: pd.DataFrame) -> List[Dict]:
        """Find swing lows in the data"""
        swing_lows = []
        
        for i in range(5, len(df) - 5):
            current_low = df.iloc[i]['low']
            
            # Check if it's a swing low
            is_swing_low = True
            for j in range(1, 6):
                if (df.iloc[i-j]['low'] <= current_low or 
                    df.iloc[i+j]['low'] <= current_low):
                    is_swing_low = False
                    break
            
            if is_swing_low:
                swing_lows.append({
                    'index': i,
                    'price': current_low,
                    'timestamp': df.iloc[i]['timestamp']
                })
        
        return swing_lows
    
    def _determine_trend(self, swing_highs: List[Dict], swing_lows: List[Dict]) -> str:
        """Determine current market trend"""
        if not swing_highs or not swing_lows:
            return 'SIDEWAYS'
        
        # Get latest swing high and low
        latest_high = swing_highs[-1]
        latest_low = swing_lows[-1]
        
        # Check if we have higher highs and higher lows (uptrend)
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            prev_high = swing_highs[-2]
            prev_low = swing_lows[-2]
            
            if (latest_high['price'] > prev_high['price'] and 
                latest_low['price'] > prev_low['price']):
                return 'UPTREND'
            elif (latest_high['price'] < prev_high['price'] and 
                  latest_low['price'] < prev_low['price']):
                return 'DOWNTREND'
        
        return 'SIDEWAYS'
    
    def _find_recent_structure_breaks(self, df: pd.DataFrame, swing_highs: List[Dict], swing_lows: List[Dict]) -> List[Dict]:
        """Find recent structure breaks (BOS/CHoCH)"""
        breaks = []
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return breaks
        
        # Check for BOS (Break of Structure)
        latest_high = swing_highs[-1]
        latest_low = swing_lows[-1]
        
        # Check if price broke above recent swing high (Bullish BOS)
        if latest_high['index'] < len(df) - 5:
            for i in range(latest_high['index'] + 1, len(df)):
                if df.iloc[i]['close'] > latest_high['price']:
                    breaks.append({
                        'type': 'BOS',
                        'direction': 'BULLISH',
                        'break_price': latest_high['price'],
                        'current_price': df.iloc[i]['close'],
                        'timestamp': df.iloc[i]['timestamp'],
                        'index': i
                    })
                    break
        
        # Check if price broke below recent swing low (Bearish BOS)
        if latest_low['index'] < len(df) - 5:
            for i in range(latest_low['index'] + 1, len(df)):
                if df.iloc[i]['close'] < latest_low['price']:
                    breaks.append({
                        'type': 'BOS',
                        'direction': 'BEARISH',
                        'break_price': latest_low['price'],
                        'current_price': df.iloc[i]['close'],
                        'timestamp': df.iloc[i]['timestamp'],
                        'index': i
                    })
                    break
        
        return breaks
    
    def _confirm_bos(self, df: pd.DataFrame, break_info: Dict) -> bool:
        """Confirm Break of Structure"""
        try:
            break_index = break_info['index']
            
            # Check if BOS is confirmed by subsequent candles
            if break_index + self.bos_confirmation_candles >= len(df):
                return False
            
            # Check if price stays above/below break level
            for i in range(break_index + 1, min(break_index + self.bos_confirmation_candles + 1, len(df))):
                if break_info['direction'] == 'BULLISH':
                    if df.iloc[i]['close'] < break_info['break_price']:
                        return False
                else:  # BEARISH
                    if df.iloc[i]['close'] > break_info['break_price']:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error confirming BOS: {e}")
            return False
    
    def _confirm_choch(self, df: pd.DataFrame, break_info: Dict) -> bool:
        """Confirm Change of Character"""
        try:
            # CHoCH confirmation logic
            # This would be more complex in a real implementation
            return self._confirm_bos(df, break_info)
            
        except Exception as e:
            logger.error(f"Error confirming CHoCH: {e}")
            return False
    
    def _create_bos_signal(self, symbol: Symbol, break_info: Dict, df: pd.DataFrame) -> Optional[TradingSignal]:
        """Create BOS trading signal"""
        try:
            current_price = break_info['current_price']
            break_price = break_info['break_price']
            
            # Calculate entry, target, and stop loss (60% target, 50% stop loss)
            if break_info['direction'] == 'BULLISH':
                entry_price = current_price
                target_price = current_price * 1.6  # 60% target
                stop_loss = current_price * 0.5  # 50% stop loss
                signal_type_name = 'BOS_BUY'
            else:  # BEARISH
                entry_price = current_price
                target_price = current_price * 0.4  # 60% target for sell
                stop_loss = current_price * 1.5  # 50% stop loss for sell
                signal_type_name = 'BOS_SELL'
            
            # Calculate confidence based on break strength
            break_strength = abs(current_price - break_price) / break_price
            confidence = min(0.95, 0.7 + (break_strength * 10))
            
            # Calculate risk-reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            if risk_reward_ratio < self.min_risk_reward_ratio:
                return None
            
            # Get or create signal type
            signal_type, _ = SignalType.objects.get_or_create(
                name=signal_type_name,
                defaults={'description': f'Break of Structure {break_info["direction"]} Signal'}
            )
            
            # Create signal
            signal = TradingSignal(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                confidence_score=confidence,
                risk_reward_ratio=risk_reward_ratio,
                quality_score=confidence,
                strength='STRONG' if confidence > 0.8 else 'MEDIUM',
                notes=f"BOS {break_info['direction']} - Break: {break_price:.4f}, Current: {current_price:.4f}",
                is_valid=True,
                expires_at=timezone.now() + timezone.timedelta(hours=24)
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating BOS signal: {e}")
            return None
    
    def _create_choch_signal(self, symbol: Symbol, break_info: Dict, df: pd.DataFrame) -> Optional[TradingSignal]:
        """Create CHoCH trading signal"""
        try:
            # Similar to BOS but with CHoCH-specific logic
            signal = self._create_bos_signal(symbol, break_info, df)
            if signal:
                signal.signal_type.name = f"CHoCH_{break_info['direction']}"
                signal.notes = f"CHoCH {break_info['direction']} - Change of Character detected"
                signal.confidence_score = min(0.95, signal.confidence_score + 0.05)  # Slightly higher confidence
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating CHoCH signal: {e}")
            return None
    
    def _find_order_blocks(self, df: pd.DataFrame) -> List[Dict]:
        """Find order blocks in the data"""
        order_blocks = []
        
        for i in range(10, len(df) - 5):
            # Look for strong moves followed by consolidation
            current_candle = df.iloc[i]
            prev_candle = df.iloc[i-1]
            
            # Check for strong bullish move
            if (current_candle['close'] > current_candle['open'] and 
                current_candle['close'] > prev_candle['high'] and
                (current_candle['close'] - current_candle['open']) / current_candle['open'] > 0.02):
                
                # Check for subsequent consolidation
                consolidation = True
                for j in range(i+1, min(i+5, len(df))):
                    if df.iloc[j]['close'] < current_candle['open']:
                        consolidation = False
                        break
                
                if consolidation:
                    order_blocks.append({
                        'index': i,
                        'type': 'BULLISH',
                        'support': current_candle['open'],
                        'resistance': current_candle['close'],
                        'timestamp': current_candle['timestamp']
                    })
            
            # Check for strong bearish move
            elif (current_candle['close'] < current_candle['open'] and 
                  current_candle['close'] < prev_candle['low'] and
                  (current_candle['open'] - current_candle['close']) / current_candle['open'] > 0.02):
                
                # Check for subsequent consolidation
                consolidation = True
                for j in range(i+1, min(i+5, len(df))):
                    if df.iloc[j]['close'] > current_candle['open']:
                        consolidation = False
                        break
                
                if consolidation:
                    order_blocks.append({
                        'index': i,
                        'type': 'BEARISH',
                        'support': current_candle['close'],
                        'resistance': current_candle['open'],
                        'timestamp': current_candle['timestamp']
                    })
        
        return order_blocks
    
    def _validate_order_block(self, df: pd.DataFrame, ob: Dict) -> bool:
        """Validate order block"""
        try:
            # Check if order block is still valid (not broken)
            ob_index = ob['index']
            
            for i in range(ob_index + 1, len(df)):
                if ob['type'] == 'BULLISH':
                    if df.iloc[i]['close'] < ob['support']:
                        return False
                else:  # BEARISH
                    if df.iloc[i]['close'] > ob['resistance']:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating order block: {e}")
            return False
    
    def _create_order_block_signal(self, symbol: Symbol, ob: Dict, df: pd.DataFrame) -> Optional[TradingSignal]:
        """Create order block signal"""
        try:
            current_price = df.iloc[-1]['close']
            
            if ob['type'] == 'BULLISH' and current_price > ob['support']:
                entry_price = current_price
                target_price = current_price * 1.6  # 60% target
                stop_loss = current_price * 0.5  # 50% stop loss
                signal_type_name = 'ORDER_BLOCK_BUY'
            elif ob['type'] == 'BEARISH' and current_price < ob['resistance']:
                entry_price = current_price
                target_price = current_price * 0.4  # 60% target for sell
                stop_loss = current_price * 1.5  # 50% stop loss for sell
                signal_type_name = 'ORDER_BLOCK_SELL'
            else:
                return None
            
            # Calculate confidence and risk-reward
            confidence = 0.75
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            if risk_reward_ratio < self.min_risk_reward_ratio:
                return None
            
            # Get or create signal type
            signal_type, _ = SignalType.objects.get_or_create(
                name=signal_type_name,
                defaults={'description': f'Order Block {ob["type"]} Signal'}
            )
            
            # Create signal
            signal = TradingSignal(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                confidence_score=confidence,
                risk_reward_ratio=risk_reward_ratio,
                quality_score=confidence,
                strength='MEDIUM',
                notes=f"Order Block {ob['type']} - Support: {ob['support']:.4f}, Resistance: {ob['resistance']:.4f}",
                is_valid=True,
                expires_at=timezone.now() + timezone.timedelta(hours=24)
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating order block signal: {e}")
            return None
    
    def _find_liquidity_sweeps(self, df: pd.DataFrame, structure: Dict) -> List[Dict]:
        """Find liquidity sweeps"""
        sweeps = []
        
        # This is a simplified implementation
        # In practice, liquidity sweeps are more complex to detect
        
        return sweeps
    
    def _validate_liquidity_sweep(self, df: pd.DataFrame, sweep: Dict) -> bool:
        """Validate liquidity sweep"""
        return True  # Simplified implementation
    
    def _create_liquidity_sweep_signal(self, symbol: Symbol, sweep: Dict, df: pd.DataFrame) -> Optional[TradingSignal]:
        """Create liquidity sweep signal"""
        return None  # Simplified implementation
    
    def _is_price_approaching_fvg(self, current_price: float, fvg: Dict) -> bool:
        """Check if price is approaching Fair Value Gap"""
        try:
            if fvg['type'] == 'BULLISH':
                return current_price <= fvg['end'] * 1.01  # Within 1% of FVG
            else:  # BEARISH
                return current_price >= fvg['start'] * 0.99  # Within 1% of FVG
        except:
            return False
    
    def _create_fvg_signal(self, symbol: Symbol, fvg: Dict, current_price: float) -> Optional[TradingSignal]:
        """Create FVG signal"""
        try:
            if fvg['type'] == 'BULLISH':
                entry_price = current_price
                target_price = fvg['start']
                stop_loss = fvg['end'] * 0.999
                signal_type_name = 'FVG_BUY'
            else:  # BEARISH
                entry_price = current_price
                target_price = fvg['start']
                stop_loss = fvg['end'] * 1.001
                signal_type_name = 'FVG_SELL'
            
            # Calculate confidence based on FVG strength
            confidence = min(0.9, 0.6 + fvg['strength'] * 10)
            
            # Get or create signal type
            signal_type, _ = SignalType.objects.get_or_create(
                name=signal_type_name,
                defaults={'description': f'Fair Value Gap {fvg["type"]} Signal'}
            )
            
            # Create signal
            signal = TradingSignal(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=Decimal(str(entry_price)),
                target_price=Decimal(str(target_price)),
                stop_loss=Decimal(str(stop_loss)),
                confidence_score=confidence,
                risk_reward_ratio=2.0,  # Default for FVG
                quality_score=confidence,
                strength='MEDIUM',
                notes=f"FVG {fvg['type']} - Strength: {fvg['strength']:.3f}",
                is_valid=True,
                expires_at=timezone.now() + timezone.timedelta(hours=24)
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating FVG signal: {e}")
            return None


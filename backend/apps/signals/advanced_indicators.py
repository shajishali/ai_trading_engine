"""
Advanced Technical Indicators Service
Implements LuxAlgo indicators and Smart Money Concepts (SMC) for enhanced signal generation
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q

from apps.data.models import TechnicalIndicator, MarketData
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


class AdvancedIndicatorsService:
    """Service for calculating advanced technical indicators including LuxAlgo indicators"""
    
    def __init__(self):
        self.name = "AdvancedIndicatorsService"
        
    def calculate_fair_value_gap(self, symbol: Symbol, lookback: int = 50) -> Optional[Dict]:
        """
        Calculate Fair Value Gap (FVG) indicator
        FVG occurs when there's a gap between candles without price action
        """
        try:
            # Get market data
            market_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:lookback]
            
            if len(market_data) < 3:
                return None
                
            # Convert to pandas DataFrame
            df = pd.DataFrame([{
                'timestamp': data.timestamp,
                'open': float(data.open_price),
                'high': float(data.high_price),
                'low': float(data.low_price),
                'close': float(data.close_price),
                'volume': float(data.volume)
            } for data in market_data])
            
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            fvg_data = []
            
            for i in range(1, len(df) - 1):
                prev_candle = df.iloc[i-1]
                current_candle = df.iloc[i]
                next_candle = df.iloc[i+1]
                
                # Bullish FVG: Previous candle high < Next candle low
                if prev_candle['high'] < next_candle['low']:
                    fvg_data.append({
                        'type': 'BULLISH',
                        'start': prev_candle['high'],
                        'end': next_candle['low'],
                        'strength': (next_candle['low'] - prev_candle['high']) / prev_candle['close'],
                        'timestamp': current_candle['timestamp']
                    })
                
                # Bearish FVG: Previous candle low > Next candle high
                elif prev_candle['low'] > next_candle['high']:
                    fvg_data.append({
                        'type': 'BEARISH',
                        'start': next_candle['high'],
                        'end': prev_candle['low'],
                        'strength': (prev_candle['low'] - next_candle['high']) / prev_candle['close'],
                        'timestamp': current_candle['timestamp']
                    })
            
            return {
                'fvg_data': fvg_data,
                'latest_fvg': fvg_data[-1] if fvg_data else None,
                'fvg_count': len(fvg_data)
            }
            
        except Exception as e:
            logger.error(f"Error calculating FVG for {symbol.symbol}: {e}")
            return None
    
    def calculate_liquidity_swings(self, symbol: Symbol, lookback: int = 100) -> Optional[Dict]:
        """
        Calculate Liquidity Swings indicator
        Identifies areas where liquidity is likely to be found
        """
        try:
            market_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:lookback]
            
            if len(market_data) < 20:
                return None
                
            df = pd.DataFrame([{
                'timestamp': data.timestamp,
                'open': float(data.open_price),
                'high': float(data.high_price),
                'low': float(data.low_price),
                'close': float(data.close_price),
                'volume': float(data.volume)
            } for data in market_data])
            
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Calculate swing highs and lows
            swing_highs = []
            swing_lows = []
            
            for i in range(5, len(df) - 5):
                current_high = df.iloc[i]['high']
                current_low = df.iloc[i]['low']
                
                # Check for swing high
                if all(current_high > df.iloc[i-j]['high'] for j in range(1, 6)) and \
                   all(current_high > df.iloc[i+j]['high'] for j in range(1, 6)):
                    swing_highs.append({
                        'price': current_high,
                        'timestamp': df.iloc[i]['timestamp'],
                        'strength': self._calculate_swing_strength(df, i, 'high')
                    })
                
                # Check for swing low
                if all(current_low < df.iloc[i-j]['low'] for j in range(1, 6)) and \
                   all(current_low < df.iloc[i+j]['low'] for j in range(1, 6)):
                    swing_lows.append({
                        'price': current_low,
                        'timestamp': df.iloc[i]['timestamp'],
                        'strength': self._calculate_swing_strength(df, i, 'low')
                    })
            
            return {
                'swing_highs': swing_highs,
                'swing_lows': swing_lows,
                'latest_swing_high': swing_highs[-1] if swing_highs else None,
                'latest_swing_low': swing_lows[-1] if swing_lows else None
            }
            
        except Exception as e:
            logger.error(f"Error calculating Liquidity Swings for {symbol.symbol}: {e}")
            return None
    
    def calculate_nadaraya_watson_envelope(self, symbol: Symbol, period: int = 20, bandwidth: float = 0.1) -> Optional[Dict]:
        """
        Calculate Nadaraya-Watson Envelope indicator
        Creates dynamic support and resistance levels
        """
        try:
            market_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:period * 2]
            
            if len(market_data) < period:
                return None
                
            df = pd.DataFrame([{
                'timestamp': data.timestamp,
                'close': float(data.close_price)
            } for data in market_data])
            
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Calculate Nadaraya-Watson regression
            x = np.arange(len(df))
            y = df['close'].values
            
            # Calculate weights using Gaussian kernel
            weights = np.exp(-0.5 * ((x - len(x) + 1) / (bandwidth * len(x))) ** 2)
            
            # Calculate weighted regression
            weighted_sum = np.sum(weights * y)
            weight_sum = np.sum(weights)
            
            if weight_sum == 0:
                return None
                
            nw_value = weighted_sum / weight_sum
            
            # Calculate envelope bands
            price_std = np.std(y)
            upper_band = nw_value + (2 * price_std)
            lower_band = nw_value - (2 * price_std)
            
            return {
                'nw_value': nw_value,
                'upper_band': upper_band,
                'lower_band': lower_band,
                'current_price': float(df.iloc[-1]['close']),
                'timestamp': df.iloc[-1]['timestamp']
            }
            
        except Exception as e:
            logger.error(f"Error calculating Nadaraya-Watson Envelope for {symbol.symbol}: {e}")
            return None
    
    def calculate_pivot_points(self, symbol: Symbol, period: int = 1) -> Optional[Dict]:
        """
        Calculate Standard Pivot Points
        """
        try:
            market_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:period + 1]
            
            if len(market_data) < period + 1:
                return None
                
            # Get previous day's OHLC
            prev_data = market_data[1]  # Previous day
            high = float(prev_data.high_price)
            low = float(prev_data.low_price)
            close = float(prev_data.close_price)
            
            # Calculate pivot point
            pivot = (high + low + close) / 3
            
            # Calculate resistance and support levels
            r1 = 2 * pivot - low
            r2 = pivot + (high - low)
            r3 = high + 2 * (pivot - low)
            
            s1 = 2 * pivot - high
            s2 = pivot - (high - low)
            s3 = low - 2 * (high - pivot)
            
            return {
                'pivot': pivot,
                'r1': r1, 'r2': r2, 'r3': r3,
                's1': s1, 's2': s2, 's3': s3,
                'timestamp': market_data[0].timestamp
            }
            
        except Exception as e:
            logger.error(f"Error calculating Pivot Points for {symbol.symbol}: {e}")
            return None
    
    def calculate_rsi_divergence(self, symbol: Symbol, period: int = 14, lookback: int = 50) -> Optional[Dict]:
        """
        Calculate RSI Divergence indicator
        Identifies divergences between price and RSI
        """
        try:
            market_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:lookback]
            
            if len(market_data) < period + 10:
                return None
                
            df = pd.DataFrame([{
                'timestamp': data.timestamp,
                'close': float(data.close_price)
            } for data in market_data])
            
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Calculate RSI
            rsi_values = self._calculate_rsi_values(df['close'].values, period)
            df['rsi'] = rsi_values
            
            # Find divergences
            divergences = []
            
            for i in range(period + 5, len(df) - 5):
                # Look for price and RSI peaks/troughs
                price_peak = self._is_peak(df['close'].values, i, 5)
                rsi_peak = self._is_peak(df['rsi'].values, i, 5)
                
                price_trough = self._is_trough(df['close'].values, i, 5)
                rsi_trough = self._is_trough(df['rsi'].values, i, 5)
                
                # Bullish divergence: Price makes lower low, RSI makes higher low
                if price_trough and rsi_trough:
                    prev_trough_idx = self._find_previous_trough(df['close'].values, i)
                    if prev_trough_idx is not None:
                        if (df.iloc[i]['close'] < df.iloc[prev_trough_idx]['close'] and 
                            df.iloc[i]['rsi'] > df.iloc[prev_trough_idx]['rsi']):
                            divergences.append({
                                'type': 'BULLISH_DIVERGENCE',
                                'timestamp': df.iloc[i]['timestamp'],
                                'strength': abs(df.iloc[i]['rsi'] - df.iloc[prev_trough_idx]['rsi'])
                            })
                
                # Bearish divergence: Price makes higher high, RSI makes lower high
                if price_peak and rsi_peak:
                    prev_peak_idx = self._find_previous_peak(df['close'].values, i)
                    if prev_peak_idx is not None:
                        if (df.iloc[i]['close'] > df.iloc[prev_peak_idx]['close'] and 
                            df.iloc[i]['rsi'] < df.iloc[prev_peak_idx]['rsi']):
                            divergences.append({
                                'type': 'BEARISH_DIVERGENCE',
                                'timestamp': df.iloc[i]['timestamp'],
                                'strength': abs(df.iloc[i]['rsi'] - df.iloc[prev_peak_idx]['rsi'])
                            })
            
            return {
                'divergences': divergences,
                'latest_divergence': divergences[-1] if divergences else None,
                'divergence_count': len(divergences)
            }
            
        except Exception as e:
            logger.error(f"Error calculating RSI Divergence for {symbol.symbol}: {e}")
            return None
    
    def calculate_stochastic_rsi(self, symbol: Symbol, rsi_period: int = 14, stoch_period: int = 14) -> Optional[Dict]:
        """
        Calculate Stochastic RSI indicator
        """
        try:
            market_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:rsi_period + stoch_period + 10]
            
            if len(market_data) < rsi_period + stoch_period:
                return None
                
            df = pd.DataFrame([{
                'timestamp': data.timestamp,
                'close': float(data.close_price)
            } for data in market_data])
            
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Calculate RSI
            rsi_values = self._calculate_rsi_values(df['close'].values, rsi_period)
            df['rsi'] = rsi_values
            
            # Calculate Stochastic RSI
            stoch_rsi_values = []
            for i in range(rsi_period + stoch_period - 1, len(df)):
                rsi_window = df['rsi'].iloc[i-stoch_period+1:i+1]
                rsi_min = rsi_window.min()
                rsi_max = rsi_window.max()
                
                if rsi_max - rsi_min == 0:
                    stoch_rsi = 50
                else:
                    stoch_rsi = ((df.iloc[i]['rsi'] - rsi_min) / (rsi_max - rsi_min)) * 100
                
                stoch_rsi_values.append(stoch_rsi)
            
            # Pad with None values for alignment
            stoch_rsi_values = [None] * (rsi_period + stoch_period - 1) + stoch_rsi_values
            df['stoch_rsi'] = stoch_rsi_values
            
            latest_stoch_rsi = stoch_rsi_values[-1] if stoch_rsi_values else None
            
            return {
                'stoch_rsi': latest_stoch_rsi,
                'timestamp': df.iloc[-1]['timestamp'],
                'overbought': latest_stoch_rsi > 80 if latest_stoch_rsi else False,
                'oversold': latest_stoch_rsi < 20 if latest_stoch_rsi else False
            }
            
        except Exception as e:
            logger.error(f"Error calculating Stochastic RSI for {symbol.symbol}: {e}")
            return None
    
    def _calculate_swing_strength(self, df: pd.DataFrame, idx: int, swing_type: str) -> float:
        """Calculate the strength of a swing point"""
        try:
            if swing_type == 'high':
                current_value = df.iloc[idx]['high']
                # Compare with surrounding values
                surrounding_values = []
                for i in range(max(0, idx-5), min(len(df), idx+6)):
                    if i != idx:
                        surrounding_values.append(df.iloc[i]['high'])
                
                if surrounding_values:
                    avg_surrounding = np.mean(surrounding_values)
                    return (current_value - avg_surrounding) / avg_surrounding
            else:  # low
                current_value = df.iloc[idx]['low']
                surrounding_values = []
                for i in range(max(0, idx-5), min(len(df), idx+6)):
                    if i != idx:
                        surrounding_values.append(df.iloc[i]['low'])
                
                if surrounding_values:
                    avg_surrounding = np.mean(surrounding_values)
                    return (avg_surrounding - current_value) / avg_surrounding
            
            return 0.0
        except:
            return 0.0
    
    def _calculate_rsi_values(self, prices: np.ndarray, period: int) -> List[float]:
        """Calculate RSI values"""
        try:
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gains = []
            avg_losses = []
            
            for i in range(len(prices)):
                if i < period:
                    avg_gains.append(None)
                    avg_losses.append(None)
                else:
                    avg_gain = np.mean(gains[i-period:i])
                    avg_loss = np.mean(losses[i-period:i])
                    avg_gains.append(avg_gain)
                    avg_losses.append(avg_loss)
            
            rsi_values = []
            for i in range(len(prices)):
                if avg_gains[i] is None or avg_losses[i] is None:
                    rsi_values.append(None)
                else:
                    if avg_losses[i] == 0:
                        rsi = 100
                    else:
                        rs = avg_gains[i] / avg_losses[i]
                        rsi = 100 - (100 / (1 + rs))
                    rsi_values.append(rsi)
            
            return rsi_values
        except:
            return [None] * len(prices)
    
    def _is_peak(self, values: np.ndarray, idx: int, window: int) -> bool:
        """Check if value at index is a peak"""
        if idx < window or idx >= len(values) - window:
            return False
        
        current = values[idx]
        for i in range(idx - window, idx + window + 1):
            if i != idx and values[i] >= current:
                return False
        return True
    
    def _is_trough(self, values: np.ndarray, idx: int, window: int) -> bool:
        """Check if value at index is a trough"""
        if idx < window or idx >= len(values) - window:
            return False
        
        current = values[idx]
        for i in range(idx - window, idx + window + 1):
            if i != idx and values[i] <= current:
                return False
        return True
    
    def _find_previous_peak(self, values: np.ndarray, current_idx: int) -> Optional[int]:
        """Find the previous peak before current index"""
        for i in range(current_idx - 1, 0, -1):
            if self._is_peak(values, i, 3):
                return i
        return None
    
    def _find_previous_trough(self, values: np.ndarray, current_idx: int) -> Optional[int]:
        """Find the previous trough before current index"""
        for i in range(current_idx - 1, 0, -1):
            if self._is_trough(values, i, 3):
                return i
        return None


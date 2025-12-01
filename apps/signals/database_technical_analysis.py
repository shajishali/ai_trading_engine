"""
Database-based technical analysis for signal generation
Phase 4: Calculate technical indicators using stored OHLCV data
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal

from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.database_data_utils import get_recent_market_data

logger = logging.getLogger(__name__)


class DatabaseTechnicalAnalysis:
    """Calculate technical indicators from database data"""
    
    def __init__(self):
        self.default_periods = {
            'sma_short': 20,
            'sma_long': 50,
            'ema_short': 12,
            'ema_long': 26,
            'rsi_period': 14,
            'macd_signal': 9,
            'bollinger_period': 20,
            'bollinger_std': 2,
            'stoch_k': 14,
            'stoch_d': 3,
            'williams_r': 14,
            'cci_period': 20,
            'atr_period': 14
        }
    
    def calculate_indicators_from_database(self, symbol: Symbol, hours_back: int = 168) -> Optional[Dict[str, float]]:
        """Calculate indicators using database data (default: 1 week)"""
        try:
            logger.info(f"Calculating indicators for {symbol.symbol} ({hours_back} hours)")
            
            # Get market data from database
            market_data = get_recent_market_data(symbol, hours_back)
            
            if market_data.empty:
                logger.warning(f"No market data available for {symbol.symbol}")
                return None
            
            if len(market_data) < 50:  # Need minimum data for reliable indicators
                logger.warning(f"Insufficient data for {symbol.symbol}: {len(market_data)} records")
                return None
            
            # Calculate all indicators
            indicators = self._calculate_all_indicators(market_data)
            
            # Store indicators in database
            self._store_indicators(symbol, indicators, market_data.iloc[-1]['timestamp'])
            
            logger.info(f"Calculated {len(indicators)} indicators for {symbol.symbol}")
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol.symbol}: {e}")
            return None
    
    def _calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate all technical indicators"""
        try:
            indicators = {}
            
            # Ensure data is sorted by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Price data
            close_prices = df['close_price']
            high_prices = df['high_price']
            low_prices = df['low_price']
            open_prices = df['open_price']
            volumes = df['volume']
            
            # Moving Averages
            indicators.update(self._calculate_moving_averages(close_prices))
            
            # RSI
            indicators['rsi'] = self._calculate_rsi(close_prices)
            
            # MACD
            indicators.update(self._calculate_macd(close_prices))
            
            # Bollinger Bands
            indicators.update(self._calculate_bollinger_bands(close_prices))
            
            # Stochastic Oscillator
            indicators.update(self._calculate_stochastic(high_prices, low_prices, close_prices))
            
            # Williams %R
            indicators['williams_r'] = self._calculate_williams_r(high_prices, low_prices, close_prices)
            
            # Commodity Channel Index (CCI)
            indicators['cci'] = self._calculate_cci(high_prices, low_prices, close_prices)
            
            # Average True Range (ATR)
            indicators['atr'] = self._calculate_atr(high_prices, low_prices, close_prices)
            
            # Volume indicators
            indicators.update(self._calculate_volume_indicators(close_prices, volumes))
            
            # Trend indicators
            indicators.update(self._calculate_trend_indicators(close_prices, high_prices, low_prices))
            
            # Momentum indicators
            indicators.update(self._calculate_momentum_indicators(close_prices))
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
    
    def _calculate_moving_averages(self, prices: pd.Series) -> Dict[str, float]:
        """Calculate Simple and Exponential Moving Averages"""
        try:
            sma_20 = prices.rolling(window=self.default_periods['sma_short']).mean()
            sma_50 = prices.rolling(window=self.default_periods['sma_long']).mean()
            
            ema_12 = prices.ewm(span=self.default_periods['ema_short']).mean()
            ema_26 = prices.ewm(span=self.default_periods['ema_long']).mean()
            
            return {
                'sma_20': float(sma_20.iloc[-1]) if not pd.isna(sma_20.iloc[-1]) else 0.0,
                'sma_50': float(sma_50.iloc[-1]) if not pd.isna(sma_50.iloc[-1]) else 0.0,
                'ema_12': float(ema_12.iloc[-1]) if not pd.isna(ema_12.iloc[-1]) else 0.0,
                'ema_26': float(ema_26.iloc[-1]) if not pd.isna(ema_26.iloc[-1]) else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating moving averages: {e}")
            return {}
    
    def _calculate_rsi(self, prices: pd.Series, period: int = None) -> float:
        """Calculate Relative Strength Index"""
        try:
            if period is None:
                period = self.default_periods['rsi_period']
            
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return 50.0
    
    def _calculate_macd(self, prices: pd.Series) -> Dict[str, float]:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        try:
            ema_12 = prices.ewm(span=self.default_periods['ema_short']).mean()
            ema_26 = prices.ewm(span=self.default_periods['ema_long']).mean()
            
            macd_line = ema_12 - ema_26
            signal_line = macd_line.ewm(span=self.default_periods['macd_signal']).mean()
            histogram = macd_line - signal_line
            
            return {
                'macd': float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0.0,
                'macd_signal': float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else 0.0,
                'macd_histogram': float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return {'macd': 0.0, 'macd_signal': 0.0, 'macd_histogram': 0.0}
    
    def _calculate_bollinger_bands(self, prices: pd.Series) -> Dict[str, float]:
        """Calculate Bollinger Bands"""
        try:
            period = self.default_periods['bollinger_period']
            std_mult = self.default_periods['bollinger_std']
            
            sma = prices.rolling(window=period).mean()
            std = prices.rolling(window=period).std()
            
            upper_band = sma + (std * std_mult)
            lower_band = sma - (std * std_mult)
            
            return {
                'bollinger_upper': float(upper_band.iloc[-1]) if not pd.isna(upper_band.iloc[-1]) else 0.0,
                'bollinger_middle': float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else 0.0,
                'bollinger_lower': float(lower_band.iloc[-1]) if not pd.isna(lower_band.iloc[-1]) else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return {'bollinger_upper': 0.0, 'bollinger_middle': 0.0, 'bollinger_lower': 0.0}
    
    def _calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Dict[str, float]:
        """Calculate Stochastic Oscillator"""
        try:
            k_period = self.default_periods['stoch_k']
            d_period = self.default_periods['stoch_d']
            
            lowest_low = low.rolling(window=k_period).min()
            highest_high = high.rolling(window=k_period).max()
            
            k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
            d_percent = k_percent.rolling(window=d_period).mean()
            
            return {
                'stoch_k': float(k_percent.iloc[-1]) if not pd.isna(k_percent.iloc[-1]) else 50.0,
                'stoch_d': float(d_percent.iloc[-1]) if not pd.isna(d_percent.iloc[-1]) else 50.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating Stochastic: {e}")
            return {'stoch_k': 50.0, 'stoch_d': 50.0}
    
    def _calculate_williams_r(self, high: pd.Series, low: pd.Series, close: pd.Series) -> float:
        """Calculate Williams %R"""
        try:
            period = self.default_periods['williams_r']
            
            highest_high = high.rolling(window=period).max()
            lowest_low = low.rolling(window=period).min()
            
            williams_r = -100 * ((highest_high - close) / (highest_high - lowest_low))
            
            return float(williams_r.iloc[-1]) if not pd.isna(williams_r.iloc[-1]) else -50.0
            
        except Exception as e:
            logger.error(f"Error calculating Williams %R: {e}")
            return -50.0
    
    def _calculate_cci(self, high: pd.Series, low: pd.Series, close: pd.Series) -> float:
        """Calculate Commodity Channel Index"""
        try:
            period = self.default_periods['cci_period']
            
            typical_price = (high + low + close) / 3
            sma_tp = typical_price.rolling(window=period).mean()
            mean_deviation = typical_price.rolling(window=period).apply(
                lambda x: np.mean(np.abs(x - x.mean())), raw=False
            )
            
            cci = (typical_price - sma_tp) / (0.015 * mean_deviation)
            
            return float(cci.iloc[-1]) if not pd.isna(cci.iloc[-1]) else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating CCI: {e}")
            return 0.0
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series) -> float:
        """Calculate Average True Range"""
        try:
            period = self.default_periods['atr_period']
            
            high_low = high - low
            high_close = np.abs(high - close.shift())
            low_close = np.abs(low - close.shift())
            
            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = true_range.rolling(window=period).mean()
            
            return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return 0.0
    
    def _calculate_volume_indicators(self, prices: pd.Series, volumes: pd.Series) -> Dict[str, float]:
        """Calculate volume-based indicators"""
        try:
            # Volume Moving Average
            volume_sma = volumes.rolling(window=20).mean()
            
            # On-Balance Volume (OBV)
            price_change = prices.diff()
            obv = np.where(price_change > 0, volumes, 
                          np.where(price_change < 0, -volumes, 0)).cumsum()
            
            # Volume Rate of Change
            volume_roc = ((volumes - volumes.shift(10)) / volumes.shift(10)) * 100
            
            return {
                'volume_sma': float(volume_sma.iloc[-1]) if not pd.isna(volume_sma.iloc[-1]) else 0.0,
                'obv': float(obv[-1]) if not pd.isna(obv[-1]) else 0.0,
                'volume_roc': float(volume_roc.iloc[-1]) if not pd.isna(volume_roc.iloc[-1]) else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating volume indicators: {e}")
            return {'volume_sma': 0.0, 'obv': 0.0, 'volume_roc': 0.0}
    
    def _calculate_trend_indicators(self, close: pd.Series, high: pd.Series, low: pd.Series) -> Dict[str, float]:
        """Calculate trend indicators"""
        try:
            # ADX (Average Directional Index)
            adx = self._calculate_adx(high, low, close)
            
            # Parabolic SAR
            sar = self._calculate_parabolic_sar(high, low, close)
            
            # Ichimoku Cloud (simplified)
            ichimoku = self._calculate_ichimoku(high, low, close)
            
            return {
                'adx': adx,
                'sar': sar,
                **ichimoku
            }
            
        except Exception as e:
            logger.error(f"Error calculating trend indicators: {e}")
            return {'adx': 0.0, 'sar': 0.0}
    
    def _calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series) -> float:
        """Calculate Average Directional Index"""
        try:
            period = 14
            
            # True Range
            high_low = high - low
            high_close = np.abs(high - close.shift())
            low_close = np.abs(low - close.shift())
            tr = np.maximum(high_low, np.maximum(high_close, low_close))
            
            # Directional Movement
            dm_plus = np.where((high.diff() > low.diff().abs()) & (high.diff() > 0), high.diff(), 0)
            dm_minus = np.where((low.diff().abs() > high.diff()) & (low.diff() < 0), low.diff().abs(), 0)
            
            # Smoothed values
            tr_smooth = tr.rolling(window=period).mean()
            dm_plus_smooth = pd.Series(dm_plus).rolling(window=period).mean()
            dm_minus_smooth = pd.Series(dm_minus).rolling(window=period).mean()
            
            # DI values
            di_plus = 100 * (dm_plus_smooth / tr_smooth)
            di_minus = 100 * (dm_minus_smooth / tr_smooth)
            
            # ADX
            dx = 100 * np.abs(di_plus - di_minus) / (di_plus + di_minus)
            adx = dx.rolling(window=period).mean()
            
            return float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating ADX: {e}")
            return 0.0
    
    def _calculate_parabolic_sar(self, high: pd.Series, low: pd.Series, close: pd.Series) -> float:
        """Calculate Parabolic SAR (simplified)"""
        try:
            # Simplified Parabolic SAR calculation
            # In a full implementation, this would be more complex
            return float(close.iloc[-1] * 0.98)  # Simplified calculation
            
        except Exception as e:
            logger.error(f"Error calculating Parabolic SAR: {e}")
            return 0.0
    
    def _calculate_ichimoku(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Dict[str, float]:
        """Calculate Ichimoku Cloud (simplified)"""
        try:
            # Simplified Ichimoku calculation
            tenkan_period = 9
            kijun_period = 26
            senkou_period = 52
            
            tenkan_sen = (high.rolling(window=tenkan_period).max() + 
                         low.rolling(window=tenkan_period).min()) / 2
            
            kijun_sen = (high.rolling(window=kijun_period).max() + 
                        low.rolling(window=kijun_period).min()) / 2
            
            return {
                'tenkan_sen': float(tenkan_sen.iloc[-1]) if not pd.isna(tenkan_sen.iloc[-1]) else 0.0,
                'kijun_sen': float(kijun_sen.iloc[-1]) if not pd.isna(kijun_sen.iloc[-1]) else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating Ichimoku: {e}")
            return {'tenkan_sen': 0.0, 'kijun_sen': 0.0}
    
    def _calculate_momentum_indicators(self, prices: pd.Series) -> Dict[str, float]:
        """Calculate momentum indicators"""
        try:
            # Rate of Change (ROC)
            roc_10 = ((prices - prices.shift(10)) / prices.shift(10)) * 100
            roc_20 = ((prices - prices.shift(20)) / prices.shift(20)) * 100
            
            # Momentum
            momentum_10 = prices - prices.shift(10)
            momentum_20 = prices - prices.shift(20)
            
            return {
                'roc_10': float(roc_10.iloc[-1]) if not pd.isna(roc_10.iloc[-1]) else 0.0,
                'roc_20': float(roc_20.iloc[-1]) if not pd.isna(roc_20.iloc[-1]) else 0.0,
                'momentum_10': float(momentum_10.iloc[-1]) if not pd.isna(momentum_10.iloc[-1]) else 0.0,
                'momentum_20': float(momentum_20.iloc[-1]) if not pd.isna(momentum_20.iloc[-1]) else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating momentum indicators: {e}")
            return {'roc_10': 0.0, 'roc_20': 0.0, 'momentum_10': 0.0, 'momentum_20': 0.0}
    
    def _store_indicators(self, symbol: Symbol, indicators: Dict[str, float], timestamp: datetime):
        """Store calculated indicators in database"""
        try:
            # Create or update TechnicalIndicator record
            indicator, created = TechnicalIndicator.objects.get_or_create(
                symbol=symbol,
                timestamp=timestamp,
                defaults=indicators
            )
            
            if not created:
                # Update existing record
                for key, value in indicators.items():
                    setattr(indicator, key, value)
                indicator.save()
            
            logger.debug(f"Stored indicators for {symbol.symbol} at {timestamp}")
            
        except Exception as e:
            logger.error(f"Error storing indicators: {e}")
    
    def get_latest_indicators(self, symbol: Symbol) -> Optional[Dict[str, float]]:
        """Get latest calculated indicators for a symbol"""
        try:
            latest_indicator = TechnicalIndicator.objects.filter(
                symbol=symbol
            ).order_by('-timestamp').first()
            
            if not latest_indicator:
                return None
            
            # Convert to dictionary
            indicators = {}
            for field in latest_indicator._meta.fields:
                if field.name not in ['id', 'symbol', 'timestamp', 'created_at', 'updated_at']:
                    value = getattr(latest_indicator, field.name)
                    if value is not None:
                        indicators[field.name] = float(value)
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error getting latest indicators: {e}")
            return None
    
    def calculate_signal_strength(self, indicators: Dict[str, float]) -> float:
        """Calculate overall signal strength based on indicators"""
        try:
            if not indicators:
                return 0.0
            
            strength_score = 0.0
            total_weight = 0.0
            
            # RSI weight
            if 'rsi' in indicators:
                rsi = indicators['rsi']
                if rsi > 70:
                    strength_score += -0.3  # Overbought
                elif rsi < 30:
                    strength_score += 0.3   # Oversold
                else:
                    strength_score += 0.1  # Neutral
                total_weight += 1.0
            
            # MACD weight
            if 'macd' in indicators and 'macd_signal' in indicators:
                macd = indicators['macd']
                signal = indicators['macd_signal']
                if macd > signal:
                    strength_score += 0.2
                else:
                    strength_score += -0.2
                total_weight += 1.0
            
            # Bollinger Bands weight
            if all(key in indicators for key in ['bollinger_upper', 'bollinger_lower']):
                price = indicators.get('close_price', 0)
                upper = indicators['bollinger_upper']
                lower = indicators['bollinger_lower']
                
                if price > upper:
                    strength_score += -0.2  # Above upper band
                elif price < lower:
                    strength_score += 0.2   # Below lower band
                else:
                    strength_score += 0.1   # Within bands
                total_weight += 1.0
            
            # Moving Average weight
            if 'sma_20' in indicators and 'sma_50' in indicators:
                sma_20 = indicators['sma_20']
                sma_50 = indicators['sma_50']
                if sma_20 > sma_50:
                    strength_score += 0.2
                else:
                    strength_score += -0.2
                total_weight += 1.0
            
            # Normalize score
            if total_weight > 0:
                return max(-1.0, min(1.0, strength_score / total_weight))
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating signal strength: {e}")
            return 0.0


# Global instance
database_technical_analysis = DatabaseTechnicalAnalysis()
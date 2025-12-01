"""
30-Minute Timeframe Strategy Service

Implements trading strategy based on 30-minute timeframe analysis:
- Uses previous high (resistance) as take profit for SELL signals and stop loss for BUY signals
- Uses previous low (support) as take profit for BUY signals and stop loss for SELL signals
- Predicts levels when previous high/low not clearly visible on chart
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import logging

from apps.data.models import MarketData, Symbol
from apps.data.services import TechnicalAnalysisService

logger = logging.getLogger(__name__)


class ThirtyMinuteStrategyService:
    """Service for 30-minute timeframe strategy implementation"""
    
    def __init__(self):
        self.ta_service = TechnicalAnalysisService()
        self.lookback_periods = 50  # Look back 50 periods (25 hours) to find levels
        self.support_resistance_buffer = 0.02  # 2% buffer for level validation
        self.min_distance_percentage = 0.05  # At least 5% distance between levels
        
        # Symbol mapping for USDT pairs to base symbols (for MarketData lookup)
        self.symbol_mapping = {
            'BTCUSDT': 'BTC',
            'ETHUSDT': 'ETH',
            'BNBUSDT': 'BNB',
            'ADAUSDT': 'ADA',
            'XRPUSDT': 'XRP',
            'SOLUSDT': 'SOL',
            'DOGEUSDT': 'DOGE',
            'DOTUSDT': 'DOT',
            'LINKUSDT': 'LINK',
            'LTCUSDT': 'LTC',
            'AVAXUSDT': 'AVAX',
            'MATICUSDT': 'MATIC',
            'UNIUSDT': 'UNI',
            'ATOMUSDT': 'ATOM',
            'FILUSDT': 'FIL',
            'TRXUSDT': 'TRX',
            'ETCUSDT': 'ETC',
            'XLMUSDT': 'XLM',
            'VETUSDT': 'VET',
            'ICPUSDT': 'ICP',
            'THETAUSDT': 'THETA',
            'ALGOUSDT': 'ALGO',
            'FTMUSDT': 'FTM',
            'HBARUSDT': 'HBAR',
            'NEARUSDT': 'NEAR',
            'EGLDUSDT': 'EGLD',
            'AAVEUSDT': 'AAVE',
            'COMPUSDT': 'COMP',
            'CRVUSDT': 'CRV',
            'LDOUSDT': 'LDO',
            'CAKEUSDT': 'CAKE',
            'PENDLEUSDT': 'PENDLE',
            'DYDXUSDT': 'DYDX',
            'FETUSDT': 'FET',
            'CROUSDT': 'CRO',
            'KCSUSDT': 'KCS',
            'OKBUSDT': 'OKB',
            'LEOUSDT': 'LEO',
            'QNTUSDT': 'QNT',
            'GRTUSDT': 'GRT',
            'XMRUSDT': 'XMR',
            'ZECUSDT': 'ZEC',
            'DAIUSDT': 'DAI',
            'TUSDUSDT': 'TUSD',
            'GTUSDT': 'GT',
            'APTUSDT': 'APT',
            'OPUSDT': 'OP',
            'ARBUSDT': 'ARB',
            'MKRUSDT': 'MKR',
            'RUNEUSDT': 'RUNE',
            'INJUSDT': 'INJ',
            'STXUSDT': 'STX',
            'SANDUSDT': 'SAND',
            'MANAUSDT': 'MANA',
            'BCHUSDT': 'BCH',
            'DASHUSDT': 'DASH',
            'NEOUSDT': 'NEO',
            'QTUMUSDT': 'QTUM',
        }
    
    def _get_market_data_symbol(self, symbol: Symbol) -> Symbol:
        """
        Get the appropriate symbol for MarketData lookup.
        Maps USDT pairs to base symbols if needed.
        """
        symbol_name = symbol.symbol
        
        # If we have a direct mapping, use the base symbol for MarketData
        if symbol_name in self.symbol_mapping:
            base_symbol_name = self.symbol_mapping[symbol_name]
            base_symbol = Symbol.objects.filter(symbol=base_symbol_name).first()
            if base_symbol:
                logger.debug(f"Mapped {symbol_name} → {base_symbol_name} for MarketData lookup")
                return base_symbol
            else:
                logger.warning(f"Base symbol {base_symbol_name} not found for {symbol_name}")
        
        # Return original symbol if no mapping or mapping failed
        return symbol
        
    def get_thirty_minute_levels(self, symbol: Symbol) -> Dict[str, any]:
        """
        Analyze 30-minute timeframe to find previous high and low levels
        
        Args:
            symbol: Trading symbol to analyze
            
        Returns:
            Dictionary containing resistance, support, and signal levels
        """
        try:
            # Get appropriate symbol for MarketData lookup (with USDT mapping)
            market_data_symbol = self._get_market_data_symbol(symbol)
            
            # Get 30-minute market data
            market_data = MarketData.objects.filter(
                symbol=market_data_symbol
            ).order_by('-timestamp')[:self.lookback_periods * 2]  # Extra data for analysis
            
            if len(market_data) < 10:
                logger.warning(f"Insufficient data for {symbol.symbol} - using predicted levels")
                return self._predict_levels(symbol, market_data)
            
            # Convert to DataFrame for analysis
            df = self._convert_to_dataframe(market_data)
            
            # Find resistance (previous high) and support (previous low)
            resistance_level = self._find_resistance_level(df)
            support_level = self._find_support_level(df)
            
            # Validate levels
            validated_levels = self._validate_levels(df, resistance_level, support_level)
            
            # If levels are not clear, predict them
            if not validated_levels['resistance_found'] or not validated_levels['support_found']:
                logger.info(f"Levels not clear for {symbol.symbol}, using predicted values")
                predicted_levels = self._predict_levels(symbol, market_data)
                validated_levels.update(predicted_levels)
            
            return validated_levels
            
        except Exception as e:
            logger.error(f"Error analyzing 30-minute levels for {symbol.symbol}: {e}")
            return self._get_fallback_levels(symbol)
    
    def _convert_to_dataframe(self, market_data: List[MarketData]) -> pd.DataFrame:
        """Convert market data to pandas DataFrame"""
        data = []
        for md in market_data:
            data.append({
                'timestamp': md.timestamp,
                'open': float(md.open_price),
                'high': float(md.high_price),
                'low': float(md.low_price),
                'close': float(md.close_price),
                'volume': float(md.volume) if md.volume else 0
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('timestamp')
        
        # Add some technical analysis
        df['price_change'] = df['close'].pct_change()
        df['volatility'] = df['price_change'].rolling(window=10).std()
        
        return df
    
    def _find_resistance_level(self, df: pd.DataFrame) -> Optional[float]:
        """Find resistance level (previous high)"""
        try:
            if len(df) < 10:
                return None
            
            # Look for recent peaks
            df['rolling_max'] = df['high'].rolling(window=5, center=True).max()
            peaks = df[df['high'] == df['rolling_max']].copy()
            
            if len(peaks) == 0:
                return None
            
            # Take the most recent significant peak
            recent_peaks = peaks.tail(10)  # Last 10 potential peaks
            current_price = df['close'].iloc[-1]
            
            # Filter peaks that are meaningfully above current price
            significant_peaks = recent_peaks[
                recent_peaks['high'] > current_price * (1 + self.min_distance_percentage)
            ]
            
            if len(significant_peaks) > 0:
                resistance = significant_peaks['high'].max()
                logger.debug(f"Found resistance level: {resistance}")
                return resistance
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding resistance level: {e}")
            return None
    
    def _find_support_level(self, df: pd.DataFrame) -> Optional[float]:
        """Find support level (previous low)"""
        try:
            if len(df) < 10:
                return None
            
            # Look for recent troughs
            df['rolling_min'] = df['low'].rolling(window=5, center=True).min()
            troughs = df[df['low'] == df['rolling_min']].copy()
            
            if len(troughs) == 0:
                return None
            
            # Take the most recent significant trough
            recent_troughs = troughs.tail(10)  # Last 10 potential troughs
            current_price = df['close'].iloc[-1]
            
            # Filter troughs that are meaningfully below current price
            significant_troughs = recent_troughs[
                recent_troughs['low'] < current_price * (1 - self.min_distance_percentage)
            ]
            
            if len(significant_troughs) > 0:
                support = significant_troughs['low'].min()
                logger.debug(f"Found support level: {support}")
                return support
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding support level: {e}")
            return None
    
    def _validate_levels(self, df: pd.DataFrame, resistance: Optional[float], support: Optional[float]) -> Dict[str, any]:
        """Validate found levels and calculate signal targets"""
        current_price = float(df['close'].iloc[-1])
        
        result = {
            'current_price': current_price,
            'resistance_level': resistance,
            'support_level': support,
            'resistance_found': resistance is not None,
            'support_found': support is not None,
            'buy_signal_levels': {},
            'sell_signal_levels': {},
            'strategy': '30_minute_timeframe'
        }
        
        # Calculate BUY signal levels
        if support:
            # For BUY: Support = Take Profit, Resistance = Stop Loss
            result['buy_signal_levels'] = {
                'take_profit': support,
                'stop_loss': resistance if resistance else current_price * 1.08,  # 8% above current
                'signal_type': 'BUY',
                'reasoning': f'Support level {support:.6f} as TP, Resistance {resistance if resistance else current_price * 1.08:.6f} as SL'
            }
        
        # Calculate SELL signal levels  
        if resistance:
            # For SELL: Resistance = Take Profit, Support = Stop Loss
            result['sell_signal_levels'] = {
                'take_profit': resistance,
                'stop_loss': support if support else current_price * 0.92,  # 8% below current
                'signal_type': 'SELL',
                'reasoning': f'Resistance level {resistance:.6f} as TP, Support {support if support else current_price * 0.92:.6f} as SL'
            }
        
        return result
    
    def _predict_levels(self, symbol: Symbol, market_data: List[MarketData]) -> Dict[str, any]:
        """Predict levels when previous high/low not clearly visible"""
        try:
            if len(market_data) < 5:
                return self._get_fallback_levels(symbol)
            
            # Get recent price data for prediction
            recent_market_data = list(market_data)
            recent_data_slice = recent_market_data[-10:] if len(recent_market_data) >= 10 else recent_market_data
            recent_prices = [float(md.close_price) for md in recent_data_slice]
            current_price = recent_prices[-1] if recent_prices else 1.0
            
            # Calculate basic statistics
            price_mean = np.mean(recent_prices)
            price_std = np.std(recent_prices)
            volatility = price_std / price_mean
            
            # Predict levels based on volatility
            prediction_buffer = max(0.05, volatility * 2)  # At least 5% buffer
            
            predicted_resistance = current_price * (1 + prediction_buffer)
            predicted_support = current_price * (1 - prediction_buffer)
            
            logger.info(f"Predicted levels for {symbol.symbol}: "
                       f"Support={predicted_support:.6f}, Resistance={predicted_resistance:.6f}")
            
            return {
                'current_price': current_price,
                'resistance_level': predicted_resistance,
                'support_level': predicted_support,
                'resistance_found': True,
                'support_found': True,
                'levels_predicted': True,
                'prediction_reason': f'Based on volatility {volatility:.4f}, buffer {prediction_buffer:.2f}',
                'buy_signal_levels': {
                    'take_profit': predicted_support,
                    'stop_loss': predicted_resistance,
                    'signal_type': 'BUY',
                    'reasoning': f'Predicted support {predicted_support:.6f} as TP, resistance {predicted_resistance:.6f} as SL'
                },
                'sell_signal_levels': {
                    'take_profit': predicted_resistance,
                    'stop_loss': predicted_support,
                    'signal_type': 'SELL',
                    'reasoning': f'Predicted resistance {predicted_resistance:.6f} as TP, support {predicted_support:.6f} as SL'
                },
                'strategy': '30_minute_timeframe_predicted'
            }
            
        except Exception as e:
            logger.error(f"Error predicting levels for {symbol.symbol}: {e}")
            return self._get_fallback_levels(symbol)
    
    def _get_fallback_levels(self, symbol: Symbol) -> Dict[str, any]:
        """Fallback levels when all else fails"""
        # Try to get latest market data using mapped symbol
        market_data_symbol = self._get_market_data_symbol(symbol)
        latest_md = MarketData.objects.filter(symbol=market_data_symbol).order_by('-timestamp').first()
        current_price = float(latest_md.close_price) if latest_md else 1.0
        
        # Use simple percentage-based levels as fallback
        fallback_resistance = current_price * 1.10  # 10% above
        fallback_support = current_price * 0.90     # 10% below
        
        logger.warning(f"Using fallback levels for {symbol.symbol}: "
                      f"Support={fallback_support:.6f}, Resistance={fallback_resistance:.6f}")
        
        return {
            'current_price': current_price,
            'resistance_level': fallback_resistance,
            'support_level': fallback_support,
            'resistance_found': False,
            'support_found': False,
            'levels_predicted': True,
            'prediction_reason': 'Fallback levels due to insufficient data',
            'buy_signal_levels': {
                'take_profit': fallback_support,
                'stop_loss': fallback_resistance,
                'signal_type': 'BUY',
                'reasoning': f'Fallback support {fallback_support:.6f} as TP, resistance {fallback_resistance:.6f} as SL'
            },
            'sell_signal_levels': {
                'take_profit': fallback_resistance,
                'stop_loss': fallback_support,
                'signal_type': 'SELL',
                'reasoning': f'Fallback resistance {fallback_resistance:.6f} as TP, support {fallback_support:.6f} as SL'
            },
            'strategy': '30_minute_timeframe_fallback'
        }
    
    def calculate_signal_levels(self, symbol: Symbol, signal_type: str) -> Dict[str, any]:
        """
        Calculate take profit and stop loss levels for a specific signal type
        
        Args:
            symbol: Trading symbol
            signal_type: 'BUY' or 'SELL'
            
        Returns:
            Dictionary with signal levels and reasoning
        """
        try:
            # Get 30-minute levels
            levels = self.get_thirty_minute_levels(symbol)
            
            # Extract levels based on signal type
            if signal_type.upper() == 'BUY':
                return levels.get('buy_signal_levels', {})
            elif signal_type.upper() == 'SELL':
                return levels.get('sell_signal_levels', {})
            else:
                logger.error(f"Invalid signal type: {signal_type}")
                return {}
                
        except Exception as e:
            logger.error(f"Error calculating signal levels: {e}")
            return {}
    
    def get_level_analysis_summary(self, symbol: Symbol) -> str:
        """Get human-readable summary of 30-minute level analysis"""
        try:
            levels = self.get_thirty_minute_levels(symbol)
            
            summary = f"30-Minute Analysis for {symbol.symbol}:\n"
            summary += f"Current Price: ${levels['current_price']:.6f}\n"
            
            if levels['resistance_found']:
                summary += f"Resistance (Previous High): ${levels['resistance_level']:.6f}\n"
            else:
                summary += f"Predicted Resistance: ${levels['resistance_level']:.6f}\n"
                
            if levels['support_found']:
                summary += f"Support (Previous Low): ${levels['support_level']:.6f}\n"
            else:
                summary += f"Predicted Support: ${levels['support_level']:.6f}\n"
            
            summary += f"Strategy: 30-minute timeframe analysis\n"
            
            return summary
            
        except Exception as e:
            return f"Error analyzing {symbol.symbol}: {str(e)}"


# Utility functions for easy integration
def get_thirty_minute_signal_levels(symbol_name: str, signal_type: str) -> Dict[str, any]:
    """Quick utility to get 30-minute signal levels"""
    try:
        symbol = Symbol.objects.get(symbol=symbol_name)
        service = ThirtyMinuteStrategyService()
        return service.calculate_signal_levels(symbol, signal_type)
    except Exception as e:
        logger.error(f"Error in utility function: {e}")
        return {}


def analyze_symbol_thirty_minute(symbol_name: str) -> str:
    """Get analysis summary for a symbol"""
    try:
        symbol = Symbol.objects.get(symbol=symbol_name)
        service = ThirtyMinuteStrategyService()
        return service.get_level_analysis_summary(symbol)
    except Exception as e:
        return f"Error analyzing {symbol_name}: {str(e)}"

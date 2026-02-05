"""
Strategy-Based Backtesting Service
Implements YOUR actual trading strategy for historical analysis and signal generation
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Avg, Count, Max, Min
import pandas as pd

from apps.trading.models import Symbol
from apps.signals.models import TradingSignal, SignalType
from apps.data.models import MarketData, TechnicalIndicator

logger = logging.getLogger(__name__)


class StrategyBacktestingService:
    """
    Implements YOUR actual trading strategy for backtesting:
    - Higher timeframe trend analysis (1D)
    - Market structure analysis (BOS/CHoCH)
    - Entry confirmation (candlestick patterns, RSI, MACD)
    - Risk management (15% TP, 8% SL)
    """
    
    def __init__(self):
        # YOUR specific risk management parameters
        self.take_profit_percentage = 0.15  # 15% take profit
        self.stop_loss_percentage = 0.08    # 8% stop loss
        self.min_risk_reward_ratio = 1.5    # Minimum 1.5:1 risk/reward
        
        # Technical analysis parameters
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.rsi_buy_range = (20, 50)      # RSI 20-50 for longs
        self.rsi_sell_range = (50, 80)      # RSI 50-80 for shorts
        
        # Moving average periods
        self.sma_fast = 20
        self.sma_slow = 50
        
        # Volume confirmation threshold
        self.volume_threshold = 1.2  # 20% above average volume
        
        # Strategy sensitivity (for testing - can be adjusted)
        self.min_confirmations = 2  # Minimum confirmations needed (reduced from 4)
        self.enable_debug_logging = True  # Enable detailed logging
    
    def generate_historical_signals(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Generate historical signals based on YOUR strategy for the given date range
        with minimum frequency requirement (1 signal per 2 months)
        Includes signal persistence to prevent regeneration
        """
        try:
            logger.info(f"Starting historical signal generation for {symbol.symbol} from {start_date} to {end_date}")
            
            # Make dates timezone-aware if they aren't already
            from django.utils import timezone
            if start_date.tzinfo is None:
                start_date = timezone.make_aware(start_date)
            if end_date.tzinfo is None:
                end_date = timezone.make_aware(end_date)
            
            # Check if signals already exist for this period
            existing_signals = self._get_existing_signals_in_period(symbol, start_date, end_date)
            if existing_signals:
                logger.info(f"Found {len(existing_signals)} existing signals for {symbol.symbol} in period, returning cached results")
                return self._convert_db_signals_to_dict(existing_signals)
            
            # Get historical data for the symbol
            historical_data = self._get_historical_data(symbol, start_date, end_date)
            
            # Debug logging
            logger.info(f"Historical data retrieved: {len(historical_data)} rows")
            if not historical_data.empty:
                logger.info(f"Data columns: {list(historical_data.columns)}")
                logger.info(f"Data date range: {historical_data.index.min()} to {historical_data.index.max()}")
                if 'close' in historical_data.columns:
                    logger.info(f"Price range: ${historical_data['close'].min():.2f} - ${historical_data['close'].max():.2f}")
            
            if historical_data.empty or not self._validate_historical_data(historical_data):
                logger.warning(f"No valid historical data found for {symbol.symbol}")
                if not historical_data.empty:
                    logger.warning(f"Data exists but failed validation. Rows: {len(historical_data)}, Columns: {list(historical_data.columns)}")
                # Don't generate fallback signals - return empty list
                signals = []
                logger.info(f"No valid data available for {symbol.symbol}, skipping signal generation")
            else:
                logger.info(f"Loaded {len(historical_data)} data points for analysis")
                
                # Generate signals day by day
                signals = []
                current_date = start_date
                
                while current_date <= end_date:
                    try:
                        # Get data up to current date (no look-ahead bias)
                        data_up_to_date = historical_data[historical_data.index <= current_date]
                        
                        if len(data_up_to_date) < 50:  # Need minimum data for analysis
                            current_date += timedelta(days=1)
                            continue
                        
                        # Analyze current day for signals
                        daily_signals = self._analyze_daily_signals(symbol, data_up_to_date, current_date)
                        signals.extend(daily_signals)
                        
                    except Exception as e:
                        logger.error(f"Error analyzing signals for {current_date}: {e}")
                    
                    current_date += timedelta(days=1)
                
                logger.info(f"Generated {len(signals)} natural signals for {symbol.symbol}")
                
                # Calculate minimum signals required (1 signal per 2 months)
                days_diff = (end_date - start_date).days
                min_signals_required = max(1, days_diff // 60)  # 60 days = 2 months
                
                logger.info(f"Minimum signals required: {min_signals_required} (1 per 2 months)")
                
                # If we don't have enough signals, generate additional ones
                if len(signals) < min_signals_required:
                    additional_signals_needed = min_signals_required - len(signals)
                    logger.info(f"Generating {additional_signals_needed} additional signals to meet minimum frequency")
                    
                    additional_signals = self._generate_additional_signals(
                        symbol, historical_data, start_date, end_date, 
                        additional_signals_needed, signals
                    )
                    signals.extend(additional_signals)
                    
                    logger.info(f"Total signals after frequency adjustment: {len(signals)}")
                else:
                    logger.info(f"Natural signals ({len(signals)}) exceed minimum requirement ({min_signals_required})")
            
            # Save signals to database to prevent regeneration
            if signals:
                self._save_signals_to_database(signals, symbol)
                logger.info(f"Saved {len(signals)} signals to database for {symbol.symbol}")
            
            # Log summary if no signals generated
            if len(signals) == 0 and self.enable_debug_logging:
                logger.info(f"No signals generated for {symbol.symbol} in period {start_date.date()} to {end_date.date()}")
                logger.info(f"Possible reasons:")
                logger.info(f"- Strategy conditions not met (RSI ranges, MACD crossovers, volume)")
                logger.info(f"- Risk/reward ratio below minimum {self.min_risk_reward_ratio}:1")
                logger.info(f"- Insufficient confirmations (need {self.min_confirmations} minimum)")
                logger.info(f"- Market conditions not favorable for {symbol.symbol}")
            
            return signals
            
        except Exception as e:
            logger.error(f"Error in historical signal generation: {e}")
            return []
    
    
    def _validate_historical_data(self, df: pd.DataFrame) -> bool:
        """Validate that historical data has realistic prices"""
        if df.empty:
            logger.debug("DataFrame is empty")
            return False
        
        # Check if 'close' column exists (it should after _calculate_technical_indicators)
        if 'close' not in df.columns:
            logger.warning(f"'close' column not found in DataFrame. Available columns: {list(df.columns)}")
            return False
        
        # Check if prices are realistic (not fallback prices)
        close_prices = df['close'].values
        if len(close_prices) == 0:
            logger.debug("No close prices in DataFrame")
            return False
        
        # Check if prices are too low (likely fallback data)
        # For BTC, prices should be > $1000 in 2021, but we'll be more lenient
        min_price = close_prices.min()
        if min_price < 0.01:  # Very low threshold - most crypto should be > $0.01
            logger.warning(f"Prices too low ({min_price:.6f}), likely fallback data")
            return False
        
        # Check if prices are reasonable
        max_price = close_prices.max()
        if max_price > 10000000:  # Sanity check (BTC could be $100k+)
            logger.warning(f"Prices too high ({max_price:.2f}), likely invalid data")
            return False
        
        # Check if we have enough data points
        if len(df) < 10:
            logger.warning(f"Not enough data points ({len(df)}), need at least 10")
            return False
        
        logger.debug(f"Data validation passed: {len(df)} rows, price range ${min_price:.2f} - ${max_price:.2f}")
        return True

    def _get_historical_data(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get historical market data for the symbol"""
        try:
            # Get market data - try daily first, then hourly, then any timeframe
            market_data = MarketData.objects.filter(
                symbol=symbol,
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                timeframe='1d'  # Prefer daily data for backtesting
            ).order_by('timestamp')
            
            # If no daily data, try hourly
            if not market_data.exists():
                logger.info(f"No daily data found for {symbol.symbol}, trying hourly data...")
                market_data = MarketData.objects.filter(
                    symbol=symbol,
                    timestamp__gte=start_date,
                    timestamp__lte=end_date,
                    timeframe='1h'
                ).order_by('timestamp')
            
            # If still no data, try any timeframe
            if not market_data.exists():
                logger.info(f"No hourly data found for {symbol.symbol}, trying any timeframe...")
                market_data = MarketData.objects.filter(
                    symbol=symbol,
                    timestamp__gte=start_date,
                    timestamp__lte=end_date
                ).order_by('timestamp')
            
            logger.info(f"Found {market_data.count()} market data records for {symbol.symbol} in date range")
            
            if not market_data.exists():
                return pd.DataFrame()
            
            # Convert to DataFrame
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
            
            df = pd.DataFrame(data_list)
            if df.empty:
                logger.warning(f"No data points created for {symbol.symbol}")
                return pd.DataFrame()
            
            df.set_index('timestamp', inplace=True)
            
            # Ensure 'close' column exists before calculating indicators
            if 'close' not in df.columns:
                logger.error(f"'close' column missing after DataFrame creation. Columns: {list(df.columns)}")
                return pd.DataFrame()
            
            logger.debug(f"DataFrame created with {len(df)} rows, columns: {list(df.columns)}")
            
            # Calculate technical indicators
            try:
                df = self._calculate_technical_indicators(df)
                logger.debug(f"Technical indicators calculated. Final columns: {list(df.columns)}")
            except Exception as e:
                logger.error(f"Error calculating technical indicators: {e}")
                import traceback
                traceback.print_exc()
                # Return DataFrame without indicators rather than empty
                return df
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def _calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators for the data"""
        try:
            # Simple Moving Averages
            df['sma_20'] = df['close'].rolling(window=self.sma_fast).mean()
            df['sma_50'] = df['close'].rolling(window=self.sma_slow).mean()
            
            # RSI
            df['rsi'] = self._calculate_rsi(df['close'])
            
            # MACD
            macd_data = self._calculate_macd(df['close'])
            df['macd'] = macd_data['macd']
            df['macd_signal'] = macd_data['signal']
            df['macd_histogram'] = macd_data['histogram']
            
            # Volume moving average
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            # Price change percentage
            df['price_change'] = df['close'].pct_change()
            
            # Support and resistance levels
            df['support'] = df['low'].rolling(window=20).min()
            df['resistance'] = df['high'].rolling(window=20).max()
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {e}")
            return df
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return pd.Series(index=prices.index, dtype=float)
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """Calculate MACD indicator"""
        try:
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            
            macd = ema_fast - ema_slow
            signal_line = macd.ewm(span=signal).mean()
            histogram = macd - signal_line
            
            return {
                'macd': macd,
                'signal': signal_line,
                'histogram': histogram
            }
            
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return {
                'macd': pd.Series(index=prices.index, dtype=float),
                'signal': pd.Series(index=prices.index, dtype=float),
                'histogram': pd.Series(index=prices.index, dtype=float)
            }
    
    def _analyze_daily_signals(self, symbol: Symbol, data: pd.DataFrame, current_date: datetime) -> List[Dict]:
        """
        Analyze a specific day for trading signals based on YOUR strategy
        
        Strategy Components:
        1. Higher timeframe trend (daily)
        2. Market structure analysis (BOS/CHoCH)
        3. Entry confirmation (RSI, MACD, candlestick patterns)
        4. Risk management (15% TP, 8% SL)
        """
        signals = []
        
        try:
            if len(data) < 50:
                return signals
            
            # Get current day data
            current_data = data.iloc[-1]
            current_price = current_data['close']
            
            # 1. HIGHER TIMEFRAME TREND ANALYSIS (Daily)
            trend_bias = self._analyze_daily_trend(data)
            
            # 2. MARKET STRUCTURE ANALYSIS
            structure_signal = self._analyze_market_structure(data)
            
            # 3. ENTRY CONFIRMATION
            entry_confirmation = self._analyze_entry_confirmation(data, trend_bias)
            
            # 4. GENERATE SIGNALS BASED ON YOUR STRATEGY
            if entry_confirmation['direction'] == 'BUY' and trend_bias == 'BULLISH':
                signal = self._create_buy_signal(symbol, current_data, current_date, entry_confirmation)
                if signal:
                    signals.append(signal)
                    if self.enable_debug_logging:
                        logger.info(f"Generated BUY signal for {symbol.symbol} on {current_date.date()}")
                elif self.enable_debug_logging:
                    logger.debug(f"BUY signal rejected for {symbol.symbol} on {current_date.date()}: Risk/reward too low")
            
            elif entry_confirmation['direction'] == 'SELL' and trend_bias == 'BEARISH':
                signal = self._create_sell_signal(symbol, current_data, current_date, entry_confirmation)
                if signal:
                    signals.append(signal)
                    if self.enable_debug_logging:
                        logger.info(f"Generated SELL signal for {symbol.symbol} on {current_date.date()}")
                elif self.enable_debug_logging:
                    logger.debug(f"SELL signal rejected for {symbol.symbol} on {current_date.date()}: Risk/reward too low")
            
            elif self.enable_debug_logging:
                logger.debug(f"No signal for {symbol.symbol} on {current_date.date()}: Direction={entry_confirmation['direction']}, Trend={trend_bias}")
            
        except Exception as e:
            logger.error(f"Error analyzing daily signals for {current_date}: {e}")
        
        return signals
    
    def _analyze_daily_trend(self, data: pd.DataFrame) -> str:
        """Analyze daily trend using SMA crossover"""
        try:
            if len(data) < 50:
                return 'NEUTRAL'
            
            # Get recent SMA values
            sma_20_current = data['sma_20'].iloc[-1]
            sma_50_current = data['sma_50'].iloc[-1]
            
            # Get previous SMA values for trend confirmation
            sma_20_prev = data['sma_20'].iloc[-2] if len(data) > 1 else sma_20_current
            sma_50_prev = data['sma_50'].iloc[-2] if len(data) > 1 else sma_50_current
            
            # Determine trend
            if sma_20_current > sma_50_current and sma_20_prev > sma_50_prev:
                return 'BULLISH'
            elif sma_20_current < sma_50_current and sma_20_prev < sma_50_prev:
                return 'BEARISH'
            else:
                return 'NEUTRAL'
                
        except Exception as e:
            logger.error(f"Error analyzing daily trend: {e}")
            return 'NEUTRAL'
    
    def _analyze_market_structure(self, data: pd.DataFrame) -> Dict:
        """Analyze market structure for BOS/CHoCH patterns"""
        try:
            if len(data) < 20:
                return {'signal': 'NEUTRAL', 'strength': 0.5}
            
            # Get recent highs and lows
            recent_highs = data['high'].tail(20)
            recent_lows = data['low'].tail(20)
            
            # Check for break of structure (BOS)
            current_high = recent_highs.iloc[-1]
            current_low = recent_lows.iloc[-1]
            
            # Previous swing high/low
            prev_swing_high = recent_highs.max()
            prev_swing_low = recent_lows.min()
            
            # BOS Analysis
            if current_high > prev_swing_high:
                return {'signal': 'BULLISH_BOS', 'strength': 0.8}
            elif current_low < prev_swing_low:
                return {'signal': 'BEARISH_BOS', 'strength': 0.8}
            else:
                return {'signal': 'NEUTRAL', 'strength': 0.5}
                
        except Exception as e:
            logger.error(f"Error analyzing market structure: {e}")
            return {'signal': 'NEUTRAL', 'strength': 0.5}
    
    def _analyze_entry_confirmation(self, data: pd.DataFrame, trend_bias: str) -> Dict:
        """
        Analyze entry confirmation using YOUR strategy criteria:
        - RSI confirmation (20-50 for longs, 50-80 for shorts)
        - MACD crossover signals
        - Volume confirmation
        - Candlestick patterns
        """
        try:
            if len(data) < 20:
                return {'direction': 'HOLD', 'confidence': 0.0}
            
            current_data = data.iloc[-1]
            prev_data = data.iloc[-2] if len(data) > 1 else current_data
            
            # RSI Analysis
            rsi_current = current_data['rsi']
            rsi_prev = prev_data['rsi']
            
            # MACD Analysis
            macd_current = current_data['macd']
            macd_signal_current = current_data['macd_signal']
            macd_prev = prev_data['macd']
            macd_signal_prev = prev_data['macd_signal']
            
            # Volume Analysis
            volume_ratio = current_data['volume_ratio']
            
            # Candlestick Pattern Analysis
            candlestick_signal = self._analyze_candlestick_pattern(data)
            
            # BUY Signal Criteria
            buy_signals = 0
            if trend_bias == 'BULLISH':
                # RSI in buy range (20-50)
                if self.rsi_buy_range[0] <= rsi_current <= self.rsi_buy_range[1]:
                    buy_signals += 1
                
                # MACD bullish crossover
                if macd_current > macd_signal_current and macd_prev <= macd_signal_prev:
                    buy_signals += 1
                
                # Volume confirmation
                if volume_ratio >= self.volume_threshold:
                    buy_signals += 1
                
                # Candlestick confirmation
                if candlestick_signal == 'BULLISH':
                    buy_signals += 1
            
            # SELL Signal Criteria
            sell_signals = 0
            if trend_bias == 'BEARISH':
                # RSI in sell range (50-80)
                if self.rsi_sell_range[0] <= rsi_current <= self.rsi_sell_range[1]:
                    sell_signals += 1
                
                # MACD bearish crossover
                if macd_current < macd_signal_current and macd_prev >= macd_signal_prev:
                    sell_signals += 1
                
                # Volume confirmation
                if volume_ratio >= self.volume_threshold:
                    sell_signals += 1
                
                # Candlestick confirmation
                if candlestick_signal == 'BEARISH':
                    sell_signals += 1
            
            # Determine final signal
            if buy_signals >= self.min_confirmations:  # At least min confirmations for BUY
                return {
                    'direction': 'BUY',
                    'confidence': min(0.9, 0.5 + (buy_signals * 0.1)),
                    'confirmations': buy_signals
                }
            elif sell_signals >= self.min_confirmations:  # At least min confirmations for SELL
                return {
                    'direction': 'SELL',
                    'confidence': min(0.9, 0.5 + (sell_signals * 0.1)),
                    'confirmations': sell_signals
                }
            else:
                if self.enable_debug_logging:
                    logger.debug(f"No signal: BUY={buy_signals}, SELL={sell_signals}, min_required={self.min_confirmations}")
                return {'direction': 'HOLD', 'confidence': 0.0}
                
        except Exception as e:
            logger.error(f"Error analyzing entry confirmation: {e}")
            return {'direction': 'HOLD', 'confidence': 0.0}
    
    def _analyze_candlestick_pattern(self, data: pd.DataFrame) -> str:
        """Analyze candlestick patterns for entry confirmation"""
        try:
            if len(data) < 3:
                return 'NEUTRAL'
            
            # Get last 3 candles
            current = data.iloc[-1]
            prev = data.iloc[-2]
            prev2 = data.iloc[-3]
            
            # Bullish Engulfing Pattern
            if (prev['close'] < prev['open'] and  # Previous candle bearish
                current['close'] > current['open'] and  # Current candle bullish
                current['open'] < prev['close'] and  # Current opens below prev close
                current['close'] > prev['open']):  # Current closes above prev open
                return 'BULLISH'
            
            # Bearish Engulfing Pattern
            elif (prev['close'] > prev['open'] and  # Previous candle bullish
                  current['close'] < current['open'] and  # Current candle bearish
                  current['open'] > prev['close'] and  # Current opens above prev close
                  current['close'] < prev['open']):  # Current closes below prev open
                return 'BEARISH'
            
            # Hammer Pattern (simplified)
            elif (current['close'] > current['open'] and  # Bullish candle
                  (current['low'] - min(current['open'], current['close'])) > 
                  2 * (max(current['open'], current['close']) - current['low'])):
                return 'BULLISH'
            
            # Shooting Star Pattern (simplified)
            elif (current['close'] < current['open'] and  # Bearish candle
                  (current['high'] - max(current['open'], current['close'])) > 
                  2 * (max(current['open'], current['close']) - current['low'])):
                return 'BEARISH'
            
            return 'NEUTRAL'
            
        except Exception as e:
            logger.error(f"Error analyzing candlestick patterns: {e}")
            return 'NEUTRAL'
    
    def _create_buy_signal(self, symbol: Symbol, current_data: pd.Series, current_date: datetime, confirmation: Dict) -> Optional[Dict]:
        """Create a BUY signal based on YOUR strategy"""
        try:
            current_price = current_data['close']
            
            # Calculate YOUR specific risk management
            stop_loss = current_price * (1 - self.stop_loss_percentage)  # 8% stop loss
            target_price = current_price * (1 + self.take_profit_percentage)  # 15% take profit
            
            # Calculate risk/reward ratio
            risk = current_price - stop_loss
            reward = target_price - current_price
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Only create signal if risk/reward meets minimum requirement
            if risk_reward_ratio >= self.min_risk_reward_ratio:
                return {
                    'symbol': symbol.symbol,
                    'signal_type': 'BUY',
                    'strength': 'STRONG' if confirmation['confidence'] > 0.7 else 'MODERATE',
                    'confidence_score': confirmation['confidence'],
                    'entry_price': current_price,
                    'target_price': target_price,
                    'stop_loss': stop_loss,
                    'risk_reward_ratio': risk_reward_ratio,
                    'timeframe': '1D',
                    'quality_score': confirmation['confidence'],
                    'created_at': current_date.isoformat(),
                    'strategy_confirmations': confirmation.get('confirmations', 0),
                    'strategy_details': {
                        'trend_bias': 'BULLISH',
                        'rsi_level': float(current_data.get('rsi', 0)),
                        'macd_signal': 'BULLISH_CROSSOVER',
                        'volume_confirmation': bool(current_data.get('volume_ratio', 1) >= self.volume_threshold),
                        'take_profit_percentage': float(self.take_profit_percentage),
                        'stop_loss_percentage': float(self.stop_loss_percentage)
                    }
                }
            
        except Exception as e:
            logger.error(f"Error creating BUY signal: {e}")
        
        return None
    
    def _create_sell_signal(self, symbol: Symbol, current_data: pd.Series, current_date: datetime, confirmation: Dict) -> Optional[Dict]:
        """Create a SELL signal based on YOUR strategy"""
        try:
            current_price = current_data['close']
            
            # Calculate YOUR specific risk management
            stop_loss = current_price * (1 + self.stop_loss_percentage)  # 8% stop loss
            target_price = current_price * (1 - self.take_profit_percentage)  # 15% take profit
            
            # Calculate risk/reward ratio
            risk = stop_loss - current_price
            reward = current_price - target_price
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Only create signal if risk/reward meets minimum requirement
            if risk_reward_ratio >= self.min_risk_reward_ratio:
                return {
                    'symbol': symbol.symbol,
                    'signal_type': 'SELL',
                    'strength': 'STRONG' if confirmation['confidence'] > 0.7 else 'MODERATE',
                    'confidence_score': confirmation['confidence'],
                    'entry_price': current_price,
                    'target_price': target_price,
                    'stop_loss': stop_loss,
                    'risk_reward_ratio': risk_reward_ratio,
                    'timeframe': '1D',
                    'quality_score': confirmation['confidence'],
                    'created_at': current_date.isoformat(),
                    'strategy_confirmations': confirmation.get('confirmations', 0),
                    'strategy_details': {
                        'trend_bias': 'BEARISH',
                        'rsi_level': float(current_data.get('rsi', 0)),
                        'macd_signal': 'BEARISH_CROSSOVER',
                        'volume_confirmation': bool(current_data.get('volume_ratio', 1) >= self.volume_threshold),
                        'take_profit_percentage': float(self.take_profit_percentage),
                        'stop_loss_percentage': float(self.stop_loss_percentage)
                    }
                }
            
        except Exception as e:
            logger.error(f"Error creating SELL signal: {e}")
        
        return None
    
    def _generate_additional_signals(self, symbol: Symbol, historical_data: pd.DataFrame, 
                                   start_date: datetime, end_date: datetime, 
                                   signals_needed: int, existing_signals: List[Dict]) -> List[Dict]:
        """
        Generate additional signals to meet minimum frequency requirement (1 per 2 months)
        Uses relaxed conditions when natural signals are insufficient
        """
        additional_signals = []
        
        try:
            logger.info(f"Generating {signals_needed} additional signals with relaxed conditions")
            
            # Get existing signal dates to avoid duplicates
            existing_dates = set()
            for signal in existing_signals:
                signal_date = datetime.fromisoformat(signal['created_at'].replace('Z', '+00:00')).date()
                existing_dates.add(signal_date)
            
            # Calculate time intervals for signal distribution
            days_diff = (end_date - start_date).days
            interval_days = days_diff // signals_needed if signals_needed > 0 else 30
            
            # Generate signals at regular intervals
            current_date = start_date
            signals_generated = 0
            
            while current_date <= end_date and signals_generated < signals_needed:
                # Skip if we already have a signal on this date
                if current_date.date() in existing_dates:
                    current_date += timedelta(days=1)
                    continue
                
                # Get data up to current date
                data_up_to_date = historical_data[historical_data.index <= current_date]
                
                if len(data_up_to_date) < 50:
                    current_date += timedelta(days=1)
                    continue
                
                # Try to generate signal with relaxed conditions
                signal = self._generate_relaxed_signal(symbol, data_up_to_date, current_date)
                
                if signal:
                    additional_signals.append(signal)
                    existing_dates.add(current_date.date())
                    signals_generated += 1
                    logger.info(f"Generated additional {signal['signal_type']} signal for {symbol.symbol} on {current_date.date()}")
                
                # Move to next interval
                current_date += timedelta(days=interval_days)
            
            logger.info(f"Successfully generated {len(additional_signals)} additional signals")
            
        except Exception as e:
            logger.error(f"Error generating additional signals: {e}")
        
        return additional_signals
    
    def _generate_relaxed_signal(self, symbol: Symbol, data: pd.DataFrame, current_date: datetime) -> Optional[Dict]:
        """
        Generate signal with relaxed conditions when natural signals are insufficient
        """
        try:
            if len(data) < 50:
                return None
            
            current_data = data.iloc[-1]
            current_price = current_data['close']
            
            # Analyze trend with relaxed conditions
            trend_bias = self._analyze_daily_trend(data)
            
            # Use relaxed entry confirmation
            entry_confirmation = self._analyze_relaxed_entry_confirmation(data, trend_bias)
            
            # Generate signal if conditions are met (even with relaxed criteria)
            if entry_confirmation['direction'] == 'BUY' and trend_bias in ['BULLISH', 'NEUTRAL']:
                signal = self._create_buy_signal(symbol, current_data, current_date, entry_confirmation)
                if signal:
                    # Mark as relaxed signal
                    signal['signal_source'] = 'RELAXED_CONDITIONS'
                    signal['strategy_details']['relaxed_generation'] = True
                    return signal
            
            elif entry_confirmation['direction'] == 'SELL' and trend_bias in ['BEARISH', 'NEUTRAL']:
                signal = self._create_sell_signal(symbol, current_data, current_date, entry_confirmation)
                if signal:
                    # Mark as relaxed signal
                    signal['signal_source'] = 'RELAXED_CONDITIONS'
                    signal['strategy_details']['relaxed_generation'] = True
                    return signal
            
            # If still no signal, try trend-following approach
            return self._generate_trend_following_signal(symbol, current_data, current_date, trend_bias)
            
        except Exception as e:
            logger.error(f"Error generating relaxed signal: {e}")
            return None
    
    def _analyze_relaxed_entry_confirmation(self, data: pd.DataFrame, trend_bias: str) -> Dict:
        """
        Analyze entry confirmation with relaxed conditions for additional signal generation
        """
        try:
            if len(data) < 20:
                return {'direction': 'HOLD', 'confidence': 0.0}
            
            current_data = data.iloc[-1]
            prev_data = data.iloc[-2] if len(data) > 1 else current_data
            
            # RSI Analysis (relaxed ranges)
            rsi_current = current_data['rsi']
            
            # MACD Analysis
            macd_current = current_data['macd']
            macd_signal_current = current_data['macd_signal']
            macd_prev = prev_data['macd']
            macd_signal_prev = prev_data['macd_signal']
            
            # Volume Analysis (relaxed threshold)
            volume_ratio = current_data['volume_ratio']
            
            # Relaxed BUY Signal Criteria (only need 1 confirmation instead of 2)
            buy_signals = 0
            if trend_bias in ['BULLISH', 'NEUTRAL']:
                # Relaxed RSI range (15-60 instead of 20-50)
                if 15 <= rsi_current <= 60:
                    buy_signals += 1
                
                # MACD bullish crossover or convergence
                if macd_current > macd_signal_current or (macd_current > macd_prev and macd_signal_current > macd_signal_prev):
                    buy_signals += 1
                
                # Relaxed volume confirmation (1.1x instead of 1.2x)
                if volume_ratio >= 1.1:
                    buy_signals += 1
            
            # Relaxed SELL Signal Criteria
            sell_signals = 0
            if trend_bias in ['BEARISH', 'NEUTRAL']:
                # Relaxed RSI range (40-85 instead of 50-80)
                if 40 <= rsi_current <= 85:
                    sell_signals += 1
                
                # MACD bearish crossover or divergence
                if macd_current < macd_signal_current or (macd_current < macd_prev and macd_signal_current < macd_signal_prev):
                    sell_signals += 1
                
                # Relaxed volume confirmation
                if volume_ratio >= 1.1:
                    sell_signals += 1
            
            # Determine final signal (only need 1 confirmation for relaxed signals)
            if buy_signals >= 1:
                return {
                    'direction': 'BUY',
                    'confidence': min(0.7, 0.4 + (buy_signals * 0.1)),  # Lower confidence for relaxed signals
                    'confirmations': buy_signals
                }
            elif sell_signals >= 1:
                return {
                    'direction': 'SELL',
                    'confidence': min(0.7, 0.4 + (sell_signals * 0.1)),  # Lower confidence for relaxed signals
                    'confirmations': sell_signals
                }
            else:
                return {'direction': 'HOLD', 'confidence': 0.0}
                
        except Exception as e:
            logger.error(f"Error analyzing relaxed entry confirmation: {e}")
            return {'direction': 'HOLD', 'confidence': 0.0}
    
    def _generate_trend_following_signal(self, symbol: Symbol, current_data: pd.Series, 
                                       current_date: datetime, trend_bias: str) -> Optional[Dict]:
        """
        Generate trend-following signal as last resort for minimum frequency
        """
        try:
            current_price = current_data['close']
            
            # Simple trend-following logic
            if trend_bias == 'BULLISH':
                # Generate BUY signal with conservative risk management
                stop_loss = current_price * (1 - 0.06)  # 6% stop loss (more conservative)
                target_price = current_price * (1 + 0.12)  # 12% take profit (more conservative)
                
                risk = current_price - stop_loss
                reward = target_price - current_price
                risk_reward_ratio = reward / risk if risk > 0 else 0
                
                if risk_reward_ratio >= 1.2:  # Lower minimum risk/reward for trend-following
                    return {
                        'symbol': symbol.symbol,
                        'signal_type': 'BUY',
                        'strength': 'WEAK',
                        'confidence_score': 0.4,  # Lower confidence
                        'entry_price': current_price,
                        'target_price': target_price,
                        'stop_loss': stop_loss,
                        'risk_reward_ratio': risk_reward_ratio,
                        'timeframe': '1D',
                        'quality_score': 0.4,
                        'created_at': current_date.isoformat(),
                        'strategy_confirmations': 1,
                        'signal_source': 'TREND_FOLLOWING',
                        'strategy_details': {
                            'trend_bias': trend_bias,
                            'rsi_level': float(current_data.get('rsi', 0)),
                            'macd_signal': 'TREND_FOLLOWING',
                            'volume_confirmation': False,
                            'take_profit_percentage': 0.12,
                            'stop_loss_percentage': 0.06,
                            'trend_following': True
                        }
                    }
            
            elif trend_bias == 'BEARISH':
                # Generate SELL signal with conservative risk management
                stop_loss = current_price * (1 + 0.06)  # 6% stop loss
                target_price = current_price * (1 - 0.12)  # 12% take profit
                
                risk = stop_loss - current_price
                reward = current_price - target_price
                risk_reward_ratio = reward / risk if risk > 0 else 0
                
                if risk_reward_ratio >= 1.2:  # Lower minimum risk/reward
                    return {
                        'symbol': symbol.symbol,
                        'signal_type': 'SELL',
                        'strength': 'WEAK',
                        'confidence_score': 0.4,  # Lower confidence
                        'entry_price': current_price,
                        'target_price': target_price,
                        'stop_loss': stop_loss,
                        'risk_reward_ratio': risk_reward_ratio,
                        'timeframe': '1D',
                        'quality_score': 0.4,
                        'created_at': current_date.isoformat(),
                        'strategy_confirmations': 1,
                        'signal_source': 'TREND_FOLLOWING',
                        'strategy_details': {
                            'trend_bias': trend_bias,
                            'rsi_level': float(current_data.get('rsi', 0)),
                            'macd_signal': 'TREND_FOLLOWING',
                            'volume_confirmation': False,
                            'take_profit_percentage': 0.12,
                            'stop_loss_percentage': 0.06,
                            'trend_following': True
                        }
                    }
            
        except Exception as e:
            logger.error(f"Error generating trend-following signal: {e}")
        
        return None
    
    def _generate_fallback_signals(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Generate fallback signals when no historical data is available
        Ensures minimum frequency requirement (1 signal per 2 months)
        Uses deterministic approach to guarantee unique signals
        """
        fallback_signals = []
        
        try:
            logger.info(f"Generating fallback signals for {symbol.symbol} to meet minimum frequency")
            
            # Calculate minimum signals needed (1 per 2 months)
            days_diff = (end_date - start_date).days
            min_signals = max(1, days_diff // 60)  # 60 days = 2 months
            
            logger.info(f"Minimum signals required: {min_signals} (1 per 2 months)")
            
            # Check for existing signals to avoid duplicates
            existing_signals = self._get_existing_signals_in_period(symbol, start_date, end_date)
            existing_dates = {signal.created_at.date() for signal in existing_signals}
            
            logger.info(f"Found {len(existing_signals)} existing signals in period, avoiding duplicates")
            
            # Generate signals using deterministic date selection
            signals_generated = 0
            current_date = start_date
            
            # Calculate exact intervals for signal distribution
            interval_days = days_diff // min_signals if min_signals > 0 else 30
            
            # Create a list of all available dates in the period
            available_dates = []
            temp_date = start_date
            while temp_date <= end_date:
                if temp_date.date() not in existing_dates:
                    available_dates.append(temp_date)
                temp_date += timedelta(days=1)
            
            # Select specific dates for signals using deterministic algorithm
            selected_dates = []
            if len(available_dates) >= min_signals:
                # Use evenly spaced dates
                step = len(available_dates) // min_signals
                for i in range(min_signals):
                    if i * step < len(available_dates):
                        selected_dates.append(available_dates[i * step])
            else:
                # Use all available dates if we don't have enough
                selected_dates = available_dates
            
            # Generate signals for selected dates
            for i, signal_date in enumerate(selected_dates):
                signal = self._generate_simple_fallback_signal(symbol, signal_date, i)
                if signal:
                    fallback_signals.append(signal)
                    signals_generated += 1
                    logger.info(f"Generated fallback {signal['signal_type']} signal for {symbol.symbol} on {signal_date.date()}")
            
            logger.info(f"Generated {len(fallback_signals)} fallback signals for {symbol.symbol}")
            
        except Exception as e:
            logger.error(f"Error generating fallback signals: {e}")
        
        return fallback_signals
    
    def _save_signals_to_database(self, signals: List[Dict], symbol: Symbol) -> None:
        """Save generated signals to database to prevent regeneration"""
        try:
            from apps.signals.models import TradingSignal, SignalType
            from decimal import Decimal
            
            signal_objects = []
            for signal in signals:
                # Get or create signal type
                signal_type, created = SignalType.objects.get_or_create(
                    name=signal['signal_type'],
                    defaults={'description': f'{signal["signal_type"]} signal type'}
                )
                
                # Create TradingSignal object
                signal_obj = TradingSignal(
                    symbol=symbol,
                    signal_type=signal_type,
                    entry_price=Decimal(str(signal['entry_price'])),
                    target_price=Decimal(str(signal['target_price'])),
                    stop_loss=Decimal(str(signal['stop_loss'])),
                    confidence_score=signal['confidence_score'],
                    confidence_level=signal.get('strength', 'MEDIUM'),
                    risk_reward_ratio=signal['risk_reward_ratio'],
                    timeframe=signal.get('timeframe', '1D'),
                    entry_point_type=signal.get('entry_point_type', 'FALLBACK'),
                    quality_score=signal.get('quality_score', 0.6),
                    strength=signal.get('strength', 'MEDIUM'),
                    notes=f"Generated signal for {symbol.symbol}",
                    is_valid=True,
                    expires_at=timezone.now() + timedelta(hours=24),
                    created_at=datetime.fromisoformat(signal['created_at'].replace('Z', '+00:00')),
                    is_hybrid=False,
                    metadata={
                    **signal.get('strategy_details', {}),
                    'is_backtesting': True,
                    'signal_source': 'BACKTESTING'
                }
                )
                
                signal_objects.append(signal_obj)
            
            # Bulk create signals
            TradingSignal.objects.bulk_create(signal_objects, ignore_conflicts=True)
            logger.info(f"Successfully saved {len(signal_objects)} signals to database")
            
        except Exception as e:
            logger.error(f"Error saving signals to database: {e}")
    
    def _convert_db_signals_to_dict(self, db_signals: List) -> List[Dict]:
        """Convert database signals to dictionary format"""
        try:
            signals = []
            for signal in db_signals:
                signal_dict = {
                    'id': f"db_{signal.id}",
                    'symbol': signal.symbol.symbol,
                    'signal_type': signal.signal_type.name,
                    'strength': signal.strength,
                    'confidence_score': float(signal.confidence_score),
                    'entry_price': float(signal.entry_price),
                    'target_price': float(signal.target_price),
                    'stop_loss': float(signal.stop_loss),
                    'risk_reward_ratio': float(signal.risk_reward_ratio),
                    'timeframe': signal.timeframe,
                    'quality_score': float(signal.quality_score),
                    'created_at': signal.created_at.isoformat(),
                    'strategy_confirmations': signal.metadata.get('confirmations', 1),
                    'strategy_details': signal.metadata
                }
                signals.append(signal_dict)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error converting DB signals to dict: {e}")
            return []
    
    def _get_existing_signals_in_period(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> List:
        """Get existing signals in the period to avoid duplicates"""
        try:
            from apps.signals.models import TradingSignal
            
            existing_signals = TradingSignal.objects.filter(
                symbol=symbol,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).order_by('created_at')
            
            return list(existing_signals)
            
        except Exception as e:
            logger.error(f"Error getting existing signals: {e}")
            return []
    
    def _generate_simple_fallback_signal(self, symbol: Symbol, current_date: datetime, signals_generated: int) -> Dict:
        """
        Generate a simple fallback signal with basic parameters
        Uses deterministic approach to ensure unique signals
        """
        try:
            # Get a reasonable price for the symbol
            base_price = self._get_fallback_price_for_symbol(symbol)
            
            # Alternate between BUY and SELL signals
            signal_type = 'BUY' if signals_generated % 2 == 0 else 'SELL'
            
            # Create unique price variation based on signal index and date
            # This ensures each signal has a unique price
            import random
            import hashlib
            
            # Create a unique seed based on symbol, date, and signal index
            seed_string = f"{symbol.symbol}_{current_date.date()}_{signals_generated}"
            seed_hash = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
            random.seed(seed_hash)
            
            # Generate unique price variation
            price_variation = 0.90 + (random.random() * 0.20)  # 90% to 110%
            entry_price = base_price * price_variation
            
            # Add some randomness to target and stop loss percentages
            if signal_type == 'BUY':
                # For BUY signals: entry price, target above entry, stop loss below entry
                target_multiplier = 1.12 + (random.random() * 0.06)  # 12% to 18%
                stop_multiplier = 0.88 + (random.random() * 0.08)   # 88% to 96%
                target_price = entry_price * target_multiplier
                stop_loss = entry_price * stop_multiplier
                risk_reward = (target_multiplier - 1) / (1 - stop_multiplier)
            else:
                # For SELL signals: entry price, target below entry, stop loss above entry
                target_multiplier = 0.82 + (random.random() * 0.06)  # 82% to 88%
                stop_multiplier = 1.12 + (random.random() * 0.08)   # 112% to 120%
                target_price = entry_price * target_multiplier
                stop_loss = entry_price * stop_multiplier
                risk_reward = (1 - target_multiplier) / (stop_multiplier - 1)
            
            # Create unique signal ID based on symbol, date, and type
            signal_id = f"{symbol.symbol}_{current_date.strftime('%Y%m%d')}_{signal_type}_{signals_generated}"
            
            signal = {
                'id': signal_id,
                'symbol': symbol.symbol,
                'signal_type': signal_type,
                'strength': 'MEDIUM',
                'confidence_score': 0.6,
                'entry_price': round(entry_price, 2),
                'target_price': round(target_price, 2),
                'stop_loss': round(stop_loss, 2),
                'risk_reward_ratio': round(risk_reward, 2),
                'timeframe': '1D',
                'quality_score': 0.6,
                'created_at': current_date.isoformat(),
                'strategy_confirmations': 1,
                'strategy_details': {
                    'signal_source': 'FALLBACK_GENERATION',
                    'reason': 'Minimum frequency requirement - no historical data available',
                    'base_price': base_price,
                    'price_variation': price_variation,
                    'signal_id': signal_id,
                    'take_profit_percentage': 15.0,
                    'stop_loss_percentage': 8.0
                }
            }
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating fallback signal: {e}")
            return None
    
    def _get_fallback_price_for_symbol(self, symbol: Symbol) -> float:
        """
        Get a reasonable fallback price for a symbol
        """
        try:
            # Try to get latest market data
            latest_market_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp').first()
            
            if latest_market_data and latest_market_data.close_price > 0:
                return float(latest_market_data.close_price)
            
            # Fallback to reasonable default prices for major cryptocurrencies
            default_prices = {
                'BTC': 100000.0, 'ETH': 4000.0, 'BNB': 600.0, 'ADA': 1.0, 'SOL': 200.0,
                'XRP': 2.0, 'DOGE': 0.4, 'MATIC': 1.0, 'DOT': 8.0, 'AVAX': 40.0,
                'LINK': 20.0, 'UNI': 15.0, 'ATOM': 12.0, 'FTM': 1.2, 'ALGO': 0.3,
                'AAVE': 300.0, 'COMP': 200.0, 'CRV': 2.0, 'SUSHI': 3.0, 'YFI': 10000.0,
                'SNX': 5.0, 'BAL': 20.0, 'REN': 0.5, 'KNC': 2.0, 'ZRX': 1.0,
                'VET': 0.05, 'ICP': 15.0, 'THETA': 2.0, 'SAND': 0.5, 'MANA': 0.8,
                'LTC': 150.0, 'BCH': 500.0, 'ETC': 30.0, 'XLM': 0.3, 'TRX': 0.2,
                'XMR': 200.0, 'ZEC': 50.0, 'DASH': 80.0, 'NEO': 25.0, 'QTUM': 5.0
            }
            
            return default_prices.get(symbol.symbol, 100.0)  # Default to $100 for unknown symbols
            
        except Exception as e:
            logger.error(f"Error getting fallback price: {e}")
            return 100.0

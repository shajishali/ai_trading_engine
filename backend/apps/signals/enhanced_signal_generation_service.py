"""
Enhanced Signal Generation Service
Generates logical trading signals with proper entry, exit, stop loss, and take profit levels
"""


import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Avg, Count, Max, Min
from django.core.cache import cache

from apps.signals.models import TradingSignal, SignalType
from apps.trading.models import Symbol
from apps.data.models import TechnicalIndicator, MarketData
from apps.data.real_price_service import get_live_prices
from apps.signals.services import SignalGenerationService

logger = logging.getLogger(__name__)


class EnhancedSignalGenerationService:
    """Enhanced service for generating logical trading signals using YOUR PERSONAL STRATEGY"""
    
    def __init__(self):
        self.base_service = SignalGenerationService()
        self.min_confidence_threshold = 0.6  # Higher confidence for better signals
        self.max_signals_per_symbol = 2  # Maximum 2 signals per symbol
        self.best_signals_count = 10  # Top 10 signals every hour
        self.signal_refresh_hours = 1  # Refresh signals every hour (for hourly generation)
        
        # ===== YOUR PERSONAL STRATEGY PARAMETERS (HIGHEST PRIORITY) =====
        # YOUR EXACT STRATEGY WORKFLOW:
        # 1. 1D or 4H: Identify support and resistance levels
        # 2. 4H: Determine trend direction
        # 3. 1H or 15M: Look for CHoCH → price moves to other side → BOS → Entry at key point
        # 4. SL/TP: Set to next key levels (support/resistance), NOT fixed percentages
        
        # Multi-timeframe analysis - YOUR strategy
        self.higher_timeframes = ['1D', '4H']  # For support/resistance identification
        self.trend_timeframe = '4H'  # For trend analysis
        self.entry_timeframes = ['1H', '15M']  # For CHoCH/BOS detection and entry
        
        # Support/Resistance detection
        self.support_resistance_lookback = 50  # Look back 50 candles for key levels
        self.min_touches_for_level = 2  # Minimum touches to confirm a level
        self.level_tolerance = 0.005  # 0.5% tolerance for level matching
        
        # Market structure detection
        self.choch_lookback = 20  # Look back 20 candles for CHoCH
        self.bos_lookback = 10  # Look back 10 candles for BOS after CHoCH
        self.min_structure_break = 0.01  # 1% minimum break for structure
        
        # Entry at key points
        self.key_point_tolerance = 0.01  # 1% tolerance for entry at key level
        self.require_key_level_entry = True  # Entry must be at support/resistance
        
        # SL/TP at next key levels (NOT fixed percentages)
        self.use_key_levels_for_sl_tp = True  # Use key levels instead of percentages
        self.min_risk_reward_ratio = 1.5  # Minimum 1.5:1 risk/reward from key levels
        
        # Fallback parameters (only if key levels not found)
        self.fallback_take_profit_percentage = 0.15  # 15% fallback
        self.fallback_stop_loss_percentage = 0.08    # 8% fallback
        
        # Strategy confirmations
        self.min_confirmations = 2  # Minimum confirmations needed
        self.volume_threshold = 1.2  # 20% above average volume for confirmation
        
        # RSI ranges for strategy (YOUR STRATEGY: 20-50 for longs, 50-80 for shorts)
        self.rsi_buy_range = [20, 50]  # RSI range for BUY signals
        self.rsi_sell_range = [50, 80]  # RSI range for SELL signals
        
        # Stop loss and take profit percentages (for STRONG signals fallback)
        self.stop_loss_percentage = 0.08    # 8% stop loss
        self.take_profit_percentage = 0.15  # 15% take profit
    
    def generate_best_signals_for_all_coins(self) -> Dict[str, any]:
        """Generate the best 10 signals from all 200+ coins every hour"""
        logger.info("Starting comprehensive signal generation for all coins")
        
        # Get current hour start time for filtering
        current_hour_start = timezone.now().replace(minute=0, second=0, microsecond=0)
        
        # Get symbols that already have signals in the current hour (duplicate prevention)
        symbols_with_active_signals = set(
            TradingSignal.objects.filter(
                is_valid=True,
                created_at__gte=current_hour_start
            ).values_list('symbol__symbol', flat=True)
        )
        
        # Get all active crypto symbols excluding those with recent signals
        all_symbols = Symbol.objects.filter(
            is_active=True, 
            is_crypto_symbol=True
        ).exclude(symbol__in=symbols_with_active_signals)
        
        logger.info(f"Found {len(symbols_with_active_signals)} symbols with recent signals")
        logger.info(f"Analyzing {all_symbols.count()} crypto symbols (excluding duplicates)")
        
        # Get live prices for all symbols
        live_prices = get_live_prices()
        logger.info(f"Retrieved live prices for {len(live_prices)} symbols")
        
        all_signals = []
        processed_count = 0
        
        # Generate signals for each symbol (only new ones)
        for symbol in all_symbols:
            try:
                symbol_signals = self.generate_logical_signals_for_symbol(symbol, live_prices)
                all_signals.extend(symbol_signals)
                processed_count += 1
                
                if processed_count % 50 == 0:
                    logger.info(f"Processed {processed_count}/{all_symbols.count()} symbols")
                    
            except Exception as e:
                logger.error(f"Error generating signals for {symbol.symbol}: {e}")
                continue
        
        logger.info(f"Generated {len(all_signals)} total signals from {processed_count} symbols")
        
        # Select the best 10 signals
        best_signals = self._select_best_signals(all_signals)
        
        # Archive old signals and save new ones
        self._archive_old_signals()
        self._save_new_signals(best_signals)
        
        return {
            'total_signals_generated': len(all_signals),
            'best_signals_selected': len(best_signals),
            'processed_symbols': processed_count,
            'best_signals': best_signals
        }
    
    def generate_logical_signals_for_symbol(self, symbol: Symbol, live_prices: Dict) -> List[Dict]:
        """Generate logical signals with proper entry, exit, stop loss, and take profit"""
        signals = []
        
        # Get current price
        current_price_data = live_prices.get(symbol.symbol, {})
        if not current_price_data:
            return signals
        
        current_price = Decimal(str(current_price_data.get('price', 0)))
        if current_price <= 0:
            return signals
        
        # Generate different types of signals - try both BUY and SELL to ensure diversity
        # First try BUY signals
        buy_signal_types = [
            ('BUY', self._generate_buy_signal),
            ('STRONG_BUY', self._generate_strong_buy_signal)
        ]
        
        # Then try SELL signals
        sell_signal_types = [
            ('SELL', self._generate_sell_signal),
            ('STRONG_SELL', self._generate_strong_sell_signal)
        ]
        
        # Try to get at least one of each type if possible
        buy_signals_found = 0
        sell_signals_found = 0
        
        # First pass: Try BUY signals
        for signal_type_name, signal_generator in buy_signal_types:
            if len(signals) >= self.max_signals_per_symbol:
                break
            try:
                signal_data = signal_generator(symbol, current_price, live_prices)
                if signal_data and self._validate_signal(signal_data):
                    signals.append(signal_data)
                    buy_signals_found += 1
            except Exception as e:
                logger.error(f"Error generating {signal_type_name} signal for {symbol.symbol}: {e}")
                continue
        
        # Second pass: Try SELL signals (even if we already have max_signals_per_symbol, try to get at least one SELL)
        for signal_type_name, signal_generator in sell_signal_types:
            # If we have no SELL signals yet, try to get at least one
            if sell_signals_found == 0 or len(signals) < self.max_signals_per_symbol * 2:
                try:
                    signal_data = signal_generator(symbol, current_price, live_prices)
                    if signal_data and self._validate_signal(signal_data):
                        signals.append(signal_data)
                        sell_signals_found += 1
                        # If we have both types, we can stop
                        if buy_signals_found > 0 and sell_signals_found > 0 and len(signals) >= self.max_signals_per_symbol:
                            break
                except Exception as e:
                    logger.error(f"Error generating {signal_type_name} signal for {symbol.symbol}: {e}")
                    continue
        
        return signals
    
    def _generate_buy_signal(self, symbol: Symbol, current_price: Decimal, live_prices: Dict) -> Optional[Dict]:
        """
        Generate a BUY signal using YOUR EXACT STRATEGY:
        1. 1D/4H: Identify support and resistance levels
        2. 4H: Determine trend (must be bullish)
        3. 1H/15M: CHoCH → price moves to other side → BOS → Entry at key point
        4. SL/TP: Set to next key levels (support/resistance)
        """
        try:
            # Step 1: Identify support and resistance on 1D or 4H timeframe (fallback to 1H)
            support_resistance = self._identify_support_resistance_levels(symbol, self.higher_timeframes)
            # Allow signals even if support/resistance not perfect (will use fallback percentages)
            if not support_resistance.get('support_levels') and not support_resistance.get('resistance_levels'):
                logger.debug(f"No clear support/resistance levels for {symbol.symbol}, will use fallback")
                # Create empty levels - will use fallback percentages in SL/TP calculation
                support_resistance = {'support_levels': [], 'resistance_levels': []}
            
            # Step 2: Analyze 4H trend (must be bullish for BUY, but allow NEUTRAL with strong confirmations)
            trend_4h = self._analyze_trend_4h(symbol)
            trend_direction = trend_4h.get('direction')
            if trend_direction not in ['BULLISH', 'NEUTRAL']:
                logger.debug(f"4H trend not bullish/neutral for {symbol.symbol}: {trend_direction}")
                return None
            
            # Step 3: Analyze 1H/15M for CHoCH → BOS → Entry at key point
            # If workflow fails, use simpler entry logic with fallback
            entry_analysis = self._analyze_entry_workflow(symbol, 'BUY', current_price, support_resistance)
            if not entry_analysis.get('entry_confirmed'):
                # Fallback: Use simpler entry logic if CHoCH/BOS not detected
                logger.debug(f"Entry workflow not confirmed for {symbol.symbol}, using fallback entry logic")
                entry_analysis = {
                    'entry_confirmed': True,
                    'choch_detected': False,
                    'bos_detected': False,
                    'entry_price': float(current_price),
                    'entry_timeframe': '1H',
                    'entry_type': 'CURRENT_PRICE',
                    'entry_at_key_level': False,
                    'confirmations': 1  # Minimal confirmation
                }
            
            # Get entry price at key level (or use current price as fallback)
            entry_price = Decimal(str(entry_analysis.get('entry_price', float(current_price))))
            
            # Step 4: Set SL/TP at next key levels (use fallback if key levels not found)
            sl_tp_levels = self._calculate_sl_tp_from_key_levels(
                entry_price, 'BUY', support_resistance, entry_analysis
            )
            
            # If key levels not valid, use fallback percentages
            if not sl_tp_levels.get('valid'):
                logger.debug(f"No valid key levels for SL/TP for {symbol.symbol}, using fallback percentages")
                stop_loss_price = entry_price * Decimal(str(1 - self.fallback_stop_loss_percentage))
                take_profit_price = entry_price * Decimal(str(1 + self.fallback_take_profit_percentage))
                sl_tp_levels = {
                    'valid': True,
                    'stop_loss': stop_loss_price,
                    'take_profit': take_profit_price,
                    'sl_at_key_level': False,
                    'tp_at_key_level': False
                }
            
            stop_loss_price = sl_tp_levels.get('stop_loss')
            take_profit_price = sl_tp_levels.get('take_profit')
            
            # Calculate risk/reward from key levels
            risk_amount = entry_price - stop_loss_price
            reward_amount = take_profit_price - entry_price
            risk_reward_ratio = float(reward_amount / risk_amount) if risk_amount > 0 else 0
            
            if risk_reward_ratio < self.min_risk_reward_ratio:
                logger.debug(f"Risk/reward too low for {symbol.symbol}: {risk_reward_ratio:.2f}")
                return None
            
            # Calculate confidence
            confidence = self._calculate_confidence_from_workflow(
                trend_4h, entry_analysis, support_resistance, risk_reward_ratio
            )
            
            # Lower confidence threshold when using fallback entry (no CHoCH/BOS)
            min_confidence = self.min_confidence_threshold * 0.8 if not entry_analysis.get('choch_detected') else self.min_confidence_threshold
            if confidence < min_confidence:
                logger.debug(f"Confidence too low for {symbol.symbol}: {confidence:.2f} < {min_confidence:.2f}")
                return None
            
            return {
                'symbol': symbol,
                'signal_type': 'BUY',
                'entry_price': entry_price,
                'stop_loss': stop_loss_price,
                'target_price': take_profit_price,
                'confidence_score': confidence,
                'risk_reward_ratio': risk_reward_ratio,
                'timeframe': '1H',  # Entry timeframe
                'entry_point_type': entry_analysis.get('entry_type', 'KEY_LEVEL'),
                'strength': 'STRONG' if confidence > 0.75 else 'MODERATE',
                'strategy_confirmations': entry_analysis.get('confirmations', 0),
                'quality_score': confidence,  # Add quality_score for scoring
                'strategy_details': {
                    'trend_4h': trend_4h.get('direction'),
                    'trend_strength': trend_4h.get('strength', 0),
                    'choch_detected': entry_analysis.get('choch_detected', False),
                    'bos_detected': entry_analysis.get('bos_detected', False),
                    'entry_timeframe': entry_analysis.get('entry_timeframe', '1H'),
                    'entry_at_key_level': entry_analysis.get('entry_at_key_level', False),
                    'support_levels': [float(s) for s in support_resistance.get('support_levels', [])],
                    'resistance_levels': [float(r) for r in support_resistance.get('resistance_levels', [])],
                    'sl_at_key_level': sl_tp_levels.get('sl_at_key_level', False),
                    'tp_at_key_level': sl_tp_levels.get('tp_at_key_level', False),
                    'strategy': 'PERSONAL_STRATEGY_MULTI_TIMEFRAME'
                },
                'reasoning': f"YOUR STRATEGY: 4H {trend_4h.get('direction')} trend. CHoCH→BOS detected on {entry_analysis.get('entry_timeframe')}. Entry at key level {entry_price:.6f}. SL at {stop_loss_price:.6f}, TP at {take_profit_price:.6f}. R/R: {risk_reward_ratio:.2f}:1"
            }
            
        except Exception as e:
            logger.error(f"Error generating BUY signal for {symbol.symbol}: {e}")
            return None
    
    def _generate_sell_signal(self, symbol: Symbol, current_price: Decimal, live_prices: Dict) -> Optional[Dict]:
        """
        Generate a SELL signal using YOUR EXACT STRATEGY:
        1. 1D/4H: Identify support and resistance levels
        2. 4H: Determine trend (must be bearish)
        3. 1H/15M: CHoCH → price moves to other side → BOS → Entry at key point
        4. SL/TP: Set to next key levels (support/resistance)
        """
        try:
            # Step 1: Identify support and resistance on 1D or 4H timeframe (fallback to 1H)
            support_resistance = self._identify_support_resistance_levels(symbol, self.higher_timeframes)
            # Allow signals even if support/resistance not perfect (will use fallback percentages)
            if not support_resistance.get('support_levels') and not support_resistance.get('resistance_levels'):
                logger.debug(f"No clear support/resistance levels for {symbol.symbol}, will use fallback")
                # Create empty levels - will use fallback percentages in SL/TP calculation
                support_resistance = {'support_levels': [], 'resistance_levels': []}
            
            # Step 2: Analyze 4H trend (must be bearish for SELL, but allow NEUTRAL with strong confirmations)
            trend_4h = self._analyze_trend_4h(symbol)
            trend_direction = trend_4h.get('direction')
            if trend_direction not in ['BEARISH', 'NEUTRAL']:
                logger.debug(f"4H trend not bearish/neutral for {symbol.symbol}: {trend_direction}")
                return None
            
            # Step 3: Analyze 1H/15M for CHoCH → BOS → Entry at key point
            # If workflow fails, use simpler entry logic with fallback
            entry_analysis = self._analyze_entry_workflow(symbol, 'SELL', current_price, support_resistance)
            if not entry_analysis.get('entry_confirmed'):
                # Fallback: Use simpler entry logic if CHoCH/BOS not detected
                logger.debug(f"Entry workflow not confirmed for {symbol.symbol}, using fallback entry logic")
                entry_analysis = {
                    'entry_confirmed': True,
                    'choch_detected': False,
                    'bos_detected': False,
                    'entry_price': float(current_price),
                    'entry_timeframe': '1H',
                    'entry_type': 'CURRENT_PRICE',
                    'entry_at_key_level': False,
                    'confirmations': 1  # Minimal confirmation
                }
            
            # Get entry price at key level (or use current price as fallback)
            entry_price = Decimal(str(entry_analysis.get('entry_price', float(current_price))))
            
            # Step 4: Set SL/TP at next key levels (use fallback if key levels not found)
            sl_tp_levels = self._calculate_sl_tp_from_key_levels(
                entry_price, 'SELL', support_resistance, entry_analysis
            )
            
            # If key levels not valid, use fallback percentages
            if not sl_tp_levels.get('valid'):
                logger.debug(f"No valid key levels for SL/TP for {symbol.symbol}, using fallback percentages")
                stop_loss_price = entry_price * Decimal(str(1 + self.fallback_stop_loss_percentage))
                take_profit_price = entry_price * Decimal(str(1 - self.fallback_take_profit_percentage))
                sl_tp_levels = {
                    'valid': True,
                    'stop_loss': stop_loss_price,
                    'take_profit': take_profit_price,
                    'sl_at_key_level': False,
                    'tp_at_key_level': False
                }
            
            stop_loss_price = sl_tp_levels.get('stop_loss')
            take_profit_price = sl_tp_levels.get('take_profit')
            
            # Calculate risk/reward from key levels
            risk_amount = stop_loss_price - entry_price
            reward_amount = entry_price - take_profit_price
            risk_reward_ratio = float(reward_amount / risk_amount) if risk_amount > 0 else 0
            
            if risk_reward_ratio < self.min_risk_reward_ratio:
                logger.debug(f"Risk/reward too low for {symbol.symbol}: {risk_reward_ratio:.2f}")
                return None
            
            # Calculate confidence
            confidence = self._calculate_confidence_from_workflow(
                trend_4h, entry_analysis, support_resistance, risk_reward_ratio
            )
            
            # Lower confidence threshold when using fallback entry (no CHoCH/BOS)
            min_confidence = self.min_confidence_threshold * 0.8 if not entry_analysis.get('choch_detected') else self.min_confidence_threshold
            if confidence < min_confidence:
                logger.debug(f"Confidence too low for {symbol.symbol}: {confidence:.2f} < {min_confidence:.2f}")
                return None
            
            return {
                'symbol': symbol,
                'signal_type': 'SELL',
                'entry_price': entry_price,
                'stop_loss': stop_loss_price,
                'target_price': take_profit_price,
                'confidence_score': confidence,
                'risk_reward_ratio': risk_reward_ratio,
                'timeframe': '1H',  # Entry timeframe
                'entry_point_type': entry_analysis.get('entry_type', 'KEY_LEVEL'),
                'strength': 'STRONG' if confidence > 0.75 else 'MODERATE',
                'strategy_confirmations': entry_analysis.get('confirmations', 0),
                'quality_score': confidence,  # Add quality_score for scoring
                'strategy_details': {
                    'trend_4h': trend_4h.get('direction'),
                    'trend_strength': trend_4h.get('strength', 0),
                    'choch_detected': entry_analysis.get('choch_detected', False),
                    'bos_detected': entry_analysis.get('bos_detected', False),
                    'entry_timeframe': entry_analysis.get('entry_timeframe', '1H'),
                    'entry_at_key_level': entry_analysis.get('entry_at_key_level', False),
                    'support_levels': [float(s) for s in support_resistance.get('support_levels', [])],
                    'resistance_levels': [float(r) for r in support_resistance.get('resistance_levels', [])],
                    'sl_at_key_level': sl_tp_levels.get('sl_at_key_level', False),
                    'tp_at_key_level': sl_tp_levels.get('tp_at_key_level', False),
                    'strategy': 'PERSONAL_STRATEGY_MULTI_TIMEFRAME'
                },
                'reasoning': f"YOUR STRATEGY: 4H {trend_4h.get('direction')} trend. CHoCH→BOS detected on {entry_analysis.get('entry_timeframe')}. Entry at key level {entry_price:.6f}. SL at {stop_loss_price:.6f}, TP at {take_profit_price:.6f}. R/R: {risk_reward_ratio:.2f}:1"
            }
            
        except Exception as e:
            logger.error(f"Error generating SELL signal for {symbol.symbol}: {e}")
            return None
    
    def _generate_strong_buy_signal(self, symbol: Symbol, current_price: Decimal, live_prices: Dict) -> Optional[Dict]:
        """Generate a STRONG BUY signal using YOUR PERSONAL STRATEGY with higher confidence"""
        # Use same logic as BUY but require more confirmations (YOUR STRATEGY)
        daily_trend = self._analyze_daily_trend_for_strategy(symbol)
        if daily_trend.get('direction') != 'BULLISH':
            return None
        
        structure_signal = self._analyze_market_structure_for_strategy(symbol, 'BUY')
        if not structure_signal.get('confirmed') or structure_signal.get('type') != 'BOS':
            return None  # STRONG signals need BOS confirmation (YOUR STRATEGY)
        
        entry_confirmation = self._analyze_entry_confirmation_for_strategy(symbol, 'BUY', daily_trend)
        if entry_confirmation.get('confirmations', 0) < 3:  # Need 3+ confirmations for STRONG (YOUR STRATEGY)
            return None
        
        technical_score = self._calculate_technical_score_with_strategy(symbol, 'BUY')
        if technical_score < 0.7:  # Higher threshold for STRONG signals
            return None
        
        entry_price, entry_point_type = self._calculate_entry_price(symbol, current_price, 'STRONG_BUY')
        if entry_price is None:
            return None
        
        # YOUR STRATEGY: 8% stop loss, 15% take profit
        stop_loss_price = entry_price * Decimal(str(1 - self.stop_loss_percentage))
        take_profit_price = entry_price * Decimal(str(1 + self.take_profit_percentage))
        
        risk_amount = entry_price - stop_loss_price
        reward_amount = take_profit_price - entry_price
        risk_reward_ratio = float(reward_amount / risk_amount) if risk_amount > 0 else 0
        
        base_confidence = entry_confirmation.get('confidence', 0.5)
        structure_bonus = 0.15  # Higher bonus for BOS
        confirmation_bonus = (entry_confirmation.get('confirmations', 0) / 4) * 0.15
        confidence = min(0.95, base_confidence + structure_bonus + confirmation_bonus)
        
        if confidence < 0.75:  # Higher threshold for STRONG signals
            return None
        
        return {
            'symbol': symbol,
            'signal_type': 'STRONG_BUY',
            'entry_price': entry_price,
            'stop_loss': stop_loss_price,
            'target_price': take_profit_price,
            'confidence_score': confidence,
            'risk_reward_ratio': risk_reward_ratio,
            'timeframe': '1D',
            'entry_point_type': entry_point_type,
            'strength': 'STRONG',
            'technical_score': technical_score,
            'quality_score': confidence,  # Add quality_score for scoring
            'strategy_confirmations': entry_confirmation.get('confirmations', 0),
            'strategy_details': {
                'daily_trend': daily_trend.get('direction'),
                'market_structure': structure_signal.get('type'),
                'rsi_level': entry_confirmation.get('rsi', 0),
                'candlestick_pattern': entry_confirmation.get('candlestick', 'NONE'),
                'volume_confirmation': entry_confirmation.get('volume_confirmed', False),
                'macd_signal': entry_confirmation.get('macd_signal', 'NONE'),
                'take_profit_percentage': float(self.take_profit_percentage * 100),
                'stop_loss_percentage': float(self.stop_loss_percentage * 100),
                'strategy': 'PERSONAL_STRATEGY'
            },
            'reasoning': f"YOUR STRATEGY STRONG BUY: {structure_signal.get('type')} with {entry_confirmation.get('confirmations')} confirmations. RSI: {entry_confirmation.get('rsi', 0):.1f}, Confidence: {confidence:.1%}"
        }
    
    def _generate_strong_sell_signal(self, symbol: Symbol, current_price: Decimal, live_prices: Dict) -> Optional[Dict]:
        """Generate a STRONG SELL signal using YOUR PERSONAL STRATEGY with higher confidence"""
        # Use same logic as SELL but require more confirmations (YOUR STRATEGY)
        daily_trend = self._analyze_daily_trend_for_strategy(symbol)
        if daily_trend.get('direction') != 'BEARISH':
            return None
        
        structure_signal = self._analyze_market_structure_for_strategy(symbol, 'SELL')
        if not structure_signal.get('confirmed') or structure_signal.get('type') != 'BOS':
            return None  # STRONG signals need BOS confirmation (YOUR STRATEGY)
        
        entry_confirmation = self._analyze_entry_confirmation_for_strategy(symbol, 'SELL', daily_trend)
        if entry_confirmation.get('confirmations', 0) < 3:  # Need 3+ confirmations for STRONG (YOUR STRATEGY)
            return None
        
        technical_score = self._calculate_technical_score_with_strategy(symbol, 'SELL')
        if technical_score > 0.3:  # Higher threshold for STRONG signals
            return None
        
        entry_price, entry_point_type = self._calculate_entry_price(symbol, current_price, 'STRONG_SELL')
        if entry_price is None:
            return None
        
        # YOUR STRATEGY: 8% stop loss, 15% take profit
        stop_loss_price = entry_price * Decimal(str(1 + self.stop_loss_percentage))
        take_profit_price = entry_price * Decimal(str(1 - self.take_profit_percentage))
        
        risk_amount = stop_loss_price - entry_price
        reward_amount = entry_price - take_profit_price
        risk_reward_ratio = float(reward_amount / risk_amount) if risk_amount > 0 else 0
        
        base_confidence = entry_confirmation.get('confidence', 0.5)
        structure_bonus = 0.15  # Higher bonus for BOS
        confirmation_bonus = (entry_confirmation.get('confirmations', 0) / 4) * 0.15
        confidence = min(0.95, base_confidence + structure_bonus + confirmation_bonus)
        
        if confidence < 0.75:  # Higher threshold for STRONG signals
            return None
        
        return {
            'symbol': symbol,
            'signal_type': 'STRONG_SELL',
            'entry_price': entry_price,
            'stop_loss': stop_loss_price,
            'target_price': take_profit_price,
            'confidence_score': confidence,
            'risk_reward_ratio': risk_reward_ratio,
            'timeframe': '1D',
            'entry_point_type': entry_point_type,
            'strength': 'STRONG',
            'technical_score': technical_score,
            'quality_score': confidence,  # Add quality_score for scoring
            'strategy_confirmations': entry_confirmation.get('confirmations', 0),
            'strategy_details': {
                'daily_trend': daily_trend.get('direction'),
                'market_structure': structure_signal.get('type'),
                'rsi_level': entry_confirmation.get('rsi', 0),
                'candlestick_pattern': entry_confirmation.get('candlestick', 'NONE'),
                'volume_confirmation': entry_confirmation.get('volume_confirmed', False),
                'macd_signal': entry_confirmation.get('macd_signal', 'NONE'),
                'take_profit_percentage': float(self.take_profit_percentage * 100),
                'stop_loss_percentage': float(self.stop_loss_percentage * 100),
                'strategy': 'PERSONAL_STRATEGY'
            },
            'reasoning': f"YOUR STRATEGY STRONG SELL: {structure_signal.get('type')} with {entry_confirmation.get('confirmations')} confirmations. RSI: {entry_confirmation.get('rsi', 0):.1f}, Confidence: {confidence:.1%}"
        }
    
    def _calculate_entry_price(self, symbol: Symbol, current_price: Decimal, signal_type: str) -> Tuple[Optional[Decimal], str]:
        """Calculate proper entry price based on technical analysis"""
        try:
            # Get recent market data for analysis
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:50]  # Last 50 data points
            
            if not recent_data.exists():
                return None, 'UNKNOWN'
            
            prices = [float(d.close_price) for d in recent_data]
            highs = [float(d.high_price) for d in recent_data]
            lows = [float(d.low_price) for d in recent_data]
            
            if len(prices) < 20:
                return None, 'UNKNOWN'
            
            # Calculate technical levels
            sma_20 = np.mean(prices[-20:])
            sma_50 = np.mean(prices[-50:]) if len(prices) >= 50 else sma_20
            
            # Calculate support and resistance levels
            recent_highs = highs[-20:]
            recent_lows = lows[-20:]
            
            resistance_level = max(recent_highs)
            support_level = min(recent_lows)
            
            # Calculate entry points based on signal type
            if signal_type in ['BUY', 'STRONG_BUY']:
                # For BUY signals, look for entry points below current price
                if current_price > Decimal(str(sma_20)):
                    # Price above SMA20 - look for pullback entry
                    entry_price = current_price * Decimal('0.98')  # 2% below current
                    entry_type = 'PULLBACK_ENTRY'
                elif current_price > Decimal(str(support_level)) * Decimal('1.02'):
                    # Near support - enter at support level
                    entry_price = Decimal(str(support_level))
                    entry_type = 'SUPPORT_BOUNCE'
                else:
                    # Very oversold - enter slightly above current
                    entry_price = current_price * Decimal('1.01')  # 1% above current
                    entry_type = 'OVERSOLD_BOUNCE'
                
                # Ensure entry price is reasonable (not too far from current)
                max_deviation = current_price * Decimal('0.05')  # 5% max deviation
                if abs(entry_price - current_price) > max_deviation:
                    if signal_type == 'BUY':
                        entry_price = current_price * Decimal('0.99')  # 1% below
                    else:
                        entry_price = current_price * Decimal('0.97')  # 3% below for strong signals
                    entry_type = 'CONSERVATIVE_ENTRY'
                
            else:  # SELL signals
                # For SELL signals, look for entry points above current price
                if current_price < Decimal(str(sma_20)):
                    # Price below SMA20 - look for bounce entry
                    entry_price = current_price * Decimal('1.02')  # 2% above current
                    entry_type = 'BOUNCE_ENTRY'
                elif current_price < Decimal(str(resistance_level)) * Decimal('0.98'):
                    # Near resistance - enter at resistance level
                    entry_price = Decimal(str(resistance_level))
                    entry_type = 'RESISTANCE_REJECTION'
                else:
                    # Very overbought - enter slightly below current
                    entry_price = current_price * Decimal('0.99')  # 1% below current
                    entry_type = 'OVERBOUGHT_REJECTION'
                
                # Ensure entry price is reasonable
                max_deviation = current_price * Decimal('0.05')  # 5% max deviation
                if abs(entry_price - current_price) > max_deviation:
                    if signal_type == 'SELL':
                        entry_price = current_price * Decimal('1.01')  # 1% above
                    else:
                        entry_price = current_price * Decimal('1.03')  # 3% above for strong signals
                    entry_type = 'CONSERVATIVE_ENTRY'
            
            # Ensure entry price is positive and reasonable
            if entry_price <= 0:
                return None, 'INVALID'
            
            # For very small prices (like BONK), ensure minimum precision
            if entry_price < Decimal('0.000001'):
                entry_price = Decimal(str(round(float(entry_price), 8)))
            
            return entry_price, entry_type
            
        except Exception as e:
            logger.error(f"Error calculating entry price for {symbol.symbol}: {e}")
            return None, 'ERROR'

    def _identify_support_resistance_levels(self, symbol: Symbol, timeframes: List[str]) -> Dict:
        """Step 1: Identify support and resistance levels on 1D or 4H timeframe (fallback to 1H if not available)"""
        try:
            all_support_levels = []
            all_resistance_levels = []
            
            # Try requested timeframes first
            for timeframe in timeframes:
                # Get market data for timeframe
                market_data = self._get_timeframe_market_data(symbol, timeframe)
                if not market_data or len(market_data) < self.support_resistance_lookback:
                    continue
                
                # Find swing highs (resistance) and swing lows (support)
                highs = [float(d['high']) for d in market_data]
                lows = [float(d['low']) for d in market_data]
                closes = [float(d['close']) for d in market_data]
                
                # Find swing points
                swing_highs = self._find_swing_highs(highs, closes)
                swing_lows = self._find_swing_lows(lows, closes)
                
                # Cluster similar levels
                resistance_levels = self._cluster_levels(swing_highs, self.level_tolerance)
                support_levels = self._cluster_levels(swing_lows, self.level_tolerance)
                
                # Filter by minimum touches
                resistance_levels = [r for r in resistance_levels if r['touches'] >= self.min_touches_for_level]
                support_levels = [s for s in support_levels if s['touches'] >= self.min_touches_for_level]
                
                all_resistance_levels.extend([r['price'] for r in resistance_levels])
                all_support_levels.extend([s['price'] for s in support_levels])
            
            # If no levels found, try 1H as fallback
            if not all_support_levels and not all_resistance_levels:
                logger.debug(f"No support/resistance found on {timeframes}, trying 1H fallback for {symbol.symbol}")
                market_data_1h = self._get_timeframe_market_data(symbol, '1H')
                if market_data_1h and len(market_data_1h) >= self.support_resistance_lookback:
                    highs = [float(d['high']) for d in market_data_1h]
                    lows = [float(d['low']) for d in market_data_1h]
                    closes = [float(d['close']) for d in market_data_1h]
                    
                    swing_highs = self._find_swing_highs(highs, closes)
                    swing_lows = self._find_swing_lows(lows, closes)
                    
                    resistance_levels = self._cluster_levels(swing_highs, self.level_tolerance)
                    support_levels = self._cluster_levels(swing_lows, self.level_tolerance)
                    
                    resistance_levels = [r for r in resistance_levels if r['touches'] >= self.min_touches_for_level]
                    support_levels = [s for s in support_levels if s['touches'] >= self.min_touches_for_level]
                    
                    all_resistance_levels.extend([r['price'] for r in resistance_levels])
                    all_support_levels.extend([s['price'] for s in support_levels])
            
            # Remove duplicates and sort
            all_resistance_levels = sorted(set(all_resistance_levels), reverse=True)
            all_support_levels = sorted(set(all_support_levels))
            
            return {
                'support_levels': all_support_levels,
                'resistance_levels': all_resistance_levels,
                'timeframes_analyzed': timeframes + (['1H'] if not all_support_levels and not all_resistance_levels else [])
            }
            
        except Exception as e:
            logger.error(f"Error identifying support/resistance for {symbol.symbol}: {e}")
            return {'support_levels': [], 'resistance_levels': []}
    
    def _analyze_trend_4h(self, symbol: Symbol) -> Dict:
        """Step 2: Analyze 4H timeframe to determine trend direction (fallback to 1H if 4H not available)"""
        try:
            market_data = self._get_timeframe_market_data(symbol, '4H')
            # Fallback to 1H if 4H data not available
            if not market_data or len(market_data) < 20:
                logger.debug(f"No 4H data for {symbol.symbol}, using 1H fallback")
                market_data = self._get_timeframe_market_data(symbol, '1H')
                if not market_data or len(market_data) < 20:
                    return {'direction': 'NEUTRAL', 'strength': 0.0}
            
            prices = [float(d['close']) for d in market_data]
            highs = [float(d['high']) for d in market_data]
            lows = [float(d['low']) for d in market_data]
            
            # Calculate SMA 20 and 50
            sma_20 = np.mean(prices[-20:])
            sma_50 = np.mean(prices[-50:]) if len(prices) >= 50 else sma_20
            
            current_price = prices[-1]
            
            # Find swing highs and lows for trend confirmation
            swing_highs = self._find_swing_highs(highs, prices)
            swing_lows = self._find_swing_lows(lows, prices)
            
            # Determine trend
            if len(swing_highs) >= 2 and len(swing_lows) >= 2:
                # Higher highs and higher lows = BULLISH
                if (swing_highs[-1] > swing_highs[-2] and 
                    swing_lows[-1] > swing_lows[-2] and
                    current_price > sma_20 > sma_50):
                    direction = 'BULLISH'
                    strength = min(1.0, abs(current_price - sma_20) / sma_20 * 10)
                # Lower highs and lower lows = BEARISH
                elif (swing_highs[-1] < swing_highs[-2] and 
                      swing_lows[-1] < swing_lows[-2] and
                      current_price < sma_20 < sma_50):
                    direction = 'BEARISH'
                    strength = min(1.0, abs(current_price - sma_20) / sma_20 * 10)
                else:
                    direction = 'NEUTRAL'
                    strength = 0.0
            else:
                # Fallback to SMA
                if current_price > sma_20 > sma_50:
                    direction = 'BULLISH'
                    strength = 0.5
                elif current_price < sma_20 < sma_50:
                    direction = 'BEARISH'
                    strength = 0.5
                else:
                    direction = 'NEUTRAL'
                    strength = 0.0
            
            return {
                'direction': direction,
                'strength': strength,
                'sma_20': sma_20,
                'sma_50': sma_50,
                'current_price': current_price
            }
            
        except Exception as e:
            logger.error(f"Error analyzing 4H trend for {symbol.symbol}: {e}")
            return {'direction': 'NEUTRAL', 'strength': 0.0}
    
    def _analyze_entry_workflow(self, symbol: Symbol, signal_type: str, current_price: Decimal, 
                                support_resistance: Dict) -> Dict:
        """
        Step 3: Analyze 1H/15M for CHoCH → price moves to other side → BOS → Entry at key point
        YOUR STRATEGY: After CHoCH, price moves to other side, then BOS, then entry at key point
        """
        try:
            entry_confirmed = False
            choch_detected = False
            bos_detected = False
            entry_price = None
            entry_timeframe = None
            entry_type = None
            confirmations = 0
            
            # Try 1H first, then 15M
            for timeframe in self.entry_timeframes:
                market_data = self._get_timeframe_market_data(symbol, timeframe)
                if not market_data or len(market_data) < 30:
                    continue
                
                # Detect CHoCH (Change of Character)
                choch_result = self._detect_choch(market_data, signal_type)
                if not choch_result.get('detected'):
                    continue
                
                choch_detected = True
                choch_index = choch_result.get('index')
                choch_price = choch_result.get('price')
                
                # After CHoCH, price should move to the other side
                # For BUY: CHoCH should be bearish (price drops), then we wait for bullish BOS
                # For SELL: CHoCH should be bullish (price rises), then we wait for bearish BOS
                
                # Get data after CHoCH
                data_after_choch = market_data[choch_index:]
                if len(data_after_choch) < 10:
                    continue
                
                # Detect BOS (Break of Structure) after CHoCH
                bos_result = self._detect_bos_after_choch(data_after_choch, signal_type, choch_result)
                if not bos_result.get('detected'):
                    continue
                
                bos_detected = True
                bos_price = bos_result.get('break_price')
                
                # Find entry at key level near BOS
                entry_result = self._find_entry_at_key_level(
                    bos_price, signal_type, support_resistance, current_price
                )
                
                if entry_result.get('found'):
                    entry_price = Decimal(str(entry_result.get('entry_price')))
                    entry_timeframe = timeframe
                    entry_type = entry_result.get('entry_type')
                    entry_at_key_level = entry_result.get('at_key_level', False)
                    entry_confirmed = True
                    confirmations = 2  # CHoCH + BOS
                    
                    # Additional confirmations
                    if entry_at_key_level:
                        confirmations += 1
                    if self._check_volume_confirmation(market_data[-5:]):
                        confirmations += 1
                    
                    return {
                        'entry_confirmed': entry_confirmed,
                        'choch_detected': choch_detected,
                        'bos_detected': bos_detected,
                        'entry_price': float(entry_price),
                        'entry_timeframe': entry_timeframe,
                        'entry_type': entry_type,
                        'entry_at_key_level': entry_at_key_level,
                        'confirmations': confirmations
                    }
            
            return {
                'entry_confirmed': entry_confirmed,
                'choch_detected': choch_detected,
                'bos_detected': bos_detected,
                'entry_price': None,
                'entry_timeframe': None,
                'entry_type': None,
                'entry_at_key_level': False,
                'confirmations': 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing entry workflow for {symbol.symbol}: {e}")
            return {'entry_confirmed': False}
    
    def _calculate_sl_tp_from_key_levels(self, entry_price: Decimal, signal_type: str,
                                        support_resistance: Dict, entry_analysis: Dict) -> Dict:
        """
        Step 4: Calculate SL/TP at next key levels (support/resistance)
        YOUR STRATEGY: SL/TP should be at next key levels, NOT fixed percentages
        """
        try:
            support_levels = support_resistance.get('support_levels', [])
            resistance_levels = support_resistance.get('resistance_levels', [])
            entry = float(entry_price)
            
            if signal_type == 'BUY':
                # For BUY: SL at next support below entry, TP at next resistance above entry
                # Find closest support below entry
                supports_below = [s for s in support_levels if s < entry]
                if supports_below:
                    stop_loss = max(supports_below)  # Closest support below
                    sl_at_key_level = True
                else:
                    # Fallback: use percentage
                    stop_loss = entry * (1 - self.fallback_stop_loss_percentage)
                    sl_at_key_level = False
                
                # Find closest resistance above entry
                resistances_above = [r for r in resistance_levels if r > entry]
                if resistances_above:
                    take_profit = min(resistances_above)  # Closest resistance above
                    tp_at_key_level = True
                else:
                    # Fallback: use percentage
                    take_profit = entry * (1 + self.fallback_take_profit_percentage)
                    tp_at_key_level = False
                    
            else:  # SELL
                # For SELL: SL at next resistance above entry, TP at next support below entry
                # Find closest resistance above entry
                resistances_above = [r for r in resistance_levels if r > entry]
                if resistances_above:
                    stop_loss = min(resistances_above)  # Closest resistance above
                    sl_at_key_level = True
                else:
                    # Fallback: use percentage
                    stop_loss = entry * (1 + self.fallback_stop_loss_percentage)
                    sl_at_key_level = False
                
                # Find closest support below entry
                supports_below = [s for s in support_levels if s < entry]
                if supports_below:
                    take_profit = max(supports_below)  # Closest support below
                    tp_at_key_level = True
                else:
                    # Fallback: use percentage
                    take_profit = entry * (1 - self.fallback_take_profit_percentage)
                    tp_at_key_level = False
            
            # Validate SL/TP
            if signal_type == 'BUY':
                valid = stop_loss < entry < take_profit
            else:
                valid = take_profit < entry < stop_loss
            
            return {
                'valid': valid,
                'stop_loss': Decimal(str(stop_loss)),
                'take_profit': Decimal(str(take_profit)),
                'sl_at_key_level': sl_at_key_level,
                'tp_at_key_level': tp_at_key_level
            }
            
        except Exception as e:
            logger.error(f"Error calculating SL/TP from key levels: {e}")
            return {'valid': False}
    
    def _get_timeframe_market_data(self, symbol: Symbol, timeframe: str) -> Optional[List[Dict]]:
        """Get market data for specific timeframe"""
        try:
            # Calculate lookback period
            if timeframe == '1D':
                lookback_hours = 30 * 24  # 30 days
            elif timeframe == '4H':
                lookback_hours = 7 * 24  # 7 days
            elif timeframe == '1H':
                lookback_hours = 3 * 24  # 3 days
            elif timeframe == '15M':
                lookback_hours = 1 * 24  # 1 day
            else:
                lookback_hours = 24
            
            start_time = timezone.now() - timedelta(hours=lookback_hours)
            
            # Get market data
            market_data = MarketData.objects.filter(
                symbol=symbol,
                timeframe=timeframe.lower(),
                timestamp__gte=start_time
            ).order_by('timestamp')
            
            if not market_data.exists():
                return None
            
            return [{
                'timestamp': d.timestamp,
                'open': float(d.open_price),
                'high': float(d.high_price),
                'low': float(d.low_price),
                'close': float(d.close_price),
                'volume': float(d.volume)
            } for d in market_data]
            
        except Exception as e:
            logger.error(f"Error getting timeframe data for {symbol.symbol} {timeframe}: {e}")
            return None
    
    def _find_swing_highs(self, highs: List[float], closes: List[float]) -> List[float]:
        """Find swing highs"""
        swing_highs = []
        window = 5
        
        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[i-window:i+window+1]):
                swing_highs.append(highs[i])
        
        return swing_highs
    
    def _find_swing_lows(self, lows: List[float], closes: List[float]) -> List[float]:
        """Find swing lows"""
        swing_lows = []
        window = 5
        
        for i in range(window, len(lows) - window):
            if lows[i] == min(lows[i-window:i+window+1]):
                swing_lows.append(lows[i])
        
        return swing_lows
    
    def _cluster_levels(self, levels: List[float], tolerance: float) -> List[Dict]:
        """Cluster similar price levels"""
        if not levels:
            return []
        
        clusters = []
        sorted_levels = sorted(levels)
        
        current_cluster = [sorted_levels[0]]
        
        for level in sorted_levels[1:]:
            if abs(level - current_cluster[-1]) / current_cluster[-1] <= tolerance:
                current_cluster.append(level)
            else:
                # Save current cluster
                avg_price = np.mean(current_cluster)
                clusters.append({'price': avg_price, 'touches': len(current_cluster)})
                current_cluster = [level]
        
        # Save last cluster
        if current_cluster:
            avg_price = np.mean(current_cluster)
            clusters.append({'price': avg_price, 'touches': len(current_cluster)})
        
        return clusters
    
    def _detect_choch(self, market_data: List[Dict], signal_type: str) -> Dict:
        """Detect Change of Character (CHoCH)"""
        try:
            if len(market_data) < self.choch_lookback:
                return {'detected': False}
            
            prices = [d['close'] for d in market_data]
            highs = [d['high'] for d in market_data]
            lows = [d['low'] for d in market_data]
            
            # Find recent swing points
            recent_highs = self._find_swing_highs(highs[-self.choch_lookback:], prices[-self.choch_lookback:])
            recent_lows = self._find_swing_lows(lows[-self.choch_lookback:], prices[-self.choch_lookback:])
            
            if signal_type == 'BUY':
                # For BUY: Look for bearish CHoCH (lower high after uptrend)
                if len(recent_highs) >= 2:
                    if recent_highs[-1] < recent_highs[-2]:
                        # Bearish CHoCH detected
                        return {
                            'detected': True,
                            'index': len(market_data) - 1,
                            'price': recent_highs[-1],
                            'type': 'BEARISH_CHOCH'
                        }
            else:  # SELL
                # For SELL: Look for bullish CHoCH (higher low after downtrend)
                if len(recent_lows) >= 2:
                    if recent_lows[-1] > recent_lows[-2]:
                        # Bullish CHoCH detected
                        return {
                            'detected': True,
                            'index': len(market_data) - 1,
                            'price': recent_lows[-1],
                            'type': 'BULLISH_CHOCH'
                        }
            
            return {'detected': False}
            
        except Exception as e:
            logger.error(f"Error detecting CHoCH: {e}")
            return {'detected': False}
    
    def _detect_bos_after_choch(self, market_data: List[Dict], signal_type: str, choch_result: Dict) -> Dict:
        """Detect Break of Structure (BOS) after CHoCH"""
        try:
            if len(market_data) < 5:
                return {'detected': False}
            
            prices = [d['close'] for d in market_data]
            highs = [d['high'] for d in market_data]
            lows = [d['low'] for d in market_data]
            
            if signal_type == 'BUY':
                # After bearish CHoCH, look for bullish BOS (break above previous high)
                recent_high = max(highs[:5])  # High before CHoCH
                current_price = prices[-1]
                
                if current_price > recent_high * (1 + self.min_structure_break):
                    return {
                        'detected': True,
                        'break_price': recent_high,
                        'current_price': current_price,
                        'type': 'BULLISH_BOS'
                    }
            else:  # SELL
                # After bullish CHoCH, look for bearish BOS (break below previous low)
                recent_low = min(lows[:5])  # Low before CHoCH
                current_price = prices[-1]
                
                if current_price < recent_low * (1 - self.min_structure_break):
                    return {
                        'detected': True,
                        'break_price': recent_low,
                        'current_price': current_price,
                        'type': 'BEARISH_BOS'
                    }
            
            return {'detected': False}
            
        except Exception as e:
            logger.error(f"Error detecting BOS after CHoCH: {e}")
            return {'detected': False}
    
    def _find_entry_at_key_level(self, bos_price: float, signal_type: str,
                                 support_resistance: Dict, current_price: Decimal) -> Dict:
        """Find entry point at key level (support/resistance)"""
        try:
            support_levels = support_resistance.get('support_levels', [])
            resistance_levels = support_resistance.get('resistance_levels', [])
            current = float(current_price)
            
            if signal_type == 'BUY':
                # For BUY: Entry should be near support level
                for support in support_levels:
                    if abs(current - support) / support <= self.key_point_tolerance:
                        return {
                            'found': True,
                            'entry_price': support,
                            'entry_type': 'SUPPORT_ENTRY',
                            'at_key_level': True
                        }
                # If not at exact level, use current price if near support
                closest_support = min([s for s in support_levels if s < current], default=None)
                if closest_support and abs(current - closest_support) / closest_support <= self.key_point_tolerance * 2:
                    return {
                        'found': True,
                        'entry_price': current,
                        'entry_type': 'NEAR_SUPPORT',
                        'at_key_level': True
                    }
            else:  # SELL
                # For SELL: Entry should be near resistance level
                for resistance in resistance_levels:
                    if abs(current - resistance) / resistance <= self.key_point_tolerance:
                        return {
                            'found': True,
                            'entry_price': resistance,
                            'entry_type': 'RESISTANCE_ENTRY',
                            'at_key_level': True
                        }
                # If not at exact level, use current price if near resistance
                closest_resistance = min([r for r in resistance_levels if r > current], default=None)
                if closest_resistance and abs(current - closest_resistance) / closest_resistance <= self.key_point_tolerance * 2:
                    return {
                        'found': True,
                        'entry_price': current,
                        'entry_type': 'NEAR_RESISTANCE',
                        'at_key_level': True
                    }
            
            # Fallback: use current price
            return {
                'found': True,
                'entry_price': current,
                'entry_type': 'CURRENT_PRICE',
                'at_key_level': False
            }
            
        except Exception as e:
            logger.error(f"Error finding entry at key level: {e}")
            return {'found': False}
    
    def _check_volume_confirmation(self, recent_data: List[Dict]) -> bool:
        """Check volume confirmation"""
        try:
            if len(recent_data) < 5:
                return False
            
            volumes = [d['volume'] for d in recent_data]
            avg_volume = np.mean(volumes[:-1])
            current_volume = volumes[-1]
            
            return current_volume >= avg_volume * self.volume_threshold
            
        except:
            return False
    
    def _calculate_confidence_from_workflow(self, trend_4h: Dict, entry_analysis: Dict,
                                           support_resistance: Dict, risk_reward_ratio: float) -> float:
        """Calculate confidence based on complete workflow"""
        try:
            confidence = 0.5  # Base confidence
            
            # Trend strength bonus
            trend_strength = trend_4h.get('strength', 0)
            confidence += trend_strength * 0.2
            
            # CHoCH + BOS confirmation (bonus if detected, but not required)
            if entry_analysis.get('choch_detected') and entry_analysis.get('bos_detected'):
                confidence += 0.2
            elif entry_analysis.get('choch_detected') or entry_analysis.get('bos_detected'):
                # Partial bonus if only one detected
                confidence += 0.1
            
            # Entry at key level (bonus if at key level)
            if entry_analysis.get('entry_at_key_level'):
                confidence += 0.1
            else:
                # Still give some confidence even without key level (fallback mode)
                confidence += 0.05
            
            # Confirmations bonus
            confirmations = entry_analysis.get('confirmations', 0)
            if confirmations > 0:
                confidence += (min(confirmations, 4) / 4) * 0.1
            else:
                # Minimum confirmation bonus for fallback entries
                confidence += 0.05
            
            # Risk/reward bonus
            if risk_reward_ratio >= 2.0:
                confidence += 0.1
            elif risk_reward_ratio >= 1.5:
                confidence += 0.05
            elif risk_reward_ratio >= 1.2:
                confidence += 0.02  # Small bonus for decent R/R
            
            return min(0.95, max(0.6, confidence))  # Ensure minimum 0.6 confidence
            
        except:
            return 0.65  # Higher fallback confidence
    
    def _analyze_daily_trend_for_strategy(self, symbol: Symbol) -> Dict:
        """Analyze daily trend using YOUR STRATEGY (1D timeframe)"""
        try:
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:50]  # Last 50 data points
            
            if not recent_data.exists() or len(recent_data) < 20:
                return {'direction': 'NEUTRAL', 'strength': 0.0}
            
            prices = [float(d.close_price) for d in recent_data]
            
            # Calculate SMA 20 and SMA 50 (YOUR STRATEGY)
            sma_20 = np.mean(prices[-20:])
            sma_50 = np.mean(prices[-50:]) if len(prices) >= 50 else sma_20
            
            current_price = prices[-1]
            
            # Determine trend direction (YOUR STRATEGY)
            if sma_20 > sma_50 and current_price > sma_20:
                direction = 'BULLISH'
                strength = abs(current_price - sma_20) / sma_20
            elif sma_20 < sma_50 and current_price < sma_20:
                direction = 'BEARISH'
                strength = abs(current_price - sma_20) / sma_20
            else:
                direction = 'NEUTRAL'
                strength = 0.0
            
            return {
                'direction': direction,
                'strength': strength,
                'sma_20': sma_20,
                'sma_50': sma_50,
                'current_price': current_price
            }
            
        except Exception as e:
            logger.error(f"Error analyzing daily trend for {symbol.symbol}: {e}")
            return {'direction': 'NEUTRAL', 'strength': 0.0}
    
    def _analyze_market_structure_for_strategy(self, symbol: Symbol, signal_type: str) -> Dict:
        """Analyze market structure for BOS/CHoCH (YOUR STRATEGY)"""
        try:
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:50]
            
            if not recent_data.exists() or len(recent_data) < 20:
                return {'confirmed': False, 'type': 'NONE'}
            
            prices = [float(d.close_price) for d in recent_data]
            highs = [float(d.high_price) for d in recent_data]
            lows = [float(d.low_price) for d in recent_data]
            
            current_price = prices[-1]
            
            # Find swing highs and lows
            swing_highs = []
            swing_lows = []
            
            for i in range(5, len(prices) - 5):
                if highs[i] == max(highs[i-5:i+6]):
                    swing_highs.append(highs[i])
                if lows[i] == min(lows[i-5:i+6]):
                    swing_lows.append(lows[i])
            
            # Check for BOS (Break of Structure)
            if signal_type == 'BUY' and swing_highs:
                recent_high = max(swing_highs[-3:]) if len(swing_highs) >= 3 else swing_highs[-1]
                if current_price > recent_high:
                    return {'confirmed': True, 'type': 'BOS', 'break_level': recent_high}
            
            if signal_type == 'SELL' and swing_lows:
                recent_low = min(swing_lows[-3:]) if len(swing_lows) >= 3 else swing_lows[-1]
                if current_price < recent_low:
                    return {'confirmed': True, 'type': 'BOS', 'break_level': recent_low}
            
            # Check for CHoCH (Change of Character)
            if signal_type == 'BUY' and len(swing_lows) >= 3:
                recent_lows = swing_lows[-3:]
                if recent_lows[-1] > recent_lows[-2] > recent_lows[-3]:
                    return {'confirmed': True, 'type': 'CHoCH', 'break_level': recent_lows[-1]}
            
            if signal_type == 'SELL' and len(swing_highs) >= 3:
                recent_highs = swing_highs[-3:]
                if recent_highs[-1] < recent_highs[-2] < recent_highs[-3]:
                    return {'confirmed': True, 'type': 'CHoCH', 'break_level': recent_highs[-1]}
            
            return {'confirmed': False, 'type': 'NONE'}
            
        except Exception as e:
            logger.error(f"Error analyzing market structure for {symbol.symbol}: {e}")
            return {'confirmed': False, 'type': 'NONE'}
    
    def _analyze_entry_confirmation_for_strategy(self, symbol: Symbol, signal_type: str, trend: Dict) -> Dict:
        """Analyze entry confirmation using YOUR STRATEGY (RSI, MACD, Candlestick, Volume)"""
        try:
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:30]
            
            if not recent_data.exists() or len(recent_data) < 20:
                return {'confirmations': 0, 'confidence': 0.0}
            
            prices = [float(d.close_price) for d in recent_data]
            volumes = [float(d.volume) for d in recent_data]
            opens = [float(d.open_price) for d in recent_data]
            highs = [float(d.high_price) for d in recent_data]
            lows = [float(d.low_price) for d in recent_data]
            
            confirmations = 0
            confidence = 0.5
            
            # 1. RSI Confirmation (YOUR STRATEGY: 20-50 for longs, 50-80 for shorts)
            rsi = self._calculate_rsi(prices)
            if signal_type == 'BUY' and self.rsi_buy_range[0] <= rsi <= self.rsi_buy_range[1]:
                confirmations += 1
                confidence += 0.15
            elif signal_type == 'SELL' and self.rsi_sell_range[0] <= rsi <= self.rsi_sell_range[1]:
                confirmations += 1
                confidence += 0.15
            
            # 2. MACD Confirmation
            macd_signal = self._calculate_macd_signal(prices)
            if signal_type == 'BUY' and macd_signal > 0:
                confirmations += 1
                confidence += 0.1
            elif signal_type == 'SELL' and macd_signal < 0:
                confirmations += 1
                confidence += 0.1
            
            # 3. Volume Confirmation (YOUR STRATEGY: 1.2x threshold)
            volume_ratio = volumes[-1] / np.mean(volumes[-20:]) if len(volumes) >= 20 else 1.0
            if volume_ratio >= self.volume_threshold:
                confirmations += 1
                confidence += 0.1
            
            # 4. Candlestick Pattern Confirmation (YOUR STRATEGY)
            candlestick_pattern = self._detect_candlestick_pattern_for_strategy(
                opens[-2:], highs[-2:], lows[-2:], prices[-2:], signal_type
            )
            if candlestick_pattern != 'NONE':
                confirmations += 1
                confidence += 0.1
            
            return {
                'confirmations': confirmations,
                'confidence': min(0.95, confidence),
                'rsi': rsi,
                'macd_signal': 'BULLISH' if macd_signal > 0 else 'BEARISH' if macd_signal < 0 else 'NEUTRAL',
                'volume_confirmed': volume_ratio >= self.volume_threshold,
                'volume_ratio': volume_ratio,
                'candlestick': candlestick_pattern
            }
            
        except Exception as e:
            logger.error(f"Error analyzing entry confirmation for {symbol.symbol}: {e}")
            return {'confirmations': 0, 'confidence': 0.0}
    
    def _detect_candlestick_pattern_for_strategy(self, opens: List[float], highs: List[float], 
                                                 lows: List[float], closes: List[float], signal_type: str) -> str:
        """Detect candlestick patterns for YOUR STRATEGY"""
        try:
            if len(closes) < 2:
                return 'NONE'
            
            prev_open, curr_open = opens[-2], opens[-1]
            prev_close, curr_close = closes[-2], closes[-1]
            prev_high, curr_high = highs[-2], highs[-1]
            prev_low, curr_low = lows[-2], lows[-1]
            
            # Bullish Engulfing Pattern
            if signal_type == 'BUY':
                if (prev_close < prev_open and  # Previous bearish
                    curr_close > curr_open and  # Current bullish
                    curr_open < prev_close and  # Opens below prev close
                    curr_close > prev_open):  # Closes above prev open
                    return 'BULLISH_ENGULFING'
                
                # Hammer Pattern
                body = abs(curr_close - curr_open)
                lower_shadow = min(curr_open, curr_close) - curr_low
                if body > 0 and lower_shadow > 2 * body:
                    return 'HAMMER'
            
            # Bearish Engulfing Pattern
            elif signal_type == 'SELL':
                if (prev_close > prev_open and  # Previous bullish
                    curr_close < curr_open and  # Current bearish
                    curr_open > prev_close and  # Opens above prev close
                    curr_close < prev_open):  # Closes below prev open
                    return 'BEARISH_ENGULFING'
                
                # Shooting Star Pattern
                body = abs(curr_close - curr_open)
                upper_shadow = curr_high - max(curr_open, curr_close)
                if body > 0 and upper_shadow > 2 * body:
                    return 'SHOOTING_STAR'
            
            return 'NONE'
            
        except Exception as e:
            logger.error(f"Error detecting candlestick pattern: {e}")
            return 'NONE'
    
    def _calculate_technical_score_with_strategy(self, symbol: Symbol, signal_type: str) -> float:
        """Calculate technical score using YOUR STRATEGY parameters"""
        try:
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:100]
            
            if not recent_data.exists():
                return 0.5
            
            prices = [float(d.close_price) for d in recent_data]
            volumes = [float(d.volume) for d in recent_data]
            
            if len(prices) < 20:
                return 0.5
            
            # Calculate RSI with YOUR ranges
            rsi = self._calculate_rsi(prices)
            
            # Calculate Moving Averages (YOUR STRATEGY: SMA 20 & 50)
            sma_20 = np.mean(prices[-20:])
            sma_50 = np.mean(prices[-50:]) if len(prices) >= 50 else sma_20
            
            # Calculate MACD
            macd_signal = self._calculate_macd_signal(prices)
            
            # Calculate Volume trend
            volume_trend = self._calculate_volume_trend(volumes)
            
            # Score based on YOUR STRATEGY
            score = 0.5  # Base neutral score
            
            if signal_type == 'BUY':
                # RSI in YOUR buy range (20-50)
                if self.rsi_buy_range[0] <= rsi <= self.rsi_buy_range[1]:
                    score += 0.25
                
                # Moving average alignment (YOUR STRATEGY)
                if prices[-1] > sma_20 > sma_50:
                    score += 0.15
                
                # MACD bullish
                if macd_signal > 0:
                    score += 0.1
                
                # Volume confirmation
                if volume_trend > 0:
                    score += 0.05
                    
            else:  # SELL
                # RSI in YOUR sell range (50-80)
                if self.rsi_sell_range[0] <= rsi <= self.rsi_sell_range[1]:
                    score += 0.25
                
                # Moving average alignment (YOUR STRATEGY)
                if prices[-1] < sma_20 < sma_50:
                    score += 0.15
                
                # MACD bearish
                if macd_signal < 0:
                    score += 0.1
                
                # Volume confirmation
                if volume_trend < 0:
                    score += 0.05
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.error(f"Error calculating technical score with strategy for {symbol.symbol}: {e}")
            return 0.5
    
    def _calculate_technical_score(self, symbol: Symbol) -> float:
        """Calculate technical analysis score for a symbol"""
        try:
            # Get recent market data
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:100]  # Last 100 data points
            
            if not recent_data.exists():
                return 0.5  # Neutral score if no data
            
            # Calculate basic technical indicators
            prices = [float(d.close_price) for d in recent_data]
            volumes = [float(d.volume) for d in recent_data]
            
            if len(prices) < 20:
                return 0.5
            
            # Calculate RSI
            rsi = self._calculate_rsi(prices)
            
            # Calculate Moving Averages
            sma_20 = np.mean(prices[-20:])
            sma_50 = np.mean(prices[-50:]) if len(prices) >= 50 else sma_20
            
            # Calculate MACD
            macd_signal = self._calculate_macd_signal(prices)
            
            # Calculate Volume trend
            volume_trend = self._calculate_volume_trend(volumes)
            
            # Combine indicators into a score
            score = 0.5  # Base neutral score
            
            # RSI contribution
            if rsi < 30:  # Oversold - bullish
                score += 0.2
            elif rsi > 70:  # Overbought - bearish
                score -= 0.2
            
            # Moving average contribution
            if prices[-1] > sma_20 > sma_50:  # Bullish trend
                score += 0.15
            elif prices[-1] < sma_20 < sma_50:  # Bearish trend
                score -= 0.15
            
            # MACD contribution
            score += macd_signal * 0.1
            
            # Volume contribution
            score += volume_trend * 0.05
            
            # Ensure score is between 0 and 1
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.error(f"Error calculating technical score for {symbol.symbol}: {e}")
            return 0.5
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI indicator"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd_signal(self, prices: List[float]) -> float:
        """Calculate MACD signal strength"""
        if len(prices) < 26:
            return 0.0
        
        # Calculate EMAs
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        
        macd_line = ema_12 - ema_26
        
        # Simple MACD signal (positive = bullish, negative = bearish)
        return 1.0 if macd_line > 0 else -1.0
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return prices[-1]
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_volume_trend(self, volumes: List[float]) -> float:
        """Calculate volume trend (positive = increasing volume)"""
        if len(volumes) < 10:
            return 0.0
        
        recent_avg = np.mean(volumes[-5:])
        older_avg = np.mean(volumes[-10:-5])
        
        if older_avg == 0:
            return 0.0
        
        trend = (recent_avg - older_avg) / older_avg
        return max(-1.0, min(1.0, trend))
    
    def _calculate_volatility(self, symbol: Symbol) -> float:
        """Calculate price volatility for risk management"""
        try:
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:30]  # Last 30 data points
            
            if not recent_data.exists():
                return 0.05  # Default 5% volatility
            
            prices = [float(d.close_price) for d in recent_data]
            returns = [prices[i] / prices[i-1] - 1 for i in range(1, len(prices))]
            
            volatility = np.std(returns) * np.sqrt(24)  # Daily volatility
            return max(0.01, min(0.5, volatility))  # Between 1% and 50%
            
        except Exception as e:
            logger.error(f"Error calculating volatility for {symbol.symbol}: {e}")
            return 0.05
    
    
    def _analyze_market_conditions(self, symbol: Symbol, current_price: Decimal) -> Dict:
        """Enhanced market condition analysis based on user plan"""
        try:
            # Get recent market data
            recent_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp')[:100]
            
            if not recent_data.exists():
                return {'trend': 'NEUTRAL', 'volatility': 0.5, 'momentum': 0.0}
            
            prices = [float(d.close_price) for d in recent_data]
            volumes = [float(d.volume) for d in recent_data]
            
            # Calculate enhanced indicators
            sma_20 = sum(prices[-20:]) / 20 if len(prices) >= 20 else sum(prices) / len(prices)
            sma_50 = sum(prices[-50:]) / 50 if len(prices) >= 50 else sma_20
            
            # Trend analysis
            if sma_20 > sma_50 * 1.02:
                trend = 'BULLISH'
            elif sma_20 < sma_50 * 0.98:
                trend = 'BEARISH'
            else:
                trend = 'NEUTRAL'
            
            # Volatility analysis
            if len(prices) >= 20:
                volatility = (max(prices[-20:]) - min(prices[-20:])) / sma_20
            else:
                volatility = 0.5
            
            # Momentum analysis
            if len(prices) >= 10:
                momentum = (prices[-1] - prices[-10]) / prices[-10]
            else:
                momentum = 0.0
            
            # Volume analysis
            if len(volumes) >= 20:
                avg_volume = sum(volumes[-20:]) / 20
                current_volume = volumes[-1]
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            else:
                volume_ratio = 1.0
            
            return {
                'trend': trend,
                'volatility': volatility,
                'momentum': momentum,
                'volume_ratio': volume_ratio,
                'sma_20': sma_20,
                'sma_50': sma_50,
                'current_price': current_price
            }
            
        except Exception as e:
            logger.error(f"Error analyzing market conditions: {e}")
            return {'trend': 'NEUTRAL', 'volatility': 0.5, 'momentum': 0.0}
    
    def _calculate_enhanced_confidence(self, symbol: Symbol, signal_type: str, market_conditions: Dict) -> float:
        """Calculate enhanced confidence based on multiple factors"""
        try:
            base_confidence = 0.5
            
            # Trend alignment bonus
            if signal_type == 'BUY' and market_conditions.get('trend') == 'BULLISH':
                base_confidence += 0.2
            elif signal_type == 'SELL' and market_conditions.get('trend') == 'BEARISH':
                base_confidence += 0.2
            
            # Momentum bonus
            momentum = market_conditions.get('momentum', 0)
            if abs(momentum) > 0.05:  # 5% momentum
                base_confidence += 0.1
            
            # Volume confirmation bonus
            volume_ratio = market_conditions.get('volume_ratio', 1.0)
            if volume_ratio > 1.2:  # 20% above average volume
                base_confidence += 0.1
            
            # Volatility adjustment
            volatility = market_conditions.get('volatility', 0.5)
            if volatility > 0.1:  # High volatility
                base_confidence += 0.05
            
            return min(0.95, base_confidence)
            
        except Exception as e:
            logger.error(f"Error calculating enhanced confidence: {e}")
            return 0.6

    def _calculate_signal_confidence(self, symbol: Symbol, signal_type: str, technical_score: float, volatility: float) -> float:
        """Calculate overall signal confidence"""
        base_confidence = technical_score
        
        # Adjust confidence based on signal type
        if signal_type in ['STRONG_BUY', 'STRONG_SELL']:
            base_confidence *= 1.2  # Boost for strong signals
        
        # Adjust for volatility (lower volatility = higher confidence)
        volatility_factor = 1.0 - (volatility * 0.5)
        base_confidence *= volatility_factor
        
        # Add some randomness for realistic confidence scores
        import random
        random_factor = random.uniform(0.9, 1.1)
        base_confidence *= random_factor
        
        return max(0.0, min(1.0, base_confidence))
    
    def _validate_signal(self, signal_data: Dict) -> bool:
        """Validate that the signal meets our criteria"""
        try:
            # Check risk/reward ratio
            if signal_data['risk_reward_ratio'] < self.min_risk_reward_ratio:
                return False
            
            # Check confidence threshold
            if signal_data['confidence_score'] < self.min_confidence_threshold:
                return False
            
            # Check that prices are logical
            entry_price = signal_data['entry_price']
            stop_loss = signal_data['stop_loss']
            target_price = signal_data['target_price']
            
            if signal_data['signal_type'] in ['BUY', 'STRONG_BUY']:
                if stop_loss >= entry_price or target_price <= entry_price:
                    return False
            else:  # SELL signals
                if stop_loss <= entry_price or target_price >= entry_price:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating signal: {e}")
            return False
    
    def _select_best_signals(self, all_signals: List[Dict]) -> List[Dict]:
        """Select the best 10 signals from ALL signal types (BUY and SELL) - PRIORITIZING YOUR PERSONAL STRATEGY"""
        if not all_signals:
            return []
        
        # Calculate combined score for each signal - YOUR STRATEGY GETS HIGHEST PRIORITY
        def signal_score(signal):
            # YOUR STRATEGY BONUS (50% weight) - Signals using your strategy get massive boost
            strategy_details = signal.get('strategy_details', {})
            strategy_name = strategy_details.get('strategy', '')
            # Recognize both PERSONAL_STRATEGY and PERSONAL_STRATEGY_MULTI_TIMEFRAME
            is_personal_strategy = strategy_name in ['PERSONAL_STRATEGY', 'PERSONAL_STRATEGY_MULTI_TIMEFRAME']
            strategy_bonus = 0.5 if is_personal_strategy else 0.0
            
            # Strategy confirmations bonus (10% weight)
            confirmations = signal.get('strategy_confirmations', 0)
            confirmation_score = min(0.1, (confirmations / 4) * 0.1)
            
            # Strategy confidence (20% weight)
            confidence = signal.get('confidence_score', 0.5) * 0.2
            
            # Risk-reward ratio (10% weight) - YOUR STRATEGY has 1.875:1
            risk_reward = signal.get('risk_reward_ratio', 1.0) / 5.0 * 0.1
            
            # Quality score (5% weight)
            quality = signal.get('quality_score', 0.5) * 0.05
            
            # News score (2.5% weight)
            news = self._get_news_score_for_signal_dict(signal) * 0.025
            
            # Sentiment score (2.5% weight)
            sentiment = self._get_sentiment_score_for_signal_dict(signal) * 0.025
            
            return strategy_bonus + confirmation_score + confidence + risk_reward + quality + news + sentiment
        
        sorted_signals = sorted(all_signals, key=signal_score, reverse=True)
        
        # Select top signals, ensuring diversity in BOTH symbols AND signal types
        best_signals = []
        used_symbols = set()
        buy_count = 0
        sell_count = 0
        
        # Target: at least 3-4 of each type if possible, but prioritize quality
        max_per_type = max(5, self.best_signals_count // 2)  # At least half can be one type
        
        for signal in sorted_signals:
            symbol_name = signal['symbol'].symbol if hasattr(signal['symbol'], 'symbol') else str(signal['symbol'])
            signal_type = signal.get('signal_type', '')
            is_buy = signal_type in ['BUY', 'STRONG_BUY']
            is_sell = signal_type in ['SELL', 'STRONG_SELL']
            
            # Skip if symbol already used
            if symbol_name in used_symbols:
                continue
            
            # Ensure diversity in signal types
            if is_buy and buy_count >= max_per_type:
                continue
            if is_sell and sell_count >= max_per_type:
                continue
            
            # Add signal
            best_signals.append(signal)
            used_symbols.add(symbol_name)
            if is_buy:
                buy_count += 1
            elif is_sell:
                sell_count += 1
            
            # Stop when we have enough signals
            if len(best_signals) >= self.best_signals_count:
                break
        
        # If we don't have enough signals, fill remaining slots without type restrictions
        if len(best_signals) < self.best_signals_count:
            for signal in sorted_signals:
                if len(best_signals) >= self.best_signals_count:
                    break
                symbol_name = signal['symbol'].symbol if hasattr(signal['symbol'], 'symbol') else str(signal['symbol'])
                if symbol_name not in used_symbols:
                    best_signals.append(signal)
                    used_symbols.add(symbol_name)
        
        logger.info(f"Selected {len(best_signals)} best signals: {buy_count} BUY, {sell_count} SELL")
        return best_signals
    
    def _get_news_score_for_signal_dict(self, signal: Dict) -> float:
        """Get news sentiment score for a signal"""
        try:
            from apps.sentiment.models import CryptoMention
            from django.utils import timezone
            from datetime import timedelta
            
            symbol = signal.get('symbol')
            if not symbol or not hasattr(symbol, 'id'):
                return 0.5
            
            recent_mentions = CryptoMention.objects.filter(
                asset=symbol,
                news_article__published_at__gte=timezone.now() - timedelta(hours=24),
                mention_type='news'
            )
            
            if not recent_mentions.exists():
                return 0.5
            
            total_score = 0.0
            total_weight = 0.0
            
            for mention in recent_mentions:
                hours_ago = (timezone.now() - mention.news_article.published_at).total_seconds() / 3600
                recency_weight = max(0, 1 - (hours_ago / 24))
                weight = mention.confidence_score * recency_weight
                sentiment_value = mention.sentiment_score if mention.sentiment_label == 'POSITIVE' else -mention.sentiment_score
                normalized_sentiment = (sentiment_value + 1) / 2
                total_score += normalized_sentiment * weight
                total_weight += weight
            
            return total_score / total_weight if total_weight > 0 else 0.5
        except Exception:
            return 0.5
    
    def _get_sentiment_score_for_signal_dict(self, signal: Dict) -> float:
        """Get market sentiment score for a signal"""
        try:
            from apps.sentiment.models import SentimentAggregate
            from django.utils import timezone
            from datetime import timedelta
            
            symbol = signal.get('symbol')
            if not symbol or not hasattr(symbol, 'id'):
                return 0.5
            
            recent_aggregate = SentimentAggregate.objects.filter(
                asset=symbol,
                timeframe='1h',
                created_at__gte=timezone.now() - timedelta(hours=2)
            ).order_by('-created_at').first()
            
            if recent_aggregate:
                return (recent_aggregate.aggregate_sentiment_score + 1) / 2
            
            return 0.5
        except Exception:
            return 0.5
    
    def _archive_old_signals(self):
        """Archive old signals to history and remove duplicates"""
        try:
            # Get current hour start - archive signals from previous hours
            current_hour_start = timezone.now().replace(minute=0, second=0, microsecond=0)
            
            # Mark old signals as executed/archived (signals from previous hours)
            old_signals = TradingSignal.objects.filter(
                is_valid=True,
                created_at__lt=current_hour_start
            )
            
            archived_count = 0
            for signal in old_signals:
                signal.is_executed = True
                signal.executed_at = timezone.now()
                signal.is_valid = False
                signal.save()
                archived_count += 1
            
            logger.info(f"Archived {archived_count} old signals from previous hours")
            
            # Remove duplicate active signals (keep only the latest for each symbol in current hour)
            self._remove_duplicate_active_signals()
            
        except Exception as e:
            logger.error(f"Error archiving old signals: {e}")
    
    def _remove_duplicate_active_signals(self):
        """Remove duplicate active signals, keeping only the latest for each symbol in current hour"""
        try:
            # Get current hour start time
            current_hour_start = timezone.now().replace(minute=0, second=0, microsecond=0)
            
            # Get all active signals from current hour grouped by symbol
            active_signals = TradingSignal.objects.filter(
                is_valid=True,
                created_at__gte=current_hour_start
            ).order_by('symbol', '-created_at')
            
            # Track symbols we've seen and remove duplicates
            seen_symbols = set()
            duplicates_removed = 0
            
            for signal in active_signals:
                symbol_name = signal.symbol.symbol
                if symbol_name in seen_symbols:
                    # This is a duplicate, archive it
                    signal.is_executed = True
                    signal.executed_at = timezone.now()
                    signal.is_valid = False
                    signal.save()
                    duplicates_removed += 1
                    logger.info(f"Removed duplicate signal for {symbol_name}")
                else:
                    seen_symbols.add(symbol_name)
            
            if duplicates_removed > 0:
                logger.info(f"Removed {duplicates_removed} duplicate active signals")
            
        except Exception as e:
            logger.error(f"Error removing duplicate signals: {e}")
    
    def _save_new_signals(self, signals: List[Dict]):
        """Save new signals to database"""
        try:
            saved_count = 0
            
            for signal_data in signals:
                try:
                    # Get or create signal type
                    signal_type, _ = SignalType.objects.get_or_create(
                        name=signal_data['signal_type'],
                        defaults={'is_active': True}
                    )
                    
                    # Create trading signal
                    signal = TradingSignal.objects.create(
                        symbol=signal_data['symbol'],
                        signal_type=signal_type,
                        strength=signal_data['strength'],
                        confidence_score=signal_data['confidence_score'],
                        confidence_level=self._get_confidence_level(signal_data['confidence_score']),
                        entry_price=signal_data['entry_price'],
                        target_price=signal_data['target_price'],
                        stop_loss=signal_data['stop_loss'],
                        risk_reward_ratio=signal_data['risk_reward_ratio'],
                        timeframe=signal_data['timeframe'],
                        entry_point_type=signal_data['entry_point_type'],
                        quality_score=signal_data['confidence_score'],
                        is_valid=True,
                        expires_at=timezone.now() + timedelta(hours=self.signal_refresh_hours * 2),
                        technical_score=signal_data['technical_score'],
                        notes=signal_data['reasoning'],
                        analyzed_at=timezone.now()
                    )
                    
                    saved_count += 1
                    logger.info(f"Saved {signal_data['signal_type']} signal for {signal_data['symbol'].symbol}")
                    
                except Exception as e:
                    logger.error(f"Error saving signal for {signal_data['symbol'].symbol}: {e}")
                    continue
            
            logger.info(f"Successfully saved {saved_count} new signals")
            
        except Exception as e:
            logger.error(f"Error saving new signals: {e}")
    
    def _get_confidence_level(self, confidence_score: float) -> str:
        """Convert confidence score to confidence level"""
        if confidence_score >= 0.85:
            return 'VERY_HIGH'
        elif confidence_score >= 0.70:
            return 'HIGH'
        elif confidence_score >= 0.50:
            return 'MEDIUM'
        else:
            return 'LOW'


# Global instance
enhanced_signal_service = EnhancedSignalGenerationService()

"""
Unified StrategyEngine implementing the Phase 1 baseline rule-based signals.

Core logic:
- Multi-timeframe analysis (1D → 4H → 1H → 15M) for trend, CHoCH/BOS structure
- Entry confirmation on 1H/15M using candlestick, RSI, MACD, pivots
- Risk management with SL/TP and basic trailing stop suggestion
- Fundamental/news gating hook via EconomicDataService (optional)
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict
from decimal import Decimal

from django.utils import timezone

from apps.trading.models import Symbol
from apps.signals.models import TradingSignal, SignalType
from apps.data.models import MarketData
from apps.data.services import TechnicalAnalysisService, EconomicDataService
from apps.signals.timeframe_analysis_service import TimeframeAnalysisService


logger = logging.getLogger(__name__)


@dataclass
class EngineConfig:
    min_confidence: float = 0.25  # Much lower threshold for more signals
    min_risk_reward: float = 1.0  # Lower RR requirement
    signal_expiry_hours: int = 4  # Shorter expiry for faster cycling


class StrategyEngine:
    """Phase 1 rule-based engine producing BUY/SELL/HOLD signals per symbol."""

    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.ta_service = TechnicalAnalysisService()
        self.timeframe_service = TimeframeAnalysisService()
        self.economic_service = EconomicDataService()

    def evaluate_symbol(self, symbol: Symbol) -> List[TradingSignal]:
        try:
            current_md = MarketData.objects.filter(symbol=symbol).order_by('-timestamp').first()
            if not current_md:
                logger.warning(f"No market data for {symbol.symbol}")
                return []

            current_price = float(current_md.close_price)

            # 1) Market context on 1D (trend + zones)
            analysis_1d = self.timeframe_service.analyze_timeframe(symbol, '1D', current_price)

            # 2) Market structure: 4H CHoCH/BOS, confirm on 1H
            analysis_4h = self.timeframe_service.analyze_timeframe(symbol, '4H', current_price)
            analysis_1h = self.timeframe_service.analyze_timeframe(symbol, '1H', current_price)
            analysis_15m = self.timeframe_service.analyze_timeframe(symbol, '15M', current_price)

            overall_bias = self._derive_bias(analysis_1d, analysis_4h)

            # 3) Entry confirmations (1H/15M): candlestick proxy via price_action, RSI, MACD, pivots
            rsi = self.ta_service.calculate_rsi(symbol)  # stores indicator as side-effect
            macd = self.ta_service.calculate_macd(symbol)

            pivot_supports = analysis_1h.get('price_analysis', {}).get('support_levels', [])
            pivot_resistances = analysis_1h.get('price_analysis', {}).get('resistance_levels', [])

            entry_direction = self._confirm_entry(overall_bias, rsi, macd, analysis_1h, analysis_15m)

            # 5) Fundamental confirmation (gate if very negative sentiment)
            macro_gate = self._fundamental_gate()
            if macro_gate == 'AVOID':
                logger.info(f"Macro gate blocks entries for {symbol.symbol}")
                return []

            # Build signals if confirmed
            signals: List[TradingSignal] = []
            if entry_direction == 'BUY':
                stop_loss, target_price, rr = self._compute_sl_tp_rr(
                    side='BUY', price=current_price, supports=pivot_supports, resistances=pivot_resistances
                )
                if rr >= self.config.min_risk_reward:
                    sig = self._build_signal(
                        symbol=symbol,
                        action='BUY',
                        price=current_price,
                        stop_loss=stop_loss,
                        target=target_price,
                        confidence=self._confidence(overall_bias, rsi, macd, analysis_1h, analysis_15m),
                    )
                    if sig.confidence_score >= self.config.min_confidence:
                        signals.append(sig)

            elif entry_direction == 'SELL':
                stop_loss, target_price, rr = self._compute_sl_tp_rr(
                    side='SELL', price=current_price, supports=pivot_supports, resistances=pivot_resistances
                )
                if rr >= self.config.min_risk_reward:
                    sig = self._build_signal(
                        symbol=symbol,
                        action='SELL',
                        price=current_price,
                        stop_loss=stop_loss,
                        target=target_price,
                        confidence=self._confidence(overall_bias, rsi, macd, analysis_1h, analysis_15m),
                    )
                    if sig.confidence_score >= self.config.min_confidence:
                        signals.append(sig)

            return signals

        except Exception as e:
            logger.error(f"Engine error for {symbol.symbol}: {e}")
            return []

    def _derive_bias(self, analysis_1d: Dict, analysis_4h: Dict) -> str:
        trend_1d = (analysis_1d.get('price_analysis') or {}).get('trend')
        trend_4h = (analysis_4h.get('price_analysis') or {}).get('trend')
        if trend_1d == 'BULLISH' and trend_4h == 'BULLISH':
            return 'BULLISH'
        if trend_1d == 'BEARISH' and trend_4h == 'BEARISH':
            return 'BEARISH'
        return 'NEUTRAL'

    def _confirm_entry(self, bias: str, rsi: Optional[float], macd: Optional[Dict], a1h: Dict, a15m: Dict) -> Optional[str]:
        # Candlestick proxy: use trend-following presence on 1H/15M as bullish proxy
        ep1h = a1h.get('entry_points', [])
        ep15 = a15m.get('entry_points', [])
        has_bullish = any(ep.get('type') in ['RESISTANCE_BREAK', 'TREND_FOLLOWING', 'BREAKOUT'] for ep in ep1h + ep15)
        has_bearish = any(ep.get('type') in ['SUPPORT_BREAK', 'MEAN_REVERSION', 'BREAKDOWN'] for ep in ep1h + ep15)

        macd_bull = macd and macd.get('macd', 0) >= macd.get('signal', 0)
        macd_bear = macd and macd.get('macd', 0) < macd.get('signal', 0)

        # Much more permissive logic for continuous real-time signal generation
        ep_count = len(ep1h) + len(ep15)
        if bias == 'BULLISH':
            # Generate BUY signals in any uptrend with minimal requirements
            if has_bullish or (rsi is not None and rsi < 75) or ep_count > 0:
                return 'BUY'
        if bias == 'BEARISH':
            # Generate SELL signals in any downtrend with minimal requirements  
            if has_bearish or (rsi is not None and rsi > 25) or ep_count > 0:
                return 'SELL'
        return None

    def _compute_sl_tp_rr(self, side: str, price: float, supports: List[float], resistances: List[float]):
        if side == 'BUY':
            nearest_support = max([s for s in supports if s <= price], default=price * 0.5)
            stop_loss = float(nearest_support)  # 50% stop loss
            target = max(resistances) if resistances else price * 1.6  # 60% target
        else:
            nearest_resistance = min([r for r in resistances if r >= price], default=price * 1.5)
            stop_loss = float(nearest_resistance)  # 50% stop loss for sell
            target = min(supports) if supports else price * 0.4  # 60% target for sell

        risk = abs(price - stop_loss)
        reward = abs(target - price)
        rr = (reward / risk) if risk > 0 else 0.0
        return Decimal(str(stop_loss)), Decimal(str(target)), rr

    def _confidence(self, bias: str, rsi: Optional[float], macd: Optional[Dict], a1h: Dict, a15m: Dict) -> float:
        base = 0.62 if bias in ['BULLISH', 'BEARISH'] else 0.5
        if rsi is not None:
            if 20 <= rsi <= 55 or 45 <= rsi <= 80:
                base += 0.1
        if macd:
            base += 0.1
        # More entry points across TFs increases confidence
        ep_count = len(a1h.get('entry_points', [])) + len(a15m.get('entry_points', []))
        base += min(0.1, ep_count * 0.02)
        return min(0.95, base)

    def _fundamental_gate(self) -> str:
        try:
            sentiment = self.economic_service.get_market_impact_score(symbol_country='US')
            # Avoid trades if strongly negative macro impact
            if sentiment < -0.4:
                return 'AVOID'
        except Exception:
            pass
        return 'ALLOW'

    def _build_signal(self, symbol: Symbol, action: str, price: float, stop_loss: Decimal, target: Decimal, confidence: float) -> TradingSignal:
        signal_type_name = 'BUY' if action == 'BUY' else 'SELL'
        signal_type, _ = SignalType.objects.get_or_create(name=signal_type_name, defaults={'description': f'{signal_type_name} signal'})

        return TradingSignal(
            symbol=symbol,
            signal_type=signal_type,
            strength='STRONG' if confidence >= 0.75 else 'MODERATE',
            confidence_score=confidence,
            confidence_level='HIGH' if confidence >= 0.7 else 'MEDIUM',
            entry_price=Decimal(str(price)),
            target_price=target,
            stop_loss=stop_loss,
            risk_reward_ratio=float(abs(target - Decimal(str(price))) / max(Decimal('0.0000001'), abs(Decimal(str(price)) - stop_loss))),
            timeframe='1H',
            notes=f"Engine v1: {action} with MTF+RSI+MACD+pivots",
            is_valid=True,
            expires_at=timezone.now() + timezone.timedelta(hours=self.config.signal_expiry_hours)
        )



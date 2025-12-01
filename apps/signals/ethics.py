"""
Ethical and logical validation utilities for trading signals.

Rejects signals that are logically impossible or misleading, such as
invalid price relationships, extreme/unbounded risk profiles, or
non-sensical values that could harm users.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Tuple, Optional


@dataclass
class EthicsCheckResult:
    is_ethical: bool
    issues: List[str]


def _to_decimal(value: Optional[Decimal | float | int | str]) -> Optional[Decimal]:
    try:
        if value is None:
            return None
        return Decimal(str(value))
    except Exception:
        return None


def compute_risk_reward_ratio(entry: Decimal, target: Decimal, stop: Decimal, signal_type: str) -> Optional[float]:
    try:
        entry_d = _to_decimal(entry)
        target_d = _to_decimal(target)
        stop_d = _to_decimal(stop)
        if entry_d is None or target_d is None or stop_d is None:
            return None
        if signal_type in ["BUY", "STRONG_BUY"]:
            reward = abs(target_d - entry_d)
            risk = abs(entry_d - stop_d)
        else:
            reward = abs(entry_d - target_d)
            risk = abs(stop_d - entry_d)
        if risk <= 0:
            return None
        return float(reward / risk)
    except Exception:
        return None


def validate_signal_prices(entry: Decimal, target: Decimal, stop: Decimal, signal_type: str) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    e = _to_decimal(entry)
    t = _to_decimal(target)
    s = _to_decimal(stop)

    if e is None or t is None or s is None:
        issues.append("Missing price fields")
        return False, issues

    if e <= 0 or t <= 0 or s <= 0:
        issues.append("Non-positive price values")
        return False, issues

    if signal_type in ["BUY", "STRONG_BUY"]:
        if not (t > e > s):
            issues.append("BUY signal must satisfy target > entry > stop")
            return False, issues
    else:
        if not (s > e > t):
            issues.append("SELL signal must satisfy stop > entry > target")
            return False, issues

    # Basic sanity: prevent absurd returns in one hop
    # e.g., > 10x target or > 80% stop from entry is flagged
    max_gain_multiple = Decimal("10")
    max_loss_pct = Decimal("0.80")
    if signal_type in ["BUY", "STRONG_BUY"]:
        if t / e > max_gain_multiple:
            issues.append("Target implies >10x move, unrealistic")
    else:
        if e / t > max_gain_multiple:
            issues.append("Target implies >10x move, unrealistic")

    if signal_type in ["BUY", "STRONG_BUY"]:
        if (e - s) / e > max_loss_pct:
            issues.append("Stop implies >80% loss, unethical risk")
    else:
        if (s - e) / e > max_loss_pct:
            issues.append("Stop implies >80% loss, unethical risk")

    return (len(issues) == 0), issues


def is_signal_ethical(signal) -> EthicsCheckResult:
    """
    Validate a `TradingSignal` instance (or similar duck-typed object)
    for logical and ethical constraints.
    """
    issues: List[str] = []

    try:
        signal_type = getattr(signal.signal_type, "name", None) or getattr(signal, "signal_type", None)
        entry = getattr(signal, "entry_price", None)
        target = getattr(signal, "target_price", None)
        stop = getattr(signal, "stop_loss", None)

        ok_prices, price_issues = validate_signal_prices(entry, target, stop, str(signal_type))
        if not ok_prices:
            issues.extend(price_issues)

        # Risk/Reward sanity bounds (0.2 to 10)
        rrr = compute_risk_reward_ratio(_to_decimal(entry), _to_decimal(target), _to_decimal(stop), str(signal_type))
        if rrr is None:
            issues.append("Unable to compute risk/reward ratio")
        else:
            if rrr < 0.2:
                issues.append("Risk/Reward < 0.2, disproportionate risk")
            if rrr > 10:
                issues.append("Risk/Reward > 10, unrealistic expectation")

        # Confidence/quality consistency
        confidence = getattr(signal, "confidence_score", None)
        quality = getattr(signal, "quality_score", None)
        if confidence is not None and quality is not None:
            try:
                if float(confidence) < 0.2 and float(quality) > 0.9:
                    issues.append("Low confidence but very high quality score inconsistency")
            except Exception:
                pass

    except Exception:
        issues.append("Unexpected validation error")

    return EthicsCheckResult(is_ethical=(len(issues) == 0), issues=issues)




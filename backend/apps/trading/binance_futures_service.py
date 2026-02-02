import logging
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests
from django.core.cache import cache
from django.db import transaction

from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


BINANCE_FUTURES_EXCHANGE_INFO_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"

# Cache keys (1 hour by default)
_CACHE_KEY_USDT_PERP_PAIRS = "binance_futures:usdt_perp_pairs"
_CACHE_KEY_USDT_BASE_ASSETS = "binance_futures:usdt_base_assets"


def _extract_usdt_perp_pairs(exchange_info: Dict) -> Set[str]:
    pairs: Set[str] = set()
    for s in exchange_info.get("symbols", []) or []:
        try:
            if s.get("status") != "TRADING":
                continue
            # USDT-margined futures
            if s.get("quoteAsset") != "USDT":
                continue
            # Prefer perpetuals (stable, always available)
            if s.get("contractType") and s.get("contractType") != "PERPETUAL":
                continue
            sym = (s.get("symbol") or "").upper().strip()
            if sym:
                pairs.add(sym)
        except Exception:
            # Defensive: don't let one bad row break the whole sync
            continue
    return pairs


def _extract_base_assets(exchange_info: Dict, usdt_pairs: Set[str]) -> Set[str]:
    base_assets: Set[str] = set()
    for s in exchange_info.get("symbols", []) or []:
        try:
            sym = (s.get("symbol") or "").upper().strip()
            if sym not in usdt_pairs:
                continue
            base = (s.get("baseAsset") or "").upper().strip()
            if base:
                base_assets.add(base)
        except Exception:
            continue
    return base_assets


def fetch_binance_futures_exchange_info(timeout_seconds: int = 15) -> Dict:
    """Fetch raw Binance Futures exchangeInfo JSON."""
    resp = requests.get(BINANCE_FUTURES_EXCHANGE_INFO_URL, timeout=timeout_seconds)
    resp.raise_for_status()
    return resp.json()


def get_binance_usdt_perp_pairs(cache_timeout_seconds: int = 3600, force_refresh: bool = False) -> Set[str]:
    """Return USDT-margined PERPETUAL futures symbols (e.g., BTCUSDT)."""
    if not force_refresh:
        cached = cache.get(_CACHE_KEY_USDT_PERP_PAIRS)
        if cached:
            return set(cached)

    exchange_info = fetch_binance_futures_exchange_info()
    pairs = _extract_usdt_perp_pairs(exchange_info)
    cache.set(_CACHE_KEY_USDT_PERP_PAIRS, sorted(pairs), cache_timeout_seconds)
    return pairs


def get_binance_usdt_futures_base_assets(cache_timeout_seconds: int = 3600, force_refresh: bool = False) -> Set[str]:
    """Return base assets that have a USDT-margined PERPETUAL futures market (e.g., BTC)."""
    if not force_refresh:
        cached = cache.get(_CACHE_KEY_USDT_BASE_ASSETS)
        if cached:
            return set(cached)

    exchange_info = fetch_binance_futures_exchange_info()
    pairs = _extract_usdt_perp_pairs(exchange_info)
    base_assets = _extract_base_assets(exchange_info, pairs)
    cache.set(_CACHE_KEY_USDT_BASE_ASSETS, sorted(base_assets), cache_timeout_seconds)
    return base_assets


def sync_binance_futures_symbols(
    *,
    deactivate_non_futures: bool = True,
    force_refresh: bool = False,
) -> Dict:
    """
    Ensure DB contains Symbol rows for Binance USDT perpetual futures base assets.

    - Creates missing symbols (symbol=BASE, name=BASE).
    - Reactivates futures symbols if previously inactive.
    - Optionally deactivates all other crypto symbols that are NOT Binance futures-eligible.
    """
    try:
        base_assets = get_binance_usdt_futures_base_assets(force_refresh=force_refresh)
    except Exception as e:
        logger.error(f"Failed to fetch Binance futures symbols: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}

    created = 0
    updated = 0
    deactivated = 0

    with transaction.atomic():
        for base in base_assets:
            try:
                obj, was_created = Symbol.objects.get_or_create(
                    symbol=base,
                    defaults={
                        "name": base,
                        "symbol_type": "CRYPTO",
                        "exchange": "BINANCE",
                        "is_active": True,
                        "is_crypto_symbol": True,
                        "is_spot_tradable": False,  # futures-only focus
                    },
                )
                if was_created:
                    created += 1
                    continue

                changed = False
                if obj.symbol_type != "CRYPTO":
                    obj.symbol_type = "CRYPTO"
                    changed = True
                if not obj.is_crypto_symbol:
                    obj.is_crypto_symbol = True
                    changed = True
                if not obj.is_active:
                    obj.is_active = True
                    changed = True
                if obj.exchange != "BINANCE":
                    obj.exchange = "BINANCE"
                    changed = True

                # Keep futures-only posture; if you later want spot too, flip this.
                if obj.is_spot_tradable:
                    obj.is_spot_tradable = False
                    changed = True

                if changed:
                    obj.save()
                    updated += 1
            except Exception as e:
                logger.warning(f"Failed to sync symbol {base}: {e}", exc_info=True)

        if deactivate_non_futures:
            deactivated = Symbol.objects.filter(
                symbol_type="CRYPTO",
                is_crypto_symbol=True,
                is_active=True,
            ).exclude(symbol__in=base_assets).update(is_active=False)

    return {
        "status": "success",
        "futures_base_assets": len(base_assets),
        "created": created,
        "updated": updated,
        "deactivated": deactivated,
    }


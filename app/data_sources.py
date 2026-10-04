"""Fetches real-time market data from the free public CoinGecko REST API (no key needed)."""
import statistics
from typing import Optional

import httpx

from app.config import settings
from app.schemas import AssetMetrics


def fetch_market_data(coins: Optional[list[str]] = None) -> list[dict]:
    coins = coins or settings.coin_list
    params = {
        "vs_currency": settings.vs_currency,
        "ids": ",".join(coins),
        "sparkline": "true",
        "price_change_percentage": "1h,24h,7d",
    }
    with httpx.Client(timeout=20) as client:
        r = client.get(f"{settings.coingecko_base_url}/coins/markets", params=params)
        r.raise_for_status()
        return r.json()


def _rsi(prices: list[float], period: int = 14) -> Optional[float]:
    if len(prices) <= period:
        return None
    deltas = [b - a for a, b in zip(prices[:-1], prices[1:])][-period:]
    gains = sum(d for d in deltas if d > 0) / period
    losses = -sum(d for d in deltas if d < 0) / period
    if losses == 0:
        return 100.0
    return round(100 - 100 / (1 + gains / losses), 2)


def _max_drawdown(prices: list[float]) -> Optional[float]:
    if not prices:
        return None
    peak, worst = prices[0], 0.0
    for p in prices:
        peak = max(peak, p)
        worst = min(worst, (p - peak) / peak)
    return round(worst * 100, 2)


def _r(v: Optional[float]) -> Optional[float]:
    return round(v, 3) if v is not None else None


def compute_metrics(raw: list[dict]) -> list[AssetMetrics]:
    """Deterministic indicator step: done in Python so the LLM only reasons, never calculates."""
    out = []
    for c in raw:
        prices = (c.get("sparkline_in_7d") or {}).get("price") or []
        price = c.get("current_price") or (prices[-1] if prices else 0.0)
        returns = [(b - a) / a for a, b in zip(prices[:-1], prices[1:]) if a]
        vol = round(statistics.pstdev(returns) * 100, 3) if len(returns) > 1 else None
        sma = round(sum(prices[-24:]) / len(prices[-24:]), 4) if prices else None
        ch7 = c.get("price_change_percentage_7d_in_currency")
        trend = "sideways"
        if ch7 is not None:
            trend = "up" if ch7 > 3 else "down" if ch7 < -3 else "sideways"
        out.append(AssetMetrics(
            id=c["id"], symbol=c.get("symbol", "").upper(), price=price,
            change_1h_pct=_r(c.get("price_change_percentage_1h_in_currency")),
            change_24h_pct=_r(c.get("price_change_percentage_24h_in_currency")),
            change_7d_pct=_r(ch7), sma_24h=sma, volatility_pct=vol,
            rsi_14=_rsi(prices), max_drawdown_7d_pct=_max_drawdown(prices), trend=trend,
        ))
    return out

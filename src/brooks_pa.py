from __future__ import annotations

"""Brooks Price Action (approximation) - rules-based proxy signals.

Al Brooks' framework is contextual and discretionary. This module provides a
computable approximation on daily bars to produce:
- brooks_score: 0..1 (higher = more favorable)
- tags: short labels describing detected context

This is *not* a faithful implementation, but a pragmatic proxy that combines:
- Trend context (close vs EMA20/50, EMA slopes)
- Breakout pressure (close near 20-day high/low)
- Bar strength (body vs ATR)
- Volatility contraction (tradeable ranges)

Inputs assume df has columns: date, open, high, low, close, volume.
"""

import numpy as np
import pandas as pd

from .indicators import atr, ema, rolling_max


def _slope(s: pd.Series, n: int = 20) -> float:
    if len(s) < n + 1:
        return 0.0
    y = s.tail(n).to_numpy(dtype=float)
    x = np.arange(len(y), dtype=float)
    x = x - x.mean()
    y = y - y.mean()
    den = (x * x).sum()
    if den == 0:
        return 0.0
    return float((x * y).sum() / den)


def brooks_proxy_score(df: pd.DataFrame) -> tuple[float, list[str]]:
    if df is None or len(df) < 80:
        return 0.0, ["数据不足"]

    d = df.copy()
    d["ema20"] = ema(d["close"], 20)
    d["ema50"] = ema(d["close"], 50)
    d["atr14"] = atr(d, 14)
    d["hi20"] = rolling_max(d["high"], 20)
    d["lo20"] = d["low"].rolling(20).min()

    last = d.iloc[-1]
    close = float(last["close"])
    ema20 = float(last["ema20"])
    ema50 = float(last["ema50"])
    atr14 = float(last.get("atr14", 0) or 0)

    tags: list[str] = []

    # Trend context
    above20 = 1.0 if close > ema20 else 0.0
    above50 = 1.0 if close > ema50 else 0.0
    s20 = _slope(d["ema20"], 20)
    s50 = _slope(d["ema50"], 30)

    trend = 0.5 * above20 + 0.5 * above50
    if trend >= 0.75:
        tags.append("上升趋势环境")
    elif trend <= 0.25:
        tags.append("下降趋势环境")
    else:
        tags.append("可能为震荡/过渡")

    if s20 > 0 and s50 > 0:
        tags.append("均线向上")
    if s20 < 0 and s50 < 0:
        tags.append("均线向下")

    # Breakout pressure
    hi20 = float(last.get("hi20", close) or close)
    lo20 = float(last.get("lo20", close) or close)
    # closeness to extremes
    rng = max(1e-9, hi20 - lo20)
    pos = (close - lo20) / rng

    breakout_pressure = float(np.clip((pos - 0.5) * 2, -1, 1))  # -1..1
    if pos > 0.85:
        tags.append("接近20日高点（突破压力）")
    elif pos < 0.15:
        tags.append("接近20日低点（下破压力）")

    # Bar strength (body vs ATR)
    body = abs(float(last["close"]) - float(last["open"]))
    body_atr = (body / atr14) if atr14 > 1e-9 else 0.0
    strength = float(np.clip(body_atr / 1.2, 0, 1))  # 0..1
    if strength > 0.7:
        tags.append("强趋势K线（实体较大）")

    # Volatility contraction / range
    vol20 = float(d["close"].pct_change().rolling(20).std().iloc[-1] or 0)
    contraction = float(np.clip((0.03 - vol20) / 0.03, 0, 1))  # low vol => higher
    if contraction > 0.6:
        tags.append("波动收缩（可能酝酿突破）")

    # Combine into score (0..1)
    # We favor: trend up, breakout pressure up, strength high, contraction moderate
    score = 0.0
    score += 0.35 * trend
    score += 0.25 * (0.5 + 0.5 * breakout_pressure)  # map -1..1 to 0..1
    score += 0.25 * strength
    score += 0.15 * contraction

    score = float(np.clip(score, 0, 1))
    tags = tags[:6]
    return score, tags

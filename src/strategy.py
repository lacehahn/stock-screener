from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .indicators import atr, ema, pct_change_n, rolling_max


@dataclass
class Pick:
    code: str
    name: str | None
    score: float
    close: float
    entry: float
    stop: float
    take_profit: float
    reasons: list[str]


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["mom63"] = pct_change_n(df["close"], 63)
    df["mom126"] = pct_change_n(df["close"], 126)
    df["atr14"] = atr(df, 14)
    # volatility proxy
    df["vol20"] = df["close"].pct_change().rolling(20).std()
    df["value_traded"] = df["close"] * df["volume"]
    df["avg_value_traded_20"] = df["value_traded"].rolling(20).mean()
    df["hi20"] = rolling_max(df["high"], 20)
    return df


def score_latest(f: pd.DataFrame, w: dict[str, float]) -> tuple[float, list[str]]:
    last = f.iloc[-1]
    reasons = []

    mom63 = float(last.get("mom63", 0) or 0)
    mom126 = float(last.get("mom126", 0) or 0)
    trend = 1.0 if float(last["close"]) > float(last["ema50"]) else 0.0
    vol = float(last.get("vol20", 0) or 0)

    score = 0.0
    score += w.get("momentum_63d", 0) * mom63
    score += w.get("momentum_126d", 0) * mom126
    score += w.get("trend_ema", 0) * trend
    score -= w.get("volatility_penalty", 0) * vol

    if mom63 > 0:
        reasons.append(f"63D momentum +{mom63:.1%}")
    if mom126 > 0:
        reasons.append(f"126D momentum +{mom126:.1%}")
    reasons.append("Close above EMA50" if trend > 0 else "Close below EMA50")
    reasons.append(f"20D vol {vol:.2%}")

    return score, reasons


def propose_levels(f: pd.DataFrame, cfg_levels: dict) -> tuple[float, float, float]:
    last = f.iloc[-1]
    close = float(last["close"])
    atr14 = float(last.get("atr14", 0) or 0)

    # Entry: breakout above last 20d high (buffered)
    entry_cfg = cfg_levels.get("entry", {})
    stop_cfg = cfg_levels.get("stop", {})
    tp_cfg = cfg_levels.get("take_profit", {})

    if entry_cfg.get("kind") == "breakout":
        buf = float(entry_cfg.get("buffer_atr", 0.1))
        base = float(last.get("hi20", close))
        entry = base + buf * atr14
    else:
        entry = close

    # Stop: ATR multiple below entry
    if stop_cfg.get("kind") == "atr":
        mult = float(stop_cfg.get("atr_mult", 2.5))
        stop = max(1.0, entry - mult * atr14)
    else:
        stop = close * 0.92

    # Take profit: risk-reward multiple
    if tp_cfg.get("kind") == "rr":
        rr = float(tp_cfg.get("rr", 2.0))
        take_profit = entry + rr * (entry - stop)
    else:
        take_profit = entry * 1.10

    return entry, stop, take_profit


def pick_top10(
    universe: list,
    history: dict[str, pd.DataFrame],
    cfg: dict,
) -> list[Pick]:
    w = cfg["strategy"]["score_weights"]
    filt = cfg["strategy"]["filters"]
    levels_cfg = cfg["levels"]

    min_value = float(cfg["market"].get("min_avg_value_traded_jpy", 0))
    min_price = float(filt.get("min_price_jpy", 0))

    picks: list[Pick] = []

    for t in universe:
        df = history.get(t.code)
        if df is None or len(df) < 210:
            continue
        fdf = compute_features(df)
        last = fdf.iloc[-1]

        # liquidity
        if float(last.get("avg_value_traded_20", 0) or 0) < min_value:
            continue
        if float(last["close"]) < min_price:
            continue

        # trend filters
        if filt.get("above_ema_50", False) and not (float(last["close"]) > float(last["ema50"])):
            continue
        if filt.get("above_ema_200", False) and not (float(last["close"]) > float(last["ema200"])):
            continue

        score, reasons = score_latest(fdf, w)
        entry, stop, tp = propose_levels(fdf, levels_cfg)

        picks.append(
            Pick(
                code=t.code,
                name=getattr(t, "name", None),
                score=float(score),
                close=float(last["close"]),
                entry=entry,
                stop=stop,
                take_profit=tp,
                reasons=reasons,
            )
        )

    picks.sort(key=lambda p: p.score, reverse=True)
    return picks[: int(cfg["strategy"].get("top_n", 10))]

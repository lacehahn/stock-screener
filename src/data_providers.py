from __future__ import annotations

import io
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import requests


@dataclass
class OHLCV:
    df: pd.DataFrame  # columns: date, open, high, low, close, volume


class StooqProvider:
    """Fetch daily data from Stooq.

    Stooq symbols for JP stocks are typically like: `7203.JP`.
    Endpoint pattern: https://stooq.com/q/d/l/?s=7203.jp&i=d
    """

    BASE = "https://stooq.com/q/d/l/"

    def __init__(
        self,
        throttle_sec: float = 0.2,
        session: Optional[requests.Session] = None,
        cache_dir: str | Path | None = None,
        cache_max_age_sec: int = 60 * 60 * 24,
    ):
        self.throttle_sec = throttle_sec
        self.sess = session or requests.Session()
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.cache_max_age_sec = int(cache_max_age_sec)

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, symbol: str) -> Path | None:
        if not self.cache_dir:
            return None
        safe = symbol.lower().replace("/", "_")
        return self.cache_dir / f"{safe}.csv"

    def _read_cache(self, symbol: str, *, allow_stale: bool = False) -> str | None:
        p = self._cache_path(symbol)
        if not p or not p.exists():
            return None
        if not allow_stale:
            age = time.time() - p.stat().st_mtime
            if age > self.cache_max_age_sec:
                return None
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            return None

    def _write_cache(self, symbol: str, text: str) -> None:
        p = self._cache_path(symbol)
        if not p:
            return
        try:
            p.write_text(text, encoding="utf-8")
        except Exception:
            pass

    def fetch_daily(self, symbol: str) -> OHLCV:
        s = symbol.lower()
        params = {"s": s, "i": "d"}

        time.sleep(self.throttle_sec)
        r = self.sess.get(self.BASE, params=params, timeout=30)
        r.raise_for_status()
        text = r.text
        request_url = str(r.url)

        # Stooq rate-limit message is plain text; fallback to cache
        if "Exceeded the daily hits limit" in text:
            # Prefer fresh cache, but fall back to stale cache if present.
            cached = self._read_cache(s)
            if not cached:
                cached = self._read_cache(s, allow_stale=True)
            if cached:
                text = cached
            else:
                snippet = (text or "").strip().replace("\r", "")[:400]
                raise RuntimeError(
                    "Stooq daily hits limit exceeded and no cache available\n"
                    f"REQUEST: {request_url}\n"
                    f"RESPONSE: {snippet}"
                )
        else:
            # Only cache valid CSVs
            if text.strip().lower().startswith("date,open,high,low,close,volume"):
                self._write_cache(s, text)

        df = pd.read_csv(io.StringIO(text))
        df.columns = [c.strip().lower() for c in df.columns]

        required = {"date", "open", "high", "low", "close", "volume"}
        if not required.issubset(set(df.columns)):
            raise ValueError(f"Unexpected Stooq response columns: {list(df.columns)[:10]}")

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        return OHLCV(df=df)

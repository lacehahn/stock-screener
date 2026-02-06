from __future__ import annotations

import random
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf


@dataclass
class OHLCV:
    df: pd.DataFrame  # columns: date, open, high, low, close, volume


class YahooBatchProvider:
    """Fetch daily OHLCV for Japan equities via yfinance in batches.

    - Maps 4-digit code -> CODE.T
    - Downloads multiple tickers per request to reduce rate limiting.
    - Optional per-ticker CSV cache.

    Notes:
    - Yahoo Finance has undocumented limits; batching + caching helps.
    """

    def __init__(
        self,
        batch_size: int = 10,
        throttle_sec: float = 5.0,
        cache_dir: str | Path | None = None,
        cache_max_age_sec: int = 60 * 60 * 12,
        max_retries: int = 3,
        backoff_sec: float = 10.0,
        user_agents: list[str] | None = None,
    ):
        self.batch_size = int(batch_size)
        self.throttle_sec = float(throttle_sec)
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.cache_max_age_sec = int(cache_max_age_sec)
        self.max_retries = int(max_retries)
        self.backoff_sec = float(backoff_sec)
        self.user_agents = user_agents or [
            # A small UA pool to reduce trivial fingerprinting.
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.2; rv:122.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/122.0.0.0 Safari/537.36",
        ]

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def symbol_for_code(code: str) -> str:
        code = str(code).zfill(4)
        return f"{code}.T"

    def _cache_path(self, code: str) -> Path | None:
        if not self.cache_dir:
            return None
        code = str(code).zfill(4)
        return self.cache_dir / f"{code}.csv"

    def _read_cache(self, code: str) -> pd.DataFrame | None:
        p = self._cache_path(code)
        if not p or not p.exists():
            return None
        age = time.time() - p.stat().st_mtime
        if age > self.cache_max_age_sec:
            return None
        try:
            df = pd.read_csv(p)
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date")
        except Exception:
            return None

    def _write_cache(self, code: str, df: pd.DataFrame) -> None:
        p = self._cache_path(code)
        if not p:
            return
        try:
            df.to_csv(p, index=False)
        except Exception:
            pass

    @staticmethod
    def _normalize_one(df: pd.DataFrame) -> pd.DataFrame:
        # yfinance columns: Open High Low Close Adj Close Volume
        df = df.copy()
        df = df.reset_index()
        rename = {
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        df = df.rename(columns=rename)
        required = {"date", "open", "high", "low", "close", "volume"}
        if not required.issubset(set(df.columns)):
            raise ValueError(f"Unexpected Yahoo columns: {list(df.columns)[:10]}")
        df["date"] = pd.to_datetime(df["date"])
        df = df[["date", "open", "high", "low", "close", "volume"]]
        df = df.sort_values("date")
        return df

    def fetch_many_by_codes(self, codes: list[str], lookback_days: int = 520) -> dict[str, OHLCV]:
        # Determine period
        period = "3y" if int(lookback_days) >= 700 else "2y"

        out: dict[str, OHLCV] = {}

        # Serve from cache first
        remaining: list[str] = []
        for c in codes:
            cached = self._read_cache(c)
            if cached is not None and not cached.empty:
                out[str(c).zfill(4)] = OHLCV(df=cached.tail(int(lookback_days)))
            else:
                remaining.append(str(c).zfill(4))

        # Batch download the rest
        for i in range(0, len(remaining), self.batch_size):
            batch_codes = remaining[i : i + self.batch_size]
            tickers = [self.symbol_for_code(c) for c in batch_codes]

            # Gentle throttle between requests
            if i > 0:
                time.sleep(self.throttle_sec)

            df_all = None

            # Retry with backoff + rotating UA
            for attempt in range(self.max_retries + 1):
                ua = random.choice(self.user_agents)
                sess = requests.Session()
                sess.headers.update({"User-Agent": ua})

                try:
                    df_all = yf.download(
                        tickers=tickers,
                        period=period,
                        interval="1d",
                        auto_adjust=False,
                        group_by="ticker",
                        threads=True,
                        progress=False,
                        session=sess,
                    )
                    break
                except Exception as e:
                    msg = str(e)
                    is_rate = ("Rate limited" in msg) or ("Too Many Requests" in msg) or ("YFRateLimitError" in msg)
                    if attempt >= self.max_retries or not is_rate:
                        raise
                    sleep_s = self.backoff_sec * (2**attempt) + random.random() * 2.0
                    time.sleep(sleep_s)

            # When only 1 ticker is requested, yfinance may return single-index columns.
            for code, ticker in zip(batch_codes, tickers):
                try:
                    if isinstance(df_all.columns, pd.MultiIndex):
                        part = df_all[ticker]
                    else:
                        part = df_all

                    if part is None or part.empty:
                        # fallback to cache if available (even stale)
                        cached = self._read_cache(code)
                        if cached is not None and not cached.empty:
                            out[code] = OHLCV(df=cached.tail(int(lookback_days)))
                        continue

                    norm = self._normalize_one(part)
                    norm = norm.tail(int(lookback_days))
                    out[code] = OHLCV(df=norm)
                    self._write_cache(code, norm)
                except Exception:
                    # best-effort; fallback to cache
                    cached = self._read_cache(code)
                    if cached is not None and not cached.empty:
                        out[code] = OHLCV(df=cached.tail(int(lookback_days)))
                    continue

        return out

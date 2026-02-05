from __future__ import annotations

import io
import time
from dataclasses import dataclass
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

    def __init__(self, throttle_sec: float = 0.05, session: Optional[requests.Session] = None):
        self.throttle_sec = throttle_sec
        self.sess = session or requests.Session()

    def fetch_daily(self, symbol: str) -> OHLCV:
        s = symbol.lower()
        params = {"s": s, "i": "d"}
        time.sleep(self.throttle_sec)
        r = self.sess.get(self.BASE, params=params, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        # Expected columns: Date, Open, High, Low, Close, Volume
        df.columns = [c.strip().lower() for c in df.columns]
        df = df.rename(columns={"date": "date"})
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        return OHLCV(df=df)

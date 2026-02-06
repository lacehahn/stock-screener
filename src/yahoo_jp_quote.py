from __future__ import annotations

import re
import time
from dataclasses import dataclass

import requests


@dataclass
class Quote:
    symbol: str
    price: float
    asof_text: str | None = None


def _ua() -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )


def fetch_intraday_price(symbol: str, *, timeout_sec: float = 15.0, throttle_sec: float = 0.3) -> Quote:
    """Best-effort scrape from Yahoo Japan quote page.

    Note: This may break if Yahoo changes HTML or blocks scraping.
    """

    time.sleep(float(throttle_sec))

    url = f"https://finance.yahoo.co.jp/quote/{symbol}"
    if symbol.endswith("/forum"):
        url = f"https://finance.yahoo.co.jp/quote/{symbol}"
    r = requests.get(
        url,
        headers={
            "User-Agent": _ua(),
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
        },
        timeout=float(timeout_sec),
    )
    r.raise_for_status()
    html = r.text

    # Try multiple robust patterns (Yahoo HTML changes often).

    # 1) regularMarketPrice style (often embedded in JSON)
    m = re.search(r"regularMarketPrice\"\s*:\s*\{[^}]*\"raw\"\s*:\s*([0-9.]+)", html)
    if m:
        return Quote(symbol=symbol, price=float(m.group(1)))

    # 2) price in JSON-LD
    m = re.search(r"\"price\"\s*:\s*\"([0-9,.]+)\"", html)
    if m:
        return Quote(symbol=symbol, price=float(m.group(1).replace(",", "")))

    # 3) og:price:amount or similar meta
    m = re.search(r"property=\"og:price:amount\"\s+content=\"([0-9,.]+)\"", html)
    if m:
        return Quote(symbol=symbol, price=float(m.group(1).replace(",", "")))

    # 4) Fallback: pick the first number that looks like a price, but avoid huge volumes by limiting length.
    m = re.search(r">\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*<", html)
    if m:
        return Quote(symbol=symbol, price=float(m.group(1).replace(",", "")))

    raise RuntimeError("Could not parse price from Yahoo JP HTML")

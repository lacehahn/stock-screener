#!/usr/bin/env python3
from __future__ import annotations

"""Update Nikkei 225 universe list (best-effort, multi-source).

NOTE: Nikkei 225 is a proprietary index. There is no guaranteed free official API.
This script tries multiple public sources and writes `universe.csv`.

Sources (in order):
1) Stooq constituents pages (free): https://stooq.com/q/i/?s=^nkx
2) Japanese Wikipedia: https://ja.wikipedia.org/wiki/%E6%97%A5%E7%B5%8C225
3) English Wikipedia: https://en.wikipedia.org/wiki/Nikkei_225

If parsing fails, it keeps the existing `universe.csv`.

Usage:
  python update_universe.py
"""

import csv
import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
OUT_CSV = ROOT / "universe.csv"


@dataclass
class Ticker:
    code: str
    name: str | None


_SESS = requests.Session()


def _get(url: str) -> str:
    r = _SESS.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text


def _flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join([str(x) for x in tup if str(x) != "nan"]).strip() for tup in df.columns]
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _extract_from_tables(tables: list[pd.DataFrame]) -> list[Ticker]:
    """Pick the table that most likely contains ~225 four-digit stock codes."""
    best: list[Ticker] = []

    for t in tables:
        t = _flatten_cols(t)

        # Find the column with the most 4-digit codes
        best_code_col = None
        best_count = 0
        for c in t.columns:
            s = t[c].astype(str)
            cnt = s.str.contains(r"\b\d{4}\b").sum()
            if cnt > best_count:
                best_count = int(cnt)
                best_code_col = c

        if not best_code_col or best_count < 50:
            continue

        # Choose a likely name column (prefer non-code text)
        name_col = None
        for c in t.columns:
            cl = c.lower()
            if any(k in cl for k in ["company", "name", "銘柄", "会社", "企業"]):
                name_col = c
                break

        out: list[Ticker] = []
        for _, row in t.iterrows():
            raw = str(row.get(best_code_col, "")).strip()
            m = re.search(r"(\d{4})", raw)
            if not m:
                continue
            code = m.group(1)
            nm = None
            if name_col:
                nm_raw = str(row.get(name_col, "")).strip()
                nm = nm_raw if nm_raw and nm_raw.lower() != "nan" else None
            out.append(Ticker(code=code, name=nm))

        if len(out) > len(best):
            best = out

    return best


def try_wikipedia(url: str) -> list[Ticker]:
    html = _get(url)
    tables = pd.read_html(StringIO(html))
    return _extract_from_tables(tables)


def try_stooq_nk225() -> list[Ticker]:
    """Parse Nikkei 225 constituents from Stooq.

    Stooq page includes a constituents table; we parse it with pandas.read_html for stability.
    Pagination uses `l=1..5`.
    """
    out: list[Ticker] = []
    for l in range(1, 6):
        url = f"https://stooq.com/q/i/?s=^nkx&l={l}"
        html = _get(url)
        tables = pd.read_html(StringIO(html))

        best = None
        for t in tables:
            t = _flatten_cols(t)
            cols = [c.lower() for c in t.columns]
            if any("symbol" in c for c in cols) and any("nazwa" in c or "name" in c for c in cols):
                best = t
                break
        if best is None:
            # fallback: pick the biggest table
            best = max(tables, key=lambda x: len(x))
            best = _flatten_cols(best)

        # locate columns
        sym_col = None
        name_col = None
        for c in best.columns:
            cl = c.lower()
            if sym_col is None and "symbol" in cl:
                sym_col = c
            if name_col is None and ("nazwa" in cl or "name" in cl):
                name_col = c

        if sym_col is None:
            continue

        for _, row in best.iterrows():
            sym = str(row.get(sym_col, "")).strip()
            m = re.search(r"\b(\d{4})\.JP\b", sym, flags=re.IGNORECASE)
            if not m:
                continue
            code = m.group(1)
            nm = None
            if name_col is not None:
                nm_raw = str(row.get(name_col, "")).strip()
                nm = nm_raw if nm_raw and nm_raw.lower() != "nan" else None
            out.append(Ticker(code=code, name=nm))

    uniq: dict[str, Ticker] = {}
    for t in out:
        uniq.setdefault(t.code, t)
    return list(uniq.values())


def load_existing() -> list[Ticker]:
    if not OUT_CSV.exists():
        return []
    df = pd.read_csv(OUT_CSV)
    out: list[Ticker] = []
    for _, r in df.iterrows():
        out.append(Ticker(code=str(r["code"]).zfill(4), name=str(r.get("name", "")) or None))
    return out


def write_csv(tickers: list[Ticker]) -> None:
    tmp = OUT_CSV.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "name"])
        for t in sorted({x.code: x for x in tickers}.values(), key=lambda x: x.code):
            w.writerow([t.code, t.name or ""])
    tmp.replace(OUT_CSV)


def main() -> int:
    existing = load_existing()

    best: list[Ticker] = []

    # 1) Stooq
    try:
        tickers = try_stooq_nk225()
        if len(tickers) >= 200:
            best = tickers
    except Exception:
        pass

    # 2) Wikipedia fallbacks
    if len(best) < 200:
        sources = [
            "https://ja.wikipedia.org/wiki/%E6%97%A5%E7%B5%8C225",
            "https://en.wikipedia.org/wiki/Nikkei_225",
        ]
        for url in sources:
            try:
                tickers = try_wikipedia(url)
                if len(tickers) >= 200:
                    best = tickers
                    break
                if len(tickers) > len(best):
                    best = tickers
            except Exception:
                continue

    if len(best) < 200:
        # Keep existing if it looks better
        if len(existing) >= len(best):
            print(f"Universe update failed; keeping existing universe.csv ({len(existing)} rows)")
            return 1

    write_csv(best)
    print(f"Updated universe.csv: {len(best)} tickers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

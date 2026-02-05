from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import requests


@dataclass
class Ticker:
    code: str  # e.g. 7203
    name: str | None = None

    @property
    def stooq_symbol(self) -> str:
        return f"{self.code}.JP"


def _parse_nikkei_codes_from_wikipedia() -> list[Ticker]:
    """Best-effort pull of Nikkei 225 constituents.

    Uses Wikipedia table (no auth). If it breaks, switch to a maintained CSV.
    """
    url = "https://en.wikipedia.org/wiki/Nikkei_225"
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    html = r.text
    # Pandas 2.2 warns about literal strings; use StringIO for forward-compat.
    from io import StringIO
    tables = pd.read_html(StringIO(html))

    # Find a table that contains "Code" column.
    for t in tables:
        cols = [str(c).lower() for c in t.columns]
        if any("code" in c for c in cols):
            code_col = None
            name_col = None
            for c in t.columns:
                cl = str(c).lower()
                if "code" in cl:
                    code_col = c
                if "company" in cl or "name" in cl:
                    name_col = c
            if code_col is None:
                continue

            out: list[Ticker] = []
            for _, row in t.iterrows():
                raw = str(row.get(code_col, "")).strip()
                m = re.search(r"(\d{4})", raw)
                if not m:
                    continue
                code = m.group(1)
                name = str(row.get(name_col, "")).strip() if name_col else None
                out.append(Ticker(code=code, name=name))
            if len(out) >= 200:
                return out

    raise RuntimeError("Failed to parse Nikkei 225 constituents from Wikipedia")


def load_universe(kind: str, csv_path: str | None = None) -> list[Ticker]:
    kind = kind.lower()
    if kind == "nikkei225":
        return _parse_nikkei_codes_from_wikipedia()
    if kind == "csv":
        if not csv_path:
            raise ValueError("csv_path required when kind=csv")
        from pathlib import Path
        p = Path(csv_path)
        if not p.is_absolute():
            # resolve relative to project root
            root = Path(__file__).resolve().parents[1]
            p = root / p
        df = pd.read_csv(p)
        # expect columns: code, name(optional)
        out = []
        for _, r in df.iterrows():
            out.append(Ticker(code=str(r["code"]).zfill(4), name=str(r.get("name", "")) or None))
        return out
    raise ValueError(f"Unknown universe kind: {kind}")

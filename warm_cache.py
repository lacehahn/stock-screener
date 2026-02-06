#!/usr/bin/env python3
from __future__ import annotations

"""Warm Stooq cache gradually.

Goal: Build up local CSV cache without triggering Stooq daily hit limits too quickly.

Strategy:
- Load universe
- Select a small slice (batch)
- Fetch daily bars for that slice
- Store via StooqProvider cache

Usage:
  python warm_cache.py --batch-size 30 --offset 0

Recommended: schedule hourly or a few times per day.
"""

import argparse
from pathlib import Path

import yaml

from src.data_providers import StooqProvider
from src.universe import load_universe


def load_cfg() -> dict:
    cfg_path = Path(__file__).resolve().parent / "config.yaml"
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=30)
    ap.add_argument("--offset", type=int, default=0)
    args = ap.parse_args()

    cfg = load_cfg()
    uni_cfg = cfg["universe"]
    universe = load_universe(uni_cfg["kind"], uni_cfg.get("path"))

    stooq_cfg = cfg.get("stooq", {})
    provider = StooqProvider(
        throttle_sec=float(stooq_cfg.get("throttle_sec", 2.0)),
        cache_dir=Path(__file__).resolve().parent / "data_cache",
        cache_max_age_sec=int(stooq_cfg.get("cache_max_age_sec", 604800)),
    )

    start = max(0, int(args.offset))
    end = min(len(universe), start + int(args.batch_size))
    batch = universe[start:end]

    ok = 0
    fail = 0
    for t in batch:
        try:
            provider.fetch_daily(t.stooq_symbol)
            ok += 1
        except Exception:
            fail += 1

    print(f"Warm cache batch {start}:{end} done. ok={ok} fail={fail} cache_dir=data_cache")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

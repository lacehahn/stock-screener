#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd
import yaml

from src.data_providers import StooqProvider
from src.report import render_markdown, write_report
from src.strategy import pick_top10
from src.universe import load_universe


def load_cfg() -> dict:
    cfg_path = Path(__file__).resolve().parent / "config.yaml"
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def asof_date(arg: str) -> str:
    if arg == "auto":
        return dt.datetime.now().strftime("%Y-%m-%d")
    return arg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default="auto")
    ap.add_argument("--limit-universe", type=int, default=0)
    args = ap.parse_args()

    cfg = load_cfg()

    uni_cfg = cfg["universe"]
    universe = load_universe(uni_cfg["kind"], uni_cfg.get("path"))
    if args.limit_universe and args.limit_universe > 0:
        universe = universe[: args.limit_universe]

    provider = StooqProvider(throttle_sec=0.05)
    lookback = int(cfg["data"].get("lookback_days", 260))

    history: dict[str, pd.DataFrame] = {}
    for i, t in enumerate(universe, 1):
        try:
            ohlcv = provider.fetch_daily(t.stooq_symbol)
            df = ohlcv.df
            df = df.tail(lookback).copy()
            # normalize columns
            df = df[["date", "open", "high", "low", "close", "volume"]]
            history[t.code] = df
        except Exception:
            continue
        if i % 25 == 0:
            print(f"已获取 {i}/{len(universe)}")

    picks = pick_top10(universe, history, cfg)
    # If we don't have enough picks, relax filters to try to fill Top N.
    top_n = int(cfg["strategy"].get("top_n", 10))
    if len(picks) < top_n:
        relaxed = dict(cfg)
        relaxed_market = dict(relaxed.get("market", {}))
        relaxed_market["min_avg_value_traded_jpy"] = min(float(relaxed_market.get("min_avg_value_traded_jpy", 0)), 20000000.0)
        relaxed["market"] = relaxed_market
        relaxed_strategy = dict(relaxed.get("strategy", {}))
        relaxed_filters = dict(relaxed_strategy.get("filters", {}))
        relaxed_filters["above_ema_50"] = False
        relaxed_filters["above_ema_200"] = False
        relaxed_strategy["filters"] = relaxed_filters
        relaxed["strategy"] = relaxed_strategy

        more = pick_top10(universe, history, relaxed)
        # merge by code preserving order
        seen = set()
        merged = []
        for p in picks + more:
            if p.code in seen:
                continue
            seen.add(p.code)
            merged.append(p)
            if len(merged) >= top_n:
                break
        picks = merged

    asof = asof_date(args.asof)
    md = render_markdown(picks, asof)
    out_dir = Path(__file__).resolve().parent / cfg["report"]["out_dir"]
    report_path = write_report(out_dir, md, asof)

    # Also update stable "latest" pointers for the web app
    latest_md = out_dir / "latest.md"
    latest_md.write_text(md, encoding="utf-8")

    html_path = out_dir / f"nikkei-report-{asof}.html"
    latest_html = out_dir / "latest.html"
    if html_path.exists():
        latest_html.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"报告已生成：{report_path}")
    print(f"最新报告：{latest_md}")
    print(f"最新HTML：{latest_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

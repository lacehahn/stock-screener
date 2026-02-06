#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import json

import pandas as pd
import yaml

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover
    tqdm = None

# Load local .env if present (so user doesn't need to export env vars)
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except Exception:
    pass

from src.data_providers import StooqProvider
from src.yahoo_provider import YahooBatchProvider
from src.report import render_markdown, write_report
from src.report_picks import write_picks_json
from src.strategy import pick_top10
from src.ai_brooks import analyze_brooks
from src.universe import load_universe


def make_dummy_ohlcv(lookback_days: int = 520, start_price: float = 2500.0) -> pd.DataFrame:
    # Business days ending today
    end = dt.date.today()
    idx = pd.bdate_range(end=end, periods=int(lookback_days))

    # Simple random-walk-ish series (deterministic enough without RNG)
    # Use a gentle drift based on index position.
    base = pd.Series(range(len(idx)), index=idx, dtype=float)
    close = start_price * (1.0 + 0.0005 * base).clip(lower=0.2)
    # Add a small oscillation
    close = close * (1.0 + 0.02 * (pd.Series(range(len(idx))) % 10 - 5) / 10.0).values

    open_ = close.shift(1).fillna(close)
    high = pd.concat([open_, close], axis=1).max(axis=1) * 1.01
    low = pd.concat([open_, close], axis=1).min(axis=1) * 0.99
    volume = pd.Series(1_500_000, index=idx, dtype=float)

    df = pd.DataFrame(
        {
            "date": idx,
            "open": open_.values,
            "high": high.values,
            "low": low.values,
            "close": close.values,
            "volume": volume.values,
        }
    )
    return df


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

    asof = asof_date(args.asof)

    uni_cfg = cfg["universe"]
    universe = load_universe(uni_cfg["kind"], uni_cfg.get("path"))
    if args.limit_universe and args.limit_universe > 0:
        universe = universe[: args.limit_universe]

    provider_name = str(cfg.get("data", {}).get("provider", "stooq")).lower()
    lookback = int(cfg["data"].get("lookback_days", 520))

    stooq_cfg = cfg.get("stooq", {})

    # Optional: keep a daily snapshot of fetched OHLCV as CSV (per-ticker) for audit/backtests
    stooq_keep_daily = bool(stooq_cfg.get("keep_daily_csv", False))
    daily_cache_dir = str(stooq_cfg.get("daily_cache_dir", "data_cache_daily"))
    daily_dir = Path(__file__).resolve().parent / daily_cache_dir / asof
    if stooq_keep_daily:
        daily_dir.mkdir(parents=True, exist_ok=True)

    stooq = StooqProvider(
        throttle_sec=float(stooq_cfg.get("throttle_sec", 0.25)),
        cache_dir=Path(__file__).resolve().parent / "data_cache",
        cache_max_age_sec=int(stooq_cfg.get("cache_max_age_sec", 604800)),
    )
    yahoo = YahooBatchProvider(
        batch_size=10,
        throttle_sec=5.0,
        max_retries=3,
        backoff_sec=10.0,
        cache_dir=Path(__file__).resolve().parent / "data_cache_yahoo",
    )

    # Twelve Data settings removed (too expensive)

    history: dict[str, pd.DataFrame] = {}
    dummy_used = False

    fetched = 0
    failed = 0
    first_err: str | None = None

    if provider_name == "yahoo":
        codes = [t.code for t in universe]
        if tqdm is not None:
            # show a coarse progress bar by batches
            total_batches = (len(codes) + yahoo.batch_size - 1) // yahoo.batch_size
            pbar = tqdm(total=total_batches, desc="抓取行情（Yahoo批量）", unit="批")
        else:
            pbar = None
            print(f"开始抓取行情（Yahoo批量）：{len(codes)} 只，batch={yahoo.batch_size}")

        # Fetch in batches while updating progress
        for i in range(0, len(codes), yahoo.batch_size):
            batch = codes[i : i + yahoo.batch_size]
            try:
                got = yahoo.fetch_many_by_codes(batch, lookback_days=lookback)
                for code, ohlcv in got.items():
                    history[code] = ohlcv.df
                fetched += len(got)
                failed += (len(batch) - len(got))
            except Exception as e:
                failed += len(batch)
                if first_err is None:
                    first_err = f"{type(e).__name__}: {e}"
            if pbar is not None:
                pbar.update(1)
        if pbar is not None:
            pbar.close()

    elif provider_name == "localcsv":
        # Local-only mode: read cached Stooq CSVs from data_cache/ (no network)
        cache_dir = Path(__file__).resolve().parent / "data_cache"
        it = universe
        if tqdm is not None:
            it = tqdm(universe, desc="读取本地缓存（CSV）", unit="只")
        else:
            print(f"开始读取本地缓存（CSV）：{len(universe)} 只")

        for t in it:
            try:
                p = cache_dir / f"{t.stooq_symbol.lower()}.csv"
                if not p.exists():
                    raise FileNotFoundError(str(p))
                df = pd.read_csv(p)
                df.columns = [c.strip().lower() for c in df.columns]
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date")
                df = df.tail(lookback).copy()
                df = df[["date", "open", "high", "low", "close", "volume"]]
                history[t.code] = df
                if stooq_keep_daily:
                    outp = daily_dir / f"{t.code}.csv"
                    df.to_csv(outp, index=False)
                fetched += 1
            except Exception as e:
                failed += 1
                if first_err is None:
                    first_err = f"{type(e).__name__}: {e}"
                continue

    else:
        it = universe
        if tqdm is not None:
            it = tqdm(universe, desc="抓取行情（Stooq）", unit="只")
        else:
            print(f"开始抓取行情（Stooq）：{len(universe)} 只")

        for t in it:
            try:
                ohlcv = stooq.fetch_daily(t.stooq_symbol)
                df = ohlcv.df
                df = df.tail(lookback).copy()
                df = df[["date", "open", "high", "low", "close", "volume"]]
                history[t.code] = df
                if stooq_keep_daily:
                    # Store full lookback slice as-of today
                    outp = daily_dir / f"{t.code}.csv"
                    df.to_csv(outp, index=False)
                fetched += 1
            except Exception as e:
                failed += 1
                if first_err is None:
                    first_err = f"{type(e).__name__}: {e}"
                continue

            if tqdm is None and fetched % 25 == 0:
                print(f"已获取 {fetched}/{len(universe)}")

    print(f"行情抓取完成：成功 {fetched}/{len(universe)}，失败 {failed}")
    if fetched == 0 and first_err:
        print(f"抓取全部失败（示例错误）：{first_err}")
        dummy_cfg = cfg.get("dummy", {})
        if bool(dummy_cfg.get("enabled", True)) and bool(dummy_cfg.get("only_when_all_failed", True)):
            # Fill dummy data so the rest of the pipeline (ranking/report/web) can be tested.
            dummy_used = True
            for i, t in enumerate(universe):
                df = make_dummy_ohlcv(lookback_days=lookback, start_price=1200.0 + 15.0 * i)
                history[t.code] = df
            print(f"已填充 Dummy 行情数据：{len(history)} 只（仅用于流程/前端调试，非真实行情）")
        else:
            print("Dummy 已关闭：本次不填充虚拟行情数据")

    dummy_cfg = cfg.get("dummy", {})
    if bool(dummy_cfg.get("enabled", True)) and (not bool(dummy_cfg.get("only_when_all_failed", True))):
        dummy_used = True
        history = {}
        for i, t in enumerate(universe):
            df = make_dummy_ohlcv(lookback_days=lookback, start_price=1200.0 + 15.0 * i)
            history[t.code] = df
        print(f"已强制使用 Dummy 行情数据：{len(history)} 只（仅用于流程/前端调试，非真实行情）")

    picks = pick_top10(universe, history, cfg)
    if dummy_used:
        for p in picks:
            p.reasons.insert(0, "DUMMY 数据（用于调试，非真实行情）")

    # AI Brooks analysis (best-effort) on top candidates
    ai_cfg = cfg.get("ai", {})
    if (bool(ai_cfg.get("enabled", False)) and (not dummy_used)) and picks:
        max_cand = int(ai_cfg.get("max_candidates", 20))
        ai_weight = float(ai_cfg.get("weight", 0.25))
        base_weight = max(0.0, 1.0 - ai_weight)
        model = str(ai_cfg.get("model", "gpt-4.1-mini"))
        api_key_env = str(ai_cfg.get("api_key_env", "OPENAI_API_KEY"))

        # analyze only top K to control cost
        cand = picks[: max_cand]

        ait = cand
        if tqdm is not None:
            ait = tqdm(cand, desc="AI 解读（Brooks）", unit="只")
        else:
            print(f"开始 AI 解读：{len(cand)} 只")

        for p in ait:
            df = history.get(p.code)
            if df is None:
                continue
            ohlcv = df.tail(120).to_dict(orient="records")
            res = analyze_brooks(p.code, p.name, ohlcv, model=model, api_key_env=api_key_env)
            if not res:
                continue
            p.ai_score = float(res.get("ai_score", 0.0) or 0.0)
            p.ai_summary_zh = str(res.get("summary_zh", "")) or None
            p.ai_context = str(res.get("context", "")) or None
            p.ai_setup_tags = list(res.get("setup_tags", []) or [])

            # Re-weight final score with AI
            p.score = base_weight * float(p.score) + ai_weight * float(p.ai_score)
            p.reasons.append(f"AI Brooks score {p.ai_score:.2f}")

        if tqdm is None:
            print("AI 解读完成")

        # re-rank after AI
        picks.sort(key=lambda x: x.score, reverse=True)
        picks = picks[: int(cfg["strategy"].get("top_n", 10))]

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

    # Load AI trade review (generated in the morning by paper_trade.py)
    ai_trade = None
    try:
        p = Path(__file__).resolve().parent / "paper" / f"ai-trade-{asof}.json"
        if p.exists():
            ai_trade = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        ai_trade = None

    md = render_markdown(picks, asof, ai_trade=ai_trade)
    if dummy_used:
        md = md.replace(
            "> **声明：非投资建议。以下为基于历史日线数据的技术面筛选与价位参考。**",
            "> **声明：非投资建议。以下为基于历史日线数据的技术面筛选与价位参考。**\n>\n> **注意：当前报告使用 Dummy 行情数据（用于流程/前端调试），非真实市场数据。**",
        )
    out_dir = Path(__file__).resolve().parent / cfg["report"]["out_dir"]
    report_path = write_report(out_dir, md, asof)
    _picks_json_path = write_picks_json(out_dir, picks, asof)

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

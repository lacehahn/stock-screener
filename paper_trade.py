#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

# Load local .env if present
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except Exception:
    pass

from src.yahoo_jp_quote import fetch_intraday_price
from src.ai_trade import analyze_trade_plan

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


@dataclass
class Position:
    code: str
    qty: int
    avg_cost: float


def load_cfg() -> dict:
    cfg_path = Path(__file__).resolve().parent / "config.yaml"
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def paper_dir() -> Path:
    d = Path(__file__).resolve().parent / "paper"
    d.mkdir(parents=True, exist_ok=True)
    return d


def portfolio_path() -> Path:
    return paper_dir() / "portfolio.json"


def trades_path() -> Path:
    return paper_dir() / "trades.csv"


def equity_path() -> Path:
    return paper_dir() / "equity.csv"


def load_portfolio(initial_cash: float) -> dict:
    p = portfolio_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {
        "cash": float(initial_cash),
        "positions": {},  # code -> {qty, avg_cost}
        "last_trade_date": None,
    }


def save_portfolio(obj: dict) -> None:
    portfolio_path().write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_csv_headers(path: Path, headers: list[str]) -> None:
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)


def _now_jst_iso() -> str:
    if ZoneInfo is None:
        return dt.datetime.now().isoformat(timespec="seconds")
    return dt.datetime.now(tz=ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")


def append_trade(row: dict) -> None:
    p = trades_path()
    ensure_csv_headers(
        p,
        [
            "ts",
            "date",
            "code",
            "side",
            "qty",
            "price",
            "notional",
            "reason",
        ],
    )
    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            row.get("ts") or _now_jst_iso(),
            row.get("date"),
            row.get("code"),
            row.get("side"),
            row.get("qty"),
            f"{row.get('price', 0):.2f}",
            f"{row.get('notional', 0):.2f}",
            row.get("reason"),
        ])


def append_equity(row: dict) -> None:
    p = equity_path()
    ensure_csv_headers(p, ["date", "cash", "holdings_value", "total"])
    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            row.get("date"),
            f"{row.get('cash', 0):.2f}",
            f"{row.get('holdings_value', 0):.2f}",
            f"{row.get('total', 0):.2f}",
        ])


def _jst_today() -> str:
    if ZoneInfo is None:
        return dt.date.today().isoformat()
    return dt.datetime.now(tz=ZoneInfo("Asia/Tokyo")).date().isoformat()


def maybe_migrate_trades_csv() -> None:
    """If trades.csv exists without 'ts' column, migrate it in-place.

    Also cleans duplicate header rows if present.
    """
    p = trades_path()
    if not p.exists():
        return
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
        if not lines:
            return

        # If already new format, just clean duplicate headers.
        if lines[0].lstrip().startswith("ts,"):
            out = [lines[0].lstrip()]
            for ln in lines[1:]:
                s = ln.strip()
                if not s:
                    continue
                if s.startswith("ts,") or s.startswith("date,"):
                    continue
                out.append(s)
            p.write_text("\n".join(out) + "\n", encoding="utf-8")
            return

        header = lines[0].split(",")
        if not header or header[0] != "date":
            return

        # Expect old header: date,code,side,qty,price,notional,reason
        new_lines = ["ts,date,code,side,qty,price,notional,reason"]
        for ln in lines[1:]:
            if not ln.strip():
                continue
            if ln.startswith("date,"):
                continue
            parts = ln.split(",")
            if len(parts) < 7:
                continue
            date = parts[0].strip()
            # Put a synthetic JST timestamp at 09:00:00
            ts = f"{date}T09:00:00+09:00"
            new_lines.append(",".join([ts] + parts))

        p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception:
        return


def load_latest_picks() -> dict:
    p = Path(__file__).resolve().parent / "reports" / "latest_picks.json"
    if not p.exists():
        raise RuntimeError("Missing reports/latest_picks.json. Run run_daily.py first.")
    return json.loads(p.read_text(encoding="utf-8"))


def get_target_codes(picks_payload: dict, top_k: int) -> list[str]:
    picks = picks_payload.get("picks") or []
    codes = []
    for p in picks[: int(top_k)]:
        code = str(p.get("code") or "").zfill(4)
        if code and code not in codes:
            codes.append(code)
    return codes


def yahoo_symbol_for_code(code: str, tpl: str) -> str:
    return tpl.format(code=str(code).zfill(4))


def _local_cache_path_for_code(code: str) -> Path:
    # Python stooq cache uses symbol like "1332.jp" as filename
    sym = f"{str(code).zfill(4)}.jp"
    return Path(__file__).resolve().parent / "data_cache" / f"{sym}.csv"


def fetch_local_price(code: str, field: str = "close") -> float | None:
    p = _local_cache_path_for_code(code)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
        if df.empty:
            return None
        field_l = str(field).strip().lower()
        if field_l not in ("close", "open"):
            field_l = "close"
        v = float(df.iloc[-1][field_l])
        return v if v > 0 else None
    except Exception:
        return None


def fetch_prices_yahoo(
    codes: list[str],
    tpl: str,
    timeout_sec: float,
    throttle_sec: float,
    *,
    use_forum_page: bool = True,
    fallback_local: bool = True,
    local_field: str = "close",
    fallback_pick_close: bool = True,
    pick_close_map: dict[str, float] | None = None,
) -> dict[str, float]:
    out: dict[str, float] = {}
    missing: list[str] = []
    for c in codes:
        sym = yahoo_symbol_for_code(c, tpl)
        if use_forum_page:
            sym = f"{sym}/forum"
        try:
            q = fetch_intraday_price(sym, timeout_sec=timeout_sec, throttle_sec=throttle_sec)
            out[c] = float(q.price)
        except Exception:
            missing.append(c)

    if fallback_local and missing:
        for c in missing:
            px = fetch_local_price(c, field=local_field)
            if px is not None:
                out[c] = float(px)

    # Final fallback: use close in latest_picks.json (signal close) if everything else missing.
    if fallback_pick_close and pick_close_map:
        for c in missing:
            if c in out:
                continue
            px = pick_close_map.get(str(c).zfill(4))
            if px is not None and float(px) > 0:
                out[c] = float(px)

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Paper trading (T+1) - daily rebalance")
    ap.add_argument("--date", default="auto", help="trade date (JST, YYYY-MM-DD), default=auto")
    ap.add_argument("--force", action="store_true", help="force re-run even if already traded for the date")
    args = ap.parse_args()

    cfg = load_cfg()
    pt = cfg.get("paper_trading", {})
    if not bool(pt.get("enabled", True)):
        print("paper_trading disabled")
        return 0

    top_k = int(pt.get("top_k", 5))
    initial_cash = float(pt.get("initial_cash_jpy", 1_000_000))
    lot_size = int(pt.get("lot_size", 100))
    buy_min_lot_if_affordable = bool(pt.get("buy_min_lot_if_affordable", True))
    price_source = str(pt.get("price_source", "yahoo_jp"))

    picks_payload = load_latest_picks()
    target = get_target_codes(picks_payload, top_k)
    pick_close_map = {str(p.get('code')).zfill(4): float(p.get('close')) for p in (picks_payload.get('picks') or []) if p.get('code') and p.get('close')}

    maybe_migrate_trades_csv()

    pf = load_portfolio(initial_cash)
    trade_date = _jst_today() if str(args.date).lower() == "auto" else str(args.date)

    # Optional: ask AI to adjust today's target ordering (and possibly drop names)
    ai_cfg = cfg.get("ai", {})
    ai_trade_report = None
    if bool(ai_cfg.get("trade_enabled", False)) and target:
        try:
            model = str(ai_cfg.get("trade_model", ai_cfg.get("model", "gpt-4.1-mini")))
            api_key_env = str(ai_cfg.get("api_key_env", "OPENAI_API_KEY"))
            cand_map = {str(x.get("code")).zfill(4): x for x in (picks_payload.get("picks") or [])}
            candidates = [cand_map.get(c, {"code": c}) for c in target]
            res = analyze_trade_plan(
                asof=trade_date,
                candidates=candidates,
                positions=positions if 'positions' in locals() else (pf.get("positions") or {}),
                top_k=top_k,
                model=model,
                api_key_env=api_key_env,
            )
            if res and res.get("codes"):
                target = [c for c in res["codes"] if c in target]
                ai_trade_report = res
                (paper_dir() / f"ai-trade-{trade_date}.json").write_text(
                    json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        except Exception:
            pass

    # Prevent double-run same day
    if (not args.force) and pf.get("last_trade_date") == trade_date:
        print(f"Already traded for {trade_date}")
        return 0

    positions: dict[str, dict] = pf.get("positions") or {}
    held_codes = sorted(list(positions.keys()))

    universe_codes = sorted(list(set(held_codes + target)))

    prices: dict[str, float] = {}
    if price_source == "yahoo_jp":
        ycfg = cfg.get("yahoo_jp", {})
        tpl = str(ycfg.get("symbol_template", "{code}.T"))
        timeout_sec = float(ycfg.get("timeout_sec", 15))
        throttle_sec = float(ycfg.get("throttle_sec", 0.3))
        use_forum_page = bool(ycfg.get("use_forum_page", True))
        fallback_local = bool(pt.get("fallback_local", True))
        local_field = str(pt.get("local_price_field", "close"))
        fallback_pick_close = bool(pt.get("fallback_pick_close", True))
        prices = fetch_prices_yahoo(
            universe_codes,
            tpl,
            timeout_sec,
            throttle_sec,
            use_forum_page=use_forum_page,
            fallback_local=fallback_local,
            local_field=local_field,
            fallback_pick_close=fallback_pick_close,
            pick_close_map=pick_close_map,
        )
    else:
        raise RuntimeError(f"Unsupported price_source: {price_source}")

    trades_made = 0

    # SELL: anything not in target
    cash = float(pf.get("cash", 0.0))
    for code in list(positions.keys()):
        if code in target:
            continue
        qty = int(positions[code]["qty"])
        px = prices.get(code)
        if not px:
            continue
        notional = qty * float(px)
        cash += notional
        append_trade({
            "date": trade_date,
            "code": code,
            "side": "SELL",
            "qty": qty,
            "price": float(px),
            "notional": float(notional),
            "reason": "rebalance_out",
        })
        trades_made += 1
        positions.pop(code, None)

    # BUY/ADJUST: equal-weight target
    # Compute current equity using available prices
    holdings_value = 0.0
    for code, pos in positions.items():
        px = prices.get(code)
        if px:
            holdings_value += int(pos["qty"]) * float(px)
    equity = cash + holdings_value
    if equity <= 0:
        print("Equity <= 0")
        return 1

    target_value_each = equity / max(1, len(target))

    # First, compute desired qty for each target
    desired_qty: dict[str, int] = {}
    for code in target:
        px = prices.get(code)
        if not px:
            continue
        qty = int(target_value_each // float(px))
        # enforce lot size
        qty = (qty // lot_size) * lot_size
        if qty == 0 and buy_min_lot_if_affordable:
            # if equal-weight is too small for one lot, still buy one lot if we can
            if (lot_size * float(px)) <= equity:
                qty = lot_size
        desired_qty[code] = max(0, qty)

    # Then, execute buys/sells to reach desired
    for code in target:
        px = prices.get(code)
        if not px:
            continue
        want = int(desired_qty.get(code, 0))
        have = int(positions.get(code, {}).get("qty", 0))
        delta = want - have
        if delta == 0:
            continue

        if delta < 0:
            sell_qty = -delta
            notional = sell_qty * float(px)
            cash += notional
            append_trade({
                "date": trade_date,
                "code": code,
                "side": "SELL",
                "qty": sell_qty,
                "price": float(px),
                "notional": float(notional),
                "reason": "rebalance_trim",
            })
            trades_made += 1
            positions[code]["qty"] = have - sell_qty
        else:
            buy_qty = delta
            cost = buy_qty * float(px)
            if cost > cash:
                # downscale to available cash
                buy_qty = int(cash // float(px))
                buy_qty = (buy_qty // lot_size) * lot_size
                cost = buy_qty * float(px)
            if buy_qty <= 0:
                continue
            cash -= cost
            # update avg cost
            if code in positions:
                old_qty = int(positions[code]["qty"])
                old_cost = float(positions[code]["avg_cost"])
                new_qty = old_qty + buy_qty
                new_avg = (old_qty * old_cost + buy_qty * float(px)) / max(1, new_qty)
                positions[code]["qty"] = new_qty
                positions[code]["avg_cost"] = float(new_avg)
            else:
                positions[code] = {"qty": int(buy_qty), "avg_cost": float(px)}

            append_trade({
                "date": trade_date,
                "code": code,
                "side": "BUY",
                "qty": buy_qty,
                "price": float(px),
                "notional": float(cost),
                "reason": "rebalance_in",
            })
            trades_made += 1

    if trades_made == 0:
        # Write an explicit no-op trade so the UI can show "当日交易".
        append_trade({
            "date": trade_date,
            "code": "-",
            "side": "HOLD",
            "qty": 0,
            "price": 0.0,
            "notional": 0.0,
            "reason": "no_change",
        })

    # Equity snapshot at end
    holdings_value = 0.0
    for code, pos in positions.items():
        px = prices.get(code)
        if px:
            holdings_value += int(pos["qty"]) * float(px)
    total = cash + holdings_value
    append_equity({"date": trade_date, "cash": cash, "holdings_value": holdings_value, "total": total})

    pf["cash"] = float(cash)
    pf["positions"] = positions
    pf["last_trade_date"] = trade_date
    save_portfolio(pf)

    print(f"Paper trade done for {trade_date}. positions={len(positions)} cash={cash:.0f} total={total:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

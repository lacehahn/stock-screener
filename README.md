# nikkei-stock-screener

Scan Japanese equities after market close, rank candidates with a rules-based technical strategy, and generate a daily report with top 10 picks + suggested entry/exit levels.

## What it does
- Universe: local `universe.csv` (default). You can populate it with **Nikkei 225** constituents.
- Data: daily OHLCV via **Stooq** (free, no key) by default
- Strategy: technical analysis (momentum + trend + liquidity + risk)
- Output: Markdown report in `reports/` + CSV details in `reports/data/`
- Can be scheduled to run daily.

## Not investment advice
This is a technical screener for educational purposes.

## Setup
```bash
cd /home/lance/clawd/nikkei-stock-screener
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run (one-shot)
```bash
python run_daily.py --asof auto
```

## Config
Edit `config.yaml`.

## Schedule
Use OpenClaw cron (recommended) or your system cron.

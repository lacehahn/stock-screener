from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .strategy import Pick


def write_picks_json(out_dir: Path, picks: list[Pick], asof: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "asof": asof,
        "picks": [asdict(p) for p in picks],
    }
    p = out_dir / f"nikkei-picks-{asof}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = out_dir / "latest_picks.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p

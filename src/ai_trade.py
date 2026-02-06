from __future__ import annotations

"""AI trade adjustment (best-effort).

Given today's candidate list (TopK) and current positions, ask the LLM to:
- reorder candidates
- optionally drop some (if low quality)
- provide a short Chinese rationale

This is intentionally simple and cost-controlled.
"""

import json
import os
from typing import Any

import requests


def _env_key(env_name: str) -> str | None:
    v = os.environ.get(env_name)
    return v if v and v.strip() else None


def analyze_trade_plan(
    *,
    asof: str,
    candidates: list[dict[str, Any]],
    positions: dict[str, Any],
    top_k: int,
    model: str,
    api_key_env: str = "OPENAI_API_KEY",
    timeout: int = 35,
) -> dict[str, Any] | None:
    key = _env_key(api_key_env)
    if not key:
        return None

    prompt = {
        "role": "user",
        "content": [
            {
                "type": "input_text",
                "text": (
                    "你是日股的盘前交易复核助手。\n"
                    "我会给你：候选标的列表（来自昨日日终策略输出，含 score/entry/stop/tp/ai_score/summary 等）以及当前持仓。\n"
                    "你的任务：\n"
                    "1) 给出今天要交易的标的顺序（最多 top_k 个），输出一个 codes 数组（4位代码字符串）。\n"
                    "2) 如你认为某些标的不适合今天执行，可从名单中剔除。\n"
                    "3) 用中文给 3~6 条要点作为 rationale。\n"
                    "约束：不要编造新闻；只基于输入信息做复核；输出必须是 JSON。\n"
                    f"交易日：{asof}，top_k={top_k}\n"
                ),
            },
            {
                "type": "input_text",
                "text": "输入数据(JSON)：\n"
                + json.dumps(
                    {
                        "asof": asof,
                        "top_k": top_k,
                        "candidates": candidates,
                        "positions": positions,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }

    payload = {
        "model": model,
        "input": [prompt],
        "max_output_tokens": 300,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "trade_plan",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "codes": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["codes", "rationale"],
                },
            }
        },
    }

    try:
        r = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    out_text = ""
    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text":
                out_text += c.get("text", "")

    if not out_text:
        return None

    try:
        obj = json.loads(out_text)
    except Exception:
        return None

    codes = obj.get("codes") or []
    if not isinstance(codes, list):
        codes = []
    obj["codes"] = [str(x).zfill(4) for x in codes][: int(top_k)]

    rationale = obj.get("rationale") or []
    if not isinstance(rationale, list):
        rationale = []
    obj["rationale"] = [str(x) for x in rationale][:8]

    return obj

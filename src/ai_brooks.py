from __future__ import annotations

"""AI-assisted Brooks-style price action interpretation.

Uses OpenAI Responses API if OPENAI_API_KEY is set.
We keep this best-effort and cost-controlled:
- Analyze only a small number of candidates (e.g. top 20)
- Use compact features rather than full raw history when possible

Returns a dict with:
- ai_score: 0..1
- summary_zh: short Chinese explanation
- setup_tags: list[str]

Important: do NOT store API keys in code/config.
"""

import json
import os
from typing import Any

import requests


def _env_key(env_name: str) -> str | None:
    v = os.environ.get(env_name)
    return v if v and v.strip() else None


def analyze_brooks(
    code: str,
    name: str | None,
    ohlcv: list[dict[str, Any]],
    *,
    model: str,
    api_key_env: str = "OPENAI_API_KEY",
    timeout: int = 35,
) -> dict[str, Any] | None:
    key = _env_key(api_key_env)
    if not key:
        return None

    # Keep last 120 bars max
    bars = ohlcv[-120:]

    # Ensure JSON-serializable (convert Timestamp/date)
    for b in bars:
        if "date" in b and b["date"] is not None:
            b["date"] = str(b["date"])[:10]

    prompt = {
        "role": "user",
        "content": [
            {
                "type": "input_text",
                "text": (
                    "你是精通 Al Brooks Price Action 的交易分析师。\n"
                    "请基于给定的【日线 OHLCV】数据，给出：\n"
                    "1) 市场环境判断（趋势/通道/交易区间）\n"
                    "2) 近期最关键的价格行为信号（例如：二次入场、楔形、双顶/双底、突破/失败突破等）\n"
                    "3) 给一个 0~1 的可交易性评分（ai_score），越高越值得关注\n"
                    "4) 用中文写 2~3 句摘要（summary_zh），并给 3~6 个 setup_tags\n\n"
                    "要求：不要编造新闻，不要使用未来信息；只基于提供的数据。\n"
                    f"标的：{code} {name or ''}\n"
                ),
            },
            {
                "type": "input_text",
                "text": "数据（JSON，按时间升序，字段 date/open/high/low/close/volume）：\n" + json.dumps(bars, ensure_ascii=False),
            },
        ],
    }

    payload = {
        "model": model,
        "input": [prompt],
        "max_output_tokens": 350,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "brooks_pa_analysis",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "ai_score": {"type": "number"},
                        "summary_zh": {"type": "string"},
                        "setup_tags": {"type": "array", "items": {"type": "string"}},
                        "context": {"type": "string"},
                    },
                    "required": ["ai_score", "summary_zh", "setup_tags", "context"],
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

    # Extract JSON output
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

    # clamp score
    try:
        s = float(obj.get("ai_score"))
        obj["ai_score"] = max(0.0, min(1.0, s))
    except Exception:
        obj["ai_score"] = 0.5

    # normalize tags length
    tags = obj.get("setup_tags") or []
    if isinstance(tags, list):
        obj["setup_tags"] = [str(x) for x in tags][:6]
    else:
        obj["setup_tags"] = []

    return obj

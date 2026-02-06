from __future__ import annotations

import datetime as dt
from pathlib import Path

from .strategy import Pick


def render_markdown(picks: list[Pick], asof: str, *, ai_trade: dict | None = None) -> str:
    lines: list[str] = []

    lines.append(f"# 日经股票筛选报告（{asof}）")
    lines.append("")
    lines.append("> **声明：非投资建议。以下为基于历史日线数据的技术面筛选与价位参考。**")
    lines.append("")

    lines.append("## 如何阅读（快速）")
    lines.append("- **Entry（买入）**：突破触发价位（近 20 日高点 + 少量 ATR 缓冲）。")
    lines.append("- **Stop（止损）**：风险控制价位（Entry − 2.5×ATR）。")
    lines.append("- **TP（止盈）**：目标价位（按 RR=2.0 计算）。")
    lines.append("")

    if not picks:
        lines.append("## 今日结果")
        lines.append("")
        lines.append("（今日无符合过滤条件的标的。你可以在 `config.yaml` 放宽过滤条件或降低流动性门槛后重试。）")
        return "\n".join(lines)

    # --- Executive summary
    lines.append("## 今日 Top10 概览（综合：动量/趋势/波动 + Brooks + AI）")
    lines.append("")
    lines.append("下面是 Top10 的**一行摘要**（便于快速扫一遍）：")
    lines.append("")
    for i, p in enumerate(picks, 1):
        name = f" {p.name}" if p.name else ""
        ai_part = f"｜AI **{p.ai_score:.2f}**" if getattr(p, "ai_score", 0) else ""
        br_part = f"｜Brooks **{p.brooks_score:.2f}**" if getattr(p, "brooks_score", 0) else ""
        lines.append(
            f"{i}. **{p.code}**{name}｜Entry **{p.entry:.0f}**｜Stop **{p.stop:.0f}**｜TP **{p.take_profit:.0f}**｜Score **{p.score:.3f}**{br_part}{ai_part}"
        )
    lines.append("")

    # --- AI trade review section (pre-market)
    if ai_trade:
        lines.append("## AI 交易复核（盘前 / 执行前）")
        lines.append("")
        codes = ai_trade.get("codes") or []
        if codes:
            lines.append("- AI 建议执行顺序：" + " → ".join([str(x) for x in codes]))
        rat = ai_trade.get("rationale") or []
        if rat:
            lines.append("- 复核要点：")
            for it in rat:
                lines.append(f"  - {it}")
        lines.append("")

    # --- AI monitor section
    has_ai = any(getattr(p, "ai_summary_zh", None) for p in picks)
    if has_ai:
        lines.append("## AI 盯盘摘要（盘后复核）")
        lines.append("")
        lines.append("下面是 AI 对 Top10 的盘后复核摘要（仅基于 OHLCV，不包含新闻）。")
        lines.append("")
        for i, p in enumerate(picks, 1):
            if getattr(p, "ai_summary_zh", None):
                lines.append(f"- **{p.code}**｜AI **{p.ai_score:.2f}**：{p.ai_summary_zh}")
        lines.append("")

    # --- Brooks section
    lines.append("## Brooks 小结（规则 + AI）")
    lines.append("")
    lines.append("- 规则 Brooks（proxy）用于提供可计算的价格行为上下文近似。")
    lines.append("- AI Brooks 用于对候选标的做更接近“读盘”的解释与复核（仅基于 OHLCV，不包含新闻）。")
    lines.append("")

    # --- Details
    lines.append("## 详细说明")
    lines.append("")

    def _tr(s: str) -> str:
        rr = s.replace("Close above EMA50", "收盘价高于 EMA50")
        rr = rr.replace("Close below EMA50", "收盘价低于 EMA50")
        rr = rr.replace("63D momentum", "63日动量")
        rr = rr.replace("126D momentum", "126日动量")
        rr = rr.replace("20D vol", "20日波动率")
        return rr

    for i, p in enumerate(picks, 1):
        title = f"{i}. {p.code}" + (f" — {p.name}" if p.name else "")
        lines.append(f"### {title}")
        lines.append("")

        # 一句话结论
        mom = [x for x in p.reasons if "momentum" in x.lower() or "动量" in x]
        trend = [x for x in p.reasons if "EMA" in x]
        vol = [x for x in p.reasons if "vol" in x.lower() or "波动率" in x]

        mom_s = _tr(mom[0]) if mom else "动量：—"
        trend_s = _tr(trend[0]) if trend else "趋势：—"
        vol_s = _tr(vol[0]) if vol else "波动：—"
        lines.append(f"**一句话结论：** {mom_s}；{trend_s}；{vol_s}。")
        lines.append("")

        # AI解读
        if getattr(p, "ai_summary_zh", None):
            lines.append("**AI 解读（Brooks 视角）**")
            lines.append("")
            lines.append(f"> {p.ai_summary_zh}")
            if getattr(p, "ai_setup_tags", None):
                lines.append("")
                lines.append("- setup_tags：" + "、".join([str(x) for x in (p.ai_setup_tags or [])]))
            lines.append("")

        # Key numbers as a small table
        lines.append("| 指标 | 数值 |")
        lines.append("|---|---:|")
        lines.append(f"| 评分 | {p.score:.4f} |")
        lines.append(f"| 最新收盘价 | {p.close:.2f} 日元 |")
        lines.append(f"| Entry（建议买入） | **{p.entry:.2f}** 日元 |")
        lines.append(f"| Stop（建议止损） | **{p.stop:.2f}** 日元 |")
        lines.append(f"| TP（建议止盈） | **{p.take_profit:.2f}** 日元 |")
        lines.append("")

        # 按主题分段
        lines.append("**推荐理由（按主题）**")
        lines.append("")

        def bullet(title_: str, items: list[str]) -> None:
            lines.append(f"- **{title_}**")
            if not items:
                lines.append("  - （无）")
            else:
                for it in items:
                    lines.append(f"  - {_tr(it)}")

        bullet("动量", [x for x in p.reasons if "momentum" in x.lower() or "动量" in x])
        bullet("趋势", [x for x in p.reasons if "EMA" in x])
        bullet("波动/风险", [x for x in p.reasons if "vol" in x.lower() or "波动率" in x])

        lines.append("")
        lines.append("---")
        lines.append("")

    # Remove last divider for neatness
    while lines and lines[-1] == "":
        lines.pop()
    if lines and lines[-1] == "---":
        lines.pop()

    return "\n".join(lines)


def _to_html(md: str, title: str) -> str:
    try:
        import markdown as mdlib

        body = mdlib.markdown(
            md,
            extensions=["tables", "fenced_code"],
            output_format="html5",
        )
    except Exception:
        # Fallback: plain text
        body = "<pre>" + (md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")) + "</pre>"

    css = """
    :root { color-scheme: dark; }
    body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background: #0b0b0f; color: #e5e7eb; }
    .wrap { max-width: 920px; margin: 0 auto; padding: 28px 18px 60px; }
    .doc { background: rgba(24,24,27,.6); border: 1px solid #27272a; border-radius: 14px; padding: 18px 18px 8px; }
    .doc h1 { font-size: 22px; margin: 6px 0 14px; }
    .doc h2 { font-size: 16px; margin: 22px 0 10px; }
    .doc h3 { font-size: 14px; margin: 18px 0 8px; padding-top: 8px; border-top: 1px dashed #2a2a2e; }
    .doc p, .doc li { line-height: 1.55; }
    .doc blockquote { margin: 12px 0; padding: 10px 14px; border-left: 3px solid #3f3f46; background: rgba(0,0,0,.25); border-radius: 10px; }
    .doc table { width: 100%; border-collapse: collapse; margin: 10px 0 14px; }
    .doc th, .doc td { border: 1px solid #2a2a2e; padding: 8px 10px; }
    .doc th { background: rgba(0,0,0,.25); text-align: left; }
    .doc hr { border: 0; border-top: 1px solid #2a2a2e; margin: 18px 0; }
    /* “color” accents */
    strong { color: #f9fafb; }
    a { color: #93c5fd; }
    code { background: rgba(0,0,0,.35); padding: 2px 6px; border-radius: 8px; }
    """

    return f"""<!doctype html>
<html lang=\"zh\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <style>{css}</style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"doc\">
      {body}
    </div>
  </div>
</body>
</html>"""


def write_report(out_dir: Path, content_md: str, asof: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"nikkei-report-{asof}.md"
    md_path.write_text(content_md, encoding="utf-8")

    # Also write HTML version for better readability (colors/typography)
    html_path = out_dir / f"nikkei-report-{asof}.html"
    html_path.write_text(_to_html(content_md, f"日经股票筛选报告（{asof}）"), encoding="utf-8")

    return md_path

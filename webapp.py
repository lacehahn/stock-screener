#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from flask import Flask, abort, render_template_string, send_from_directory, request

APP_DIR = Path(__file__).resolve().parent
REPORTS_DIR = APP_DIR / "reports"

app = Flask(__name__)

INDEX_TMPL = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>日经筛选器</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }
    pre { white-space: pre-wrap; line-height: 1.35; }
    .muted { color: #666; }
    .row { display:flex; gap: 12px; flex-wrap: wrap; margin: 12px 0; }
    button { padding: 8px 12px; }
    code { background: #f3f3f3; padding: 2px 4px; }
  </style>
</head>
<body>
  <h1>日经筛选器（WSL Web App）</h1>
  <p class="muted">展示最新报告，并提供简单管理入口（本机使用为主）。</p>

  <div class="row">
    <a href="/latest">查看最新报告（纯文本）</a>
    <a href="/files">列出历史报告文件</a>
    <a href="/admin">管理</a>
  </div>

  <h2>最新报告</h2>
  <pre>{{ content }}</pre>
</body>
</html>"""

ADMIN_TMPL = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>管理 - 日经筛选器</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }
    .muted { color:#666; }
    .box { border:1px solid #ddd; padding: 12px; margin: 12px 0; }
    input { padding: 6px; width: 340px; }
    button { padding: 8px 12px; }
    pre { white-space: pre-wrap; }
  </style>
</head>
<body>
  <h1>管理</h1>
  <p class="muted">提示：可通过设置环境变量 <code>ADMIN_TOKEN</code> 启用简单鉴权（推荐）。</p>

  <div class="box">
    <h2>运行任务</h2>
    <form method="post" action="/admin/run">
      <div>
        <label>Token（可选）：</label>
        <input name="token" placeholder="如果设置了 ADMIN_TOKEN，请在这里输入" />
      </div>
      <div style="margin-top:10px;">
        <button name="action" value="update_universe">更新日经225成分股列表</button>
        <button name="action" value="run_daily">立即生成报告（一次）</button>
      </div>
    </form>
  </div>

  <div class="box">
    <h2>状态</h2>
    <pre>{{ status }}</pre>
  </div>

  <p><a href="/">返回首页</a></p>
</body>
</html>"""


@app.get("/")
def index():
    latest = REPORTS_DIR / "latest.md"
    content = latest.read_text(encoding="utf-8") if latest.exists() else "(no report yet)"
    return render_template_string(INDEX_TMPL, content=content)


@app.get("/latest")
def latest():
    p = REPORTS_DIR / "latest.md"
    if not p.exists():
        abort(404)
    return p.read_text(encoding="utf-8"), 200, {"Content-Type": "text/plain; charset=utf-8"}


def _check_token(token: str | None) -> bool:
    required = os.environ.get("ADMIN_TOKEN")
    if not required:
        return True  # no auth configured
    return (token or "") == required


def _status_text() -> str:
    latest = REPORTS_DIR / "latest.md"
    uni = APP_DIR / "universe.csv"
    uni_rows = 0
    if uni.exists():
        try:
            uni_rows = sum(1 for _ in uni.open("r", encoding="utf-8")) - 1
        except Exception:
            uni_rows = 0
    return "\n".join([
        f"latest.md: {'OK' if latest.exists() else 'MISSING'}",
        f"universe.csv rows: {uni_rows}",
        f"reports dir: {REPORTS_DIR}",
    ])


@app.get("/files")
def files():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted([x.name for x in REPORTS_DIR.glob("nikkei-report-*.md")], reverse=True)
    out = "\n".join(files) + "\n"
    return out, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.get("/admin")
def admin():
    return render_template_string(ADMIN_TMPL, status=_status_text())


@app.post("/admin/run")
def admin_run():
    token = request.form.get("token")
    if not _check_token(token):
        return "unauthorized\n", 401

    action = request.form.get("action")
    if action == "update_universe":
        rc = os.system(f"{APP_DIR}/.venv/bin/python {APP_DIR}/update_universe.py")
        return ("OK\n" if rc == 0 else f"FAILED (rc={rc})\n"), 200

    if action == "run_daily":
        rc = os.system(f"{APP_DIR}/.venv/bin/python {APP_DIR}/run_daily.py")
        return ("OK\n" if rc == 0 else f"FAILED (rc={rc})\n"), 200

    return "unknown action\n", 400


@app.get("/files/<path:fname>")
def get_file(fname: str):
    return send_from_directory(REPORTS_DIR, fname)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8787"))
    app.run(host=host, port=port)

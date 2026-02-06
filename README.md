# nikkei-stock-screener

日经（Nikkei 225）日线筛选 + 模拟盘（Paper Trading）+ 中文报告（HTML Dashboard）。

> 声明：非投资建议。本项目仅用于研究/演示。

## 功能概览

### 1) 收盘后筛选（15:30 JST）
- Universe：`universe.csv`（日经225成分，来自 stooq constituents 抓取脚本）
- 数据：**日线 OHLCV**
  - 推荐模式：`data.provider=localcsv`（只读本地缓存 CSV，不访问 Stooq，稳定）
  - 首次建缓存：可短时间用热点/IP 运行一次 Stooq 抓取以填充 `data_cache/`
- 策略：
  - 技术面打分（动量/趋势/波动惩罚/流动性过滤）
  - Brooks 规则 proxy（价格行为特征）
  - **AI Brooks（可选）**：盘后“盯盘式”复核，输出 `ai_score + 中文摘要 + tags`，并作为排序因子加入总分
- 输出：
  - `reports/nikkei-report-YYYY-MM-DD.html`（前端 iframe 显示）
  - `reports/nikkei-report-YYYY-MM-DD.md`
  - `reports/nikkei-picks-YYYY-MM-DD.json`（供模拟盘/前端读取）
  - `reports/latest.*`（稳定指针）

### 2) 模拟盘（Paper Trading，9:30 JST）
- T+1 思路：使用昨日日终 picks，第二天早上执行
- 默认：TopK（可配置），每日再平衡
- 成交价：抓取 Yahoo Japan HTML（`/quote/{code}.T/forum`）解析当前价
- 交易记录：
  - `paper/portfolio.json`
  - `paper/trades.csv`（含 JST 时间戳 `ts`）
  - `paper/equity.csv`
- **AI 交易复核（可选）**：交易执行前把候选 + 当前持仓发给 AI，让 AI 调整执行顺序/剔除并输出 rationale
  - 输出：`paper/ai-trade-YYYY-MM-DD.json`
  - 收盘报告会自动把该复核结果写入当日 HTML

### 3) Web Dashboard（Next.js）
- 地址：`http://localhost:8790`
- 功能：Top10 列表、K线/预测、新闻、报告（HTML）、模拟盘页面
- **历史报告按日期选择**：UI 顶部可选择日期查看对应报告与 picks
- 图表数据：`/api/price/[code]` **只读本地 `data_cache/`**（不访问 Stooq）

---

## 安装

```bash
cd /home/lance/clawd/nikkei-stock-screener
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd web-next
npm install
```

## 配置

编辑 `config.yaml`。

关键配置示例：
- 使用本地 CSV（不访问 Stooq）：
  ```yaml
  data:
    provider: localcsv
  ```
- AI（需要 OpenAI Key + 账户有余额）：
  ```yaml
  ai:
    enabled: true
    api_key_env: OPENAI_API_KEY
  ```

### OpenAI Key
推荐放在项目 `.env`（不会提交）：
```env
OPENAI_API_KEY=sk-...
```

---

## 运行

### 1) 收盘后生成报告
```bash
cd /home/lance/clawd/nikkei-stock-screener
source .venv/bin/activate
python run_daily.py --asof auto
```

### 2) 执行模拟盘交易
```bash
cd /home/lance/clawd/nikkei-stock-screener
source .venv/bin/activate
python paper_trade.py --date auto
```

（用于测试同一天重复执行）
```bash
python paper_trade.py --force --date auto
```

### 3) 启动前端
```bash
cd /home/lance/clawd/nikkei-stock-screener/web-next
npm run dev -- --hostname 0.0.0.0 --port 8790
```

---

## 定时（建议）
- 09:30 JST（工作日）：`paper_trade.py`
- 15:30 JST（工作日）：`run_daily.py`

可用 OpenClaw cron 或系统 cron。

---

## 备注
- `reports/` 默认不提交 Git（本地产物）
- `data_cache/`、`paper/`、`.trash/` 都不应提交（本地数据）

"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
// markdown deps removed (using HTML iframe)

const CandleChart = dynamic(() => import("@/components/CandleChart"), { ssr: false });

import RiskRewardBar from "@/components/RiskRewardBar";

type Pick = {
  rank: number;
  code: string;
  name?: string;
  score?: number;
  close?: number;
  entry?: number;
  stop?: number;
  takeProfit?: number;
  reasons?: string[];
};

type NewsItem = { title: string; link: string; pubDate: string; source?: string };

type Candle = { date: string; open: number; high: number; low: number; close: number; volume: number };

type ForecastPoint = { date: string; close: number };

type Panel = "report" | "chart" | "news" | "paper";

function CardTab({
  active,
  title,
  desc,
  onClick,
}: {
  active: boolean;
  title: string;
  desc: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-xl border p-4 text-left transition hover:bg-zinc-800/40 ${
        active ? "border-zinc-600 bg-zinc-900/60" : "border-zinc-800 bg-zinc-900/30"
      }`}
    >
      <div className="text-sm font-medium text-zinc-100">{title}</div>
      <div className="mt-1 text-xs text-zinc-400">{desc}</div>
    </button>
  );
}

export default function Home() {
  const [md, setMd] = useState<string>("");

  const [einkMode, setEinkMode] = useState<boolean>(false);
  const [reportHtmlUrl, setReportHtmlUrl] = useState<string>("/api/report/latest.html");
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [picks, setPicks] = useState<Pick[]>([]);
  const [selected, setSelected] = useState<Pick | null>(null);

  const [panel, setPanel] = useState<Panel>("chart");

  const [paperStrategy, setPaperStrategy] = useState<string>("");
  const [paperSummary, setPaperSummary] = useState<Record<string, unknown> | null>(null);

  const [news, setNews] = useState<NewsItem[]>([]);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);
  const [forecastMethod, setForecastMethod] = useState<string>("");
  const [showLevels, setShowLevels] = useState<boolean>(true);

  const withEink = (url: string) => {
    if (!einkMode) return url;
    return url.includes("?") ? `${url}&mode=eink` : `${url}?mode=eink`;
  };

  useEffect(() => {
    try {
      const saved = localStorage.getItem("einkMode");
      if (saved === "1") setEinkMode(true);
    } catch {}

    (async () => {
      const r = await fetch("/api/report/latest");
      const j = await r.json();
      if (j.ok) setMd(j.markdown);
    })();
    (async () => {
      const r = await fetch("/api/report/picks");
      const j = await r.json();
      if (j.ok) {
        setPicks(j.picks);
        setSelected(j.picks?.[0] ?? null);
      }
    })();
    (async () => {
      const r = await fetch("/api/report/dates");
      const j = await r.json();
      if (j.ok) {
        setAvailableDates(j.dates ?? []);
        if ((j.dates ?? []).length > 0) {
          setSelectedDate(j.dates[0]);
          setReportHtmlUrl(withEink(`/api/report/html/${j.dates[0]}`));
        } else {
          setReportHtmlUrl(withEink("/api/report/latest.html"));
        }
      }
    })();
    (async () => {
      const r = await fetch("/api/paper/strategy");
      const j = await r.json();
      if (j.ok) setPaperStrategy(j.strategyZh ?? "");
    })();
    (async () => {
      const r = await fetch("/api/paper/summary");
      const j = await r.json();
      if (j.ok) setPaperSummary(j);
    })();
  }, []);

  useEffect(() => {
    // keep report iframe in sync with eink toggle
    if (selectedDate) setReportHtmlUrl(withEink(`/api/report/html/${selectedDate}`));
    else setReportHtmlUrl(withEink("/api/report/latest.html"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [einkMode]);

  useEffect(() => {
    if (!selected) return;

    (async () => {
      const r = await fetch(`/api/news/${selected.code}`);
      const j = await r.json();
      setNews(j.ok ? j.news : []);
    })();

    (async () => {
      const r = await fetch(`/api/price/${selected.code}`);
      const j = await r.json();
      setCandles(j.ok ? j.series : []);
    })();

    (async () => {
      const r = await fetch(`/api/predict/${selected.code}`);
      const j = await r.json();
      setForecast(j.ok ? j.forecast : []);
      setForecastMethod(j.method ?? "");
    })();
  }, [selected?.code]);

  const title = useMemo(() => {
    const m = md.match(/^#\s+(.+)$/m);
    return m ? m[1] : "日经筛选器";
  }, [md]);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <header className="flex flex-col gap-2">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
              <p className="text-sm text-zinc-400">Dashboard：Top10 筛选 + 报告 / K线与预测 / 新闻</p>
            </div>

            <div className="flex items-center gap-2">
              <button
                className={`rounded-lg border px-2 py-1 text-xs transition ${
                  einkMode
                    ? "border-zinc-500 bg-zinc-100 text-zinc-900"
                    : "border-zinc-800 bg-zinc-900/40 text-zinc-200 hover:bg-zinc-800/40"
                }`}
                onClick={() => {
                  const next = !einkMode;
                  setEinkMode(next);
                  try {
                    localStorage.setItem("einkMode", next ? "1" : "0");
                  } catch {}
                }}
                title="墨水屏阅读模式（报告 iframe 加白底/黑字/去色）"
              >
                墨水屏
              </button>

              <div className="text-xs text-zinc-400">报告日期</div>
              <select
                className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-2 py-1 text-xs text-zinc-200"
                value={selectedDate}
                onChange={async (e) => {
                  const d = e.target.value;
                  setSelectedDate(d);
                  setReportHtmlUrl(withEink(`/api/report/html/${d}`));
                  const r = await fetch(`/api/report/picks/${d}`);
                  const j = await r.json();
                  if (j.ok) {
                    setPicks(j.picks);
                    setSelected(j.picks?.[0] ?? null);
                  }
                }}
              >
                {availableDates.length === 0 ? <option value="">（无历史报告）</option> : null}
                {availableDates.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </header>

        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Left: picks (keep simple) */}
          <aside className="lg:col-span-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-zinc-200">Top10（点击切换）</h2>
              <a className="text-xs text-zinc-400 hover:text-zinc-200" href="/api/report/latest" target="_blank">
                原始报告
              </a>
            </div>

            <div className="mt-3 space-y-2">
              {picks.map((p) => (
                <button
                  key={p.code}
                  onClick={() => setSelected(p)}
                  className={`w-full rounded-lg border px-3 py-2 text-left transition hover:bg-zinc-800/50 ${
                    selected?.code === p.code ? "border-zinc-600 bg-zinc-800/60" : "border-zinc-800"
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="font-medium">
                      {p.rank}. {p.code} <span className="text-zinc-400">{p.name ?? ""}</span>
                    </div>
                    <div className="text-xs text-zinc-400">score {p.score?.toFixed(3) ?? "-"}</div>
                  </div>
                  <div className="mt-2">
                    <RiskRewardBar entry={p.entry} stop={p.stop} takeProfit={p.takeProfit} />
                  </div>
                </button>
              ))}
              {picks.length === 0 ? <div className="text-sm text-zinc-500">暂无 Top10（先生成一次日终报告）</div> : null}
            </div>
          </aside>

          {/* Right */}
          <main className="lg:col-span-8 space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
              <CardTab active={panel === "chart"} title="K线 + 预测" desc="同图叠加" onClick={() => setPanel("chart")} />
              <CardTab active={panel === "news"} title="新闻" desc="公司名+代码匹配" onClick={() => setPanel("news")} />
              <CardTab active={panel === "report"} title="报告" desc="文档化段落" onClick={() => setPanel("report")} />
              <CardTab active={panel === "paper"} title="模拟盘" desc="T+1 每日再平衡" onClick={() => setPanel("paper")} />
            </div>

            {panel === "chart" ? (
              <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                <div className="flex items-end justify-between gap-4">
                  <div>
                    <h2 className="text-sm font-medium text-zinc-200">K线 + 预测</h2>
                    <p className="mt-1 text-xs text-zinc-400">
                      {selected ? `${selected.code} ${selected.name ?? ""}` : "请选择一只股票"}
                      {forecastMethod ? ` · 预测方法：${forecastMethod}` : ""}
                    </p>
                  </div>
                  <div className="text-xs text-zinc-400">蓝线=预测（未来10天）</div>
                </div>

                <div className="mt-4 flex items-center justify-between gap-3">
                  <div className="text-xs text-zinc-400">显示价位横线（Entry/Stop/TP）</div>
                  <label className="flex items-center gap-2 text-xs text-zinc-200">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-sky-400"
                      checked={showLevels}
                      onChange={(e) => setShowLevels(e.target.checked)}
                    />
                    显示
                  </label>
                </div>

                <div className="mt-3">
                  <CandleChart
                    candles={candles.map((c) => ({ ...c }))}
                    forecast={forecast}
                    entry={showLevels ? selected?.entry : undefined}
                    stop={showLevels ? selected?.stop : undefined}
                    takeProfit={showLevels ? selected?.takeProfit : undefined}
                  />
                </div>
              </section>
            ) : null}

            {panel === "news" ? (
              <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                <h2 className="text-sm font-medium text-zinc-200">相关新闻（最近）</h2>
                <p className="mt-1 text-xs text-zinc-400">点击打开新闻源站。</p>

                <div className="mt-3 space-y-2">
                  {news.map((n) => (
                    <a
                      key={n.link}
                      href={n.link}
                      target="_blank"
                      rel="noreferrer"
                      className="block rounded-lg border border-zinc-800 px-3 py-2 hover:bg-zinc-800/40"
                    >
                      <div className="text-sm text-zinc-100">{n.title}</div>
                      <div className="mt-1 text-xs text-zinc-400">
                        {n.source ? `${n.source} · ` : ""}
                        {n.pubDate}
                      </div>
                    </a>
                  ))}
                  {news.length === 0 ? <div className="text-sm text-zinc-500">暂无新闻或获取失败</div> : null}
                </div>
              </section>
            ) : null}

            {panel === "report" ? (
              <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                <h2 className="text-sm font-medium text-zinc-200">报告正文（HTML）</h2>
                <p className="mt-1 text-xs text-zinc-400">报告由日终任务生成 HTML（更稳定的排版/颜色）。</p>

                <div className="mt-3 overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/30">
                  <iframe
                    src={reportHtmlUrl}
                    className="h-[70vh] w-full"
                    sandbox="allow-same-origin"
                    title="report"
                  />
                </div>
              </section>
            ) : null}

            {panel === "paper" ? (
              <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                <h2 className="text-sm font-medium text-zinc-200">模拟盘（Paper Trading）</h2>
                <p className="mt-1 text-xs text-zinc-400">按你要求的布局：交易 / 账户 / 持仓 / 策略 / 设定。</p>

                {/* Row 1 */}
                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/20 p-3">
                    <div className="text-xs font-medium text-zinc-200">当日交易</div>
                    <div className="mt-2 space-y-1 text-xs text-zinc-300">
                      {(() => {
                        const all = ((paperSummary as any)?.trades as Record<string, string>[] | undefined) ?? [];
                        // "当日交易" = 最近一个交易日的全部交易（可能不止一笔）
                        const latestDate =
                          (all[0]?.date || "").trim() ||
                          (paperSummary as any)?.portfolio?.last_trade_date ||
                          (paperSummary as any)?.serverDateJst;
                        const rows = all.filter((t) => (t.date || "").trim() === String(latestDate).trim());
                        if (!rows.length) return <div className="text-zinc-500">今天暂无交易（或还未运行 paper_trade.py）</div>;
                        return rows.slice(0, 12).map((t, i) => (
                          <div key={i} className="flex items-baseline justify-between gap-3">
                            <div className="text-zinc-200">
                              {t.code}{" "}
                              <span
                                className={
                                  t.side === "BUY"
                                    ? "text-emerald-300"
                                    : t.side === "SELL"
                                      ? "text-rose-300"
                                      : "text-zinc-300"
                                }
                              >
                                {t.side}
                              </span>
                            </div>
                            <div className="text-zinc-400">{t.qty} @ {t.price} ({t.reason})</div>
                          </div>
                        ));
                      })()}
                    </div>
                  </div>

                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/20 p-3">
                    <div className="text-xs font-medium text-zinc-200">最近交易</div>
                    <div className="mt-2 space-y-1 text-xs text-zinc-300">
                      {(paperSummary as any)?.trades && (paperSummary as any).trades.length > 0 ? (
                        (((paperSummary as any).trades as Record<string, string>[]).slice(0, 12) as Record<string, string>[]).map((t, i) => (
                          <div key={i} className="flex items-baseline justify-between gap-3">
                            <div className="text-zinc-200">
                              {t.date} {t.code}{" "}
                              <span
                                className={
                                  t.side === "BUY"
                                    ? "text-emerald-300"
                                    : t.side === "SELL"
                                      ? "text-rose-300"
                                      : "text-zinc-300"
                                }
                              >
                                {t.side}
                              </span>
                            </div>
                            <div className="text-zinc-400">{t.qty} @ {t.price}</div>
                          </div>
                        ))
                      ) : (
                        <div className="text-zinc-500">暂无交易记录</div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Row 2 */}
                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/20 p-3">
                    <div className="text-xs font-medium text-zinc-200">当前账户概况（含收益）</div>
                    <div className="mt-2 text-xs text-zinc-300 space-y-1">
                      {(() => {
                        const cash = (paperSummary as any)?.portfolio?.cash;
                        const eq = ((paperSummary as any)?.equity as Record<string, string>[] | undefined) ?? [];
                        const last = eq.length ? eq[eq.length - 1] : null;
                        const total = last?.total != null ? Number(last.total) : null;
                        const init = Number((paperSummary as any)?.strategy?.settings?.initial_cash_jpy ?? (paperSummary as any)?.latestPicks?.initial_cash_jpy ?? (paperSummary as any)?.portfolio?.initial_cash_jpy ?? 1000000);
                        const pnl = total != null ? total - init : null;
                        const pnlPct = total != null && init ? (pnl! / init) * 100 : null;
                        return (
                          <>
                            <div>现金：{cash != null ? Number(cash).toFixed(0) : "-"} JPY</div>
                            <div>总资产：{total != null ? total.toFixed(0) : "-"} JPY</div>
                            <div>
                              累计收益：
                              {pnl != null ? `${pnl >= 0 ? "+" : ""}${pnl.toFixed(0)} JPY` : "-"}
                              {pnlPct != null ? `（${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%）` : ""}
                            </div>
                            <div>上次交易日：{(paperSummary as any)?.portfolio?.last_trade_date ?? "-"}</div>
                          </>
                        );
                      })()}
                    </div>
                  </div>

                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/20 p-3">
                    <div className="text-xs font-medium text-zinc-200">持仓</div>
                    <div className="mt-2 space-y-1 text-xs text-zinc-300">
                      {(paperSummary as any)?.portfolio?.positions && Object.keys((paperSummary as any).portfolio.positions).length > 0 ? (
                        Object.entries((paperSummary as any).portfolio.positions as Record<string, any>).map(([code, pos]) => (
                          <div key={code} className="flex items-baseline justify-between">
                            <div>{code}</div>
                            <div className="text-zinc-400">qty {pos.qty} · avg {Number(pos.avg_cost).toFixed(2)}</div>
                          </div>
                        ))
                      ) : (
                        <div className="text-zinc-500">暂无持仓</div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Row 3 */}
                <div className="mt-4 rounded-lg border border-zinc-800 bg-zinc-950/20 p-3">
                  <div className="text-xs font-medium text-zinc-200">交易策略</div>
                  <pre className="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-zinc-300">{paperStrategy || "（未加载）"}</pre>
                </div>

                {/* Row 4 */}
                <div className="mt-4 rounded-lg border border-zinc-800 bg-zinc-950/20 p-3">
                  <div className="text-xs font-medium text-zinc-200">设定</div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <button
                      className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-800"
                      onClick={async () => {
                        if (!confirm("确认清零模拟盘？将把 paper/ 下文件移到 .trash（可恢复）。")) return;
                        const r = await fetch("/api/paper/reset", {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ confirm: true }),
                        });
                        const j = await r.json();
                        if (!j.ok) alert(j.error ?? "reset failed");
                        const r2 = await fetch("/api/paper/summary");
                        const j2 = await r2.json();
                        if (j2.ok) setPaperSummary(j2);
                      }}
                    >
                      清零 / 重新开始
                    </button>

                    <button
                      className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-800"
                      onClick={async () => {
                        const v = prompt("设置初始资金（JPY）", "1000000");
                        if (!v) return;
                        const r = await fetch("/api/paper/settings", {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ initial_cash_jpy: Number(v) }),
                        });
                        const j = await r.json();
                        if (!j.ok) alert(j.error ?? "save failed");
                        const r2 = await fetch("/api/paper/strategy");
                        const j2 = await r2.json();
                        if (j2.ok) setPaperStrategy(j2.strategyZh ?? "");
                      }}
                    >
                      设定初始金额
                    </button>

                    <button
                      className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-800"
                      onClick={async () => {
                        const v = prompt("设置 TopK（买入只数）", "5");
                        if (!v) return;
                        const r = await fetch("/api/paper/settings", {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ top_k: Number(v) }),
                        });
                        const j = await r.json();
                        if (!j.ok) alert(j.error ?? "save failed");
                        const r2 = await fetch("/api/paper/strategy");
                        const j2 = await r2.json();
                        if (j2.ok) setPaperStrategy(j2.strategyZh ?? "");
                      }}
                    >
                      设定 TopK
                    </button>

                    <div className="text-xs text-zinc-500">提示：初始资金变更只在清零后首次建仓时生效。</div>
                  </div>
                </div>
              </section>
            ) : null}
          </main>
        </div>

        <footer className="mt-10 text-xs text-zinc-500">本地 Web App（WSL）。预测仅用于研究/演示，不构成投资建议。</footer>
      </div>
    </div>
  );
}

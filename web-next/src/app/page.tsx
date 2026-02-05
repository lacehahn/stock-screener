"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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

type Panel = "report" | "chart" | "news";

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
  const [reportHtmlUrl] = useState<string>("/api/report/latest.html");
  const [picks, setPicks] = useState<Pick[]>([]);
  const [selected, setSelected] = useState<Pick | null>(null);

  const [panel, setPanel] = useState<Panel>("chart");

  const [news, setNews] = useState<NewsItem[]>([]);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);
  const [forecastMethod, setForecastMethod] = useState<string>("");
  const [showLevels, setShowLevels] = useState<boolean>(true);

  useEffect(() => {
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
  }, []);

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
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="text-sm text-zinc-400">Dashboard：Top10 筛选 + 报告 / K线与预测 / 新闻</p>
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
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <CardTab active={panel === "chart"} title="K线 + 预测" desc="同图叠加" onClick={() => setPanel("chart")} />
              <CardTab active={panel === "news"} title="新闻" desc="公司名+代码匹配" onClick={() => setPanel("news")} />
              <CardTab active={panel === "report"} title="报告" desc="文档化段落" onClick={() => setPanel("report")} />
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
          </main>
        </div>

        <footer className="mt-10 text-xs text-zinc-500">本地 Web App（WSL）。预测仅用于研究/演示，不构成投资建议。</footer>
      </div>
    </div>
  );
}

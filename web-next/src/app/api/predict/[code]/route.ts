import { NextResponse } from "next/server";

export const runtime = "nodejs";

type Bar = { date: string; close: number };

function addDaysISO(iso: string, days: number) {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export async function GET(_: Request, { params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  if (!/^\d{4}$/.test(code)) {
    return NextResponse.json({ ok: false, error: "invalid code" }, { status: 400 });
  }

  // Fetch directly from Stooq to avoid self-calls.
  const sym = `${code}.jp`;
  const url = `https://stooq.com/q/d/l/?s=${encodeURIComponent(sym)}&i=d`;

  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), 25000);
  const r = await fetch(url, { signal: ac.signal, next: { revalidate: 3600 } }).finally(() => clearTimeout(t));
  if (!r.ok) {
    return NextResponse.json({ ok: false, error: `stooq error ${r.status}` }, { status: 502 });
  }
  const text = await r.text();
  const lines = text.trim().split(/\r?\n/);

  const series: Bar[] = [];
  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(",");
    if (parts.length < 6) continue;
    const date = parts[0];
    const close = Number(parts[4]);
    if (!date || !Number.isFinite(close)) continue;
    series.push({ date, close });
  }
  const closes = series.map((x) => x.close).filter((x) => Number.isFinite(x));
  if (closes.length < 30) {
    return NextResponse.json({ ok: true, code, forecast: [] });
  }

  // Simple forecast: linear regression on last N closes.
  const N = Math.min(60, closes.length);
  const y = closes.slice(-N);
  const x = Array.from({ length: N }, (_, i) => i);

  const xMean = (N - 1) / 2;
  const yMean = y.reduce((a, b) => a + b, 0) / N;
  let num = 0;
  let den = 0;
  for (let i = 0; i < N; i++) {
    num += (x[i] - xMean) * (y[i] - yMean);
    den += (x[i] - xMean) * (x[i] - xMean);
  }
  const slope = den === 0 ? 0 : num / den;
  const intercept = yMean - slope * xMean;

  const horizon = 10;
  const lastDate = series[series.length - 1].date;
  const forecast = Array.from({ length: horizon }, (_, k) => {
    const xi = N - 1 + (k + 1);
    const pred = intercept + slope * xi;
    return { date: addDaysISO(lastDate, k + 1), close: Number(pred.toFixed(2)) };
  });

  return NextResponse.json({ ok: true, code, forecast, method: "linear-regression-close" });
}

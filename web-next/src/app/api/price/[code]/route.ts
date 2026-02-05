import { NextResponse } from "next/server";

export const runtime = "nodejs";

function toStooqSymbol(code: string) {
  return `${code}.jp`;
}

export async function GET(_: Request, { params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  if (!/^\d{4}$/.test(code)) {
    return NextResponse.json({ ok: false, error: "invalid code" }, { status: 400 });
  }

  const sym = toStooqSymbol(code);
  const url = `https://stooq.com/q/d/l/?s=${encodeURIComponent(sym)}&i=d`;

  // Use AbortController for a longer timeout than default.
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), 25000);
  const r = await fetch(url, {
    signal: ac.signal,
    next: { revalidate: 3600 },
  }).finally(() => clearTimeout(t));
  if (!r.ok) {
    return NextResponse.json({ ok: false, error: `stooq error ${r.status}` }, { status: 502 });
  }
  const text = await r.text();
  const lines = text.trim().split(/\r?\n/);
  // header: Date,Open,High,Low,Close,Volume
  const out: { date: string; open: number; high: number; low: number; close: number; volume: number }[] = [];
  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(",");
    if (parts.length < 6) continue;
    const date = parts[0];
    const open = Number(parts[1]);
    const high = Number(parts[2]);
    const low = Number(parts[3]);
    const close = Number(parts[4]);
    const volume = Number(parts[5]);
    if (!date) continue;
    if (![open, high, low, close, volume].every((x) => Number.isFinite(x))) continue;
    out.push({ date, open, high, low, close, volume });
  }

  const series = out.slice(-200);
  return NextResponse.json({ ok: true, code, series });
}

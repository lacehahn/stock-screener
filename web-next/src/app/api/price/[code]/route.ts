import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const runtime = "nodejs";

function rootDir() {
  // web-next -> project root
  return path.resolve(process.cwd(), "..");
}

function cachePathForCode(code: string) {
  // Python cache: data_cache/{symbol}.csv, symbol is like "1332.jp"
  const sym = `${code}.jp`;
  return path.join(rootDir(), "data_cache", `${sym}.csv`);
}

function dummySeries(code: string) {
  const today = new Date();
  const series: { date: string; open: number; high: number; low: number; close: number; volume: number }[] = [];
  let close = 1200 + (Number(code) % 500);
  for (let i = 220; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const date = d.toISOString().slice(0, 10);
    const open = close;
    close = close * (1 + 0.0005) * (1 + (((i % 10) - 5) * 0.001));
    const high = Math.max(open, close) * 1.01;
    const low = Math.min(open, close) * 0.99;
    const volume = 1_500_000;
    series.push({ date, open, high, low, close, volume });
  }
  return series;
}

export async function GET(_: Request, { params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  if (!/^\d{4}$/.test(code)) {
    return NextResponse.json({ ok: false, error: "invalid code" }, { status: 400 });
  }

  const p = cachePathForCode(code);
  if (!fs.existsSync(p)) {
    // No network access here: local-only mode.
    // Provide dummy series so UI remains usable.
    return NextResponse.json({ ok: true, code, series: dummySeries(code), dummy: true, source: "dummy" });
  }

  const text = fs.readFileSync(p, "utf-8");
  const lines = text.trim().split(/\r?\n/);

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
  return NextResponse.json({ ok: true, code, series, source: "cache" });
}

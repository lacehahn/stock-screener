import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const runtime = "nodejs";

function rootDir() {
  return path.resolve(process.cwd(), "..");
}

export async function GET(_: Request, { params }: { params: Promise<{ asof: string }> }) {
  const { asof } = await params;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(asof)) {
    return NextResponse.json({ ok: false, error: "invalid asof" }, { status: 400 });
  }

  const p = path.join(rootDir(), "reports", `nikkei-picks-${asof}.json`);
  if (!fs.existsSync(p)) {
    return NextResponse.json({ ok: false, error: "not found" }, { status: 404 });
  }
  const j = JSON.parse(fs.readFileSync(p, "utf-8"));

  const picks = (j.picks ?? []).map((x: any, idx: number) => ({
    rank: idx + 1,
    code: String(x.code),
    name: x.name,
    score: x.score,
    close: x.close,
    entry: x.entry,
    stop: x.stop,
    takeProfit: x.take_profit,
    reasons: x.reasons,
  }));

  return NextResponse.json({ ok: true, asof, picks });
}

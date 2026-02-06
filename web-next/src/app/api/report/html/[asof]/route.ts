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

  const p = path.join(rootDir(), "reports", `nikkei-report-${asof}.html`);
  if (!fs.existsSync(p)) {
    return NextResponse.json({ ok: false, error: "not found" }, { status: 404 });
  }
  const html = fs.readFileSync(p, "utf-8");
  return new NextResponse(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

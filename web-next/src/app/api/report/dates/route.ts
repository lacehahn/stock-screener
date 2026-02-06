import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const runtime = "nodejs";

function rootDir() {
  return path.resolve(process.cwd(), "..");
}

export async function GET() {
  const reportsDir = path.join(rootDir(), "reports");
  let dates: string[] = [];
  try {
    const files = fs.readdirSync(reportsDir);
    // nikkei-report-YYYY-MM-DD.html
    const re = /^nikkei-report-(\d{4}-\d{2}-\d{2})\.html$/;
    dates = files
      .map((f) => {
        const m = f.match(re);
        return m ? m[1] : null;
      })
      .filter((x): x is string => Boolean(x))
      .sort()
      .reverse();
  } catch {
    dates = [];
  }

  return NextResponse.json({ ok: true, dates });
}

import { NextResponse } from "next/server";
import fs from "fs";
import { latestReportPath } from "@/lib/paths";
import { parseTopPicksFromMarkdown } from "@/lib/parseReport";

export const runtime = "nodejs";

export async function GET() {
  const p = latestReportPath();
  if (!fs.existsSync(p)) {
    return NextResponse.json({ ok: false, error: "latest report not found" }, { status: 404 });
  }
  const md = fs.readFileSync(p, "utf-8");
  const picks = parseTopPicksFromMarkdown(md);
  return NextResponse.json({ ok: true, picks });
}

import { NextResponse } from "next/server";
import fs from "fs";
import { universeCsvPath } from "@/lib/paths";

export const runtime = "nodejs";

export async function GET() {
  const p = universeCsvPath();
  if (!fs.existsSync(p)) {
    return NextResponse.json({ ok: false, error: "universe.csv not found" }, { status: 404 });
  }
  const text = fs.readFileSync(p, "utf-8");
  const lines = text.trim().split(/\r?\n/);
  const map: Record<string, string> = {};
  for (let i = 1; i < lines.length; i++) {
    const [code, name] = lines[i].split(",");
    if (!code) continue;
    map[code.trim()] = (name ?? "").trim();
  }
  return NextResponse.json({ ok: true, map });
}

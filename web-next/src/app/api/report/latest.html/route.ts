import { NextResponse } from "next/server";
import fs from "fs";
import { reportsDir } from "@/lib/paths";

export const runtime = "nodejs";

export async function GET() {
  const p = `${reportsDir()}/latest.html`;
  if (!fs.existsSync(p)) {
    return NextResponse.json({ ok: false, error: "latest.html not found" }, { status: 404 });
  }
  const html = fs.readFileSync(p, "utf-8");
  return new NextResponse(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      // basic hardening
      "X-Content-Type-Options": "nosniff",
    },
  });
}

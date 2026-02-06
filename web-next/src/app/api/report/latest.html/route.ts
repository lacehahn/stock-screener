import { NextResponse } from "next/server";
import fs from "fs";
import { reportsDir } from "@/lib/paths";

export const runtime = "nodejs";

function injectEinkCss(html: string) {
  const css = `
  <style id="eink-mode">
    :root, body { background: #ffffff !important; color: #111111 !important; }
    body { font-size: 18px !important; line-height: 1.7 !important; letter-spacing: 0.1px; }
    a { color: #111111 !important; text-decoration: underline; }
    * { box-shadow: none !important; text-shadow: none !important; }
    table { border-collapse: collapse !important; }
    th, td { border: 1px solid #111 !important; }
    pre, code { background: #f4f4f4 !important; color: #111 !important; }
    img, svg, canvas { filter: grayscale(100%) contrast(120%) !important; }
    [style*="background"], [class*="bg-"] { background: transparent !important; }
  </style>`;

  if (html.includes("</head>")) return html.replace("</head>", `${css}\n</head>`);
  return `${css}\n${html}`;
}

export async function GET(req: Request) {
  const p = `${reportsDir()}/latest.html`;
  if (!fs.existsSync(p)) {
    return NextResponse.json({ ok: false, error: "latest.html not found" }, { status: 404 });
  }
  let html = fs.readFileSync(p, "utf-8");

  const url = new URL(req.url);
  if ((url.searchParams.get("mode") || "").toLowerCase() === "eink") {
    html = injectEinkCss(html);
  }

  return new NextResponse(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      // basic hardening
      "X-Content-Type-Options": "nosniff",
    },
  });
}

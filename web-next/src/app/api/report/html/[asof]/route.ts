import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const runtime = "nodejs";

function rootDir() {
  return path.resolve(process.cwd(), "..");
}

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
    /* reduce pure black backgrounds from the original theme */
    [style*="background"], [class*="bg-"] { background: transparent !important; }
  </style>`;

  if (html.includes("</head>")) return html.replace("</head>", `${css}\n</head>`);
  return `${css}\n${html}`;
}

export async function GET(req: Request, { params }: { params: Promise<{ asof: string }> }) {
  const { asof } = await params;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(asof)) {
    return NextResponse.json({ ok: false, error: "invalid asof" }, { status: 400 });
  }

  const p = path.join(rootDir(), "reports", `nikkei-report-${asof}.html`);
  if (!fs.existsSync(p)) {
    return NextResponse.json({ ok: false, error: "not found" }, { status: 404 });
  }
  let html = fs.readFileSync(p, "utf-8");

  const url = new URL(req.url);
  if ((url.searchParams.get("mode") || "").toLowerCase() === "eink") {
    html = injectEinkCss(html);
  }

  return new NextResponse(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

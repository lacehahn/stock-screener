import { NextResponse } from "next/server";
import { XMLParser } from "fast-xml-parser";

export const runtime = "nodejs";

export async function GET(_: Request, { params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  if (!/^\d{4}$/.test(code)) {
    return NextResponse.json({ ok: false, error: "invalid code" }, { status: 400 });
  }

  // Google News RSS.
  // Use company name (from universe.csv) when available for better matching.
  // Load company name from universe.csv (best-effort)
  let company = "";
  try {
    const fs = await import("fs");
    const { universeCsvPath } = await import("@/lib/paths");
    const p = universeCsvPath();
    if (fs.existsSync(p)) {
      const text = fs.readFileSync(p, "utf-8");
      const lines = text.trim().split(/\r?\n/);
      for (let i = 1; i < lines.length; i++) {
        const [c, name] = lines[i].split(",");
        if ((c ?? "").trim() === code) {
          company = (name ?? "").trim();
          break;
        }
      }
    }
  } catch {
    company = "";
  }

  const query = company ? `${company} ${code} 株価 OR 決算 OR 日経` : `${code} 株価 OR 決算 OR 日経`;
  const q = encodeURIComponent(query);
  const rss = `https://news.google.com/rss/search?q=${q}&hl=ja&gl=JP&ceid=JP:ja`;

  const r = await fetch(rss, {
    // let Next cache a bit to avoid hammering
    next: { revalidate: 600 },
  });
  if (!r.ok) {
    return NextResponse.json({ ok: false, error: `rss fetch error ${r.status}` }, { status: 502 });
  }
  const xml = await r.text();

  const parser = new XMLParser({ ignoreAttributes: false });
  const data = parser.parse(xml);
  const items = data?.rss?.channel?.item ?? [];
  const arr = Array.isArray(items) ? items : [items];

  const news = arr.slice(0, 10).map((it: any) => ({
    title: it.title as string,
    link: it.link as string,
    pubDate: it.pubDate as string,
    source: it.source?.["#text"] ?? it.source ?? "",
  }));

  return NextResponse.json({ ok: true, code, news });
}

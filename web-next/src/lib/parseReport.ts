export type Pick = {
  rank: number;
  code: string;
  name?: string;
  score?: number;
  close?: number;
  entry?: number;
  stop?: number;
  takeProfit?: number;
  reasons?: string[];
};

export function parseTopPicksFromMarkdown(md: string): Pick[] {
  // Parser for the generated Chinese report.
  // We primarily parse the "今日 Top10 概览" lines because they contain Entry/Stop/TP/Score.
  // Example:
  // 1. **4004** RESONAC HOLDINGS｜Entry **9487**｜Stop **8306**｜TP **11850**｜Score **0.760**

  const lines = md.split(/\r?\n/);

  const byCode: Record<string, Pick> = {};

  // 1) Parse overview lines
  for (const line of lines) {
    const m = line.match(
      /^(\d+)\.\s+\*\*(\d{4})\*\*\s*(.*?)｜Entry\s+\*\*([0-9.]+)\*\*｜Stop\s+\*\*([0-9.]+)\*\*｜TP\s+\*\*([0-9.]+)\*\*｜Score\s+\*\*([0-9.]+)\*\*/
    );
    if (!m) continue;
    const rank = Number(m[1]);
    const code = m[2];
    const name = (m[3] || "").trim() || undefined;
    const entry = Number(m[4]);
    const stop = Number(m[5]);
    const tp = Number(m[6]);
    const score = Number(m[7]);

    byCode[code] = {
      rank,
      code,
      name,
      entry: Number.isFinite(entry) ? entry : undefined,
      stop: Number.isFinite(stop) ? stop : undefined,
      takeProfit: Number.isFinite(tp) ? tp : undefined,
      score: Number.isFinite(score) ? score : undefined,
    };
  }

  // 2) Parse detail sections for reasons + close (optional)
  // Heading: ### 1. 4004 — NAME
  let cur: Pick | null = null;

  for (const line of lines) {
    const h = line.match(/^###\s+(\d+)\.\s+(\d{4})\s+—\s+(.+)\s*$/);
    if (h) {
      const code = h[2];
      cur = byCode[code] ?? { rank: Number(h[1]), code, name: h[3].trim() };
      cur.rank = cur.rank ?? Number(h[1]);
      cur.name = cur.name ?? h[3].trim();
      byCode[code] = cur;
      continue;
    }

    if (!cur) continue;

    // Table row: | 最新收盘价 | 9351.00 日元 |
    const row = line.match(/^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|/);
    if (row) {
      const key = row[1].trim();
      const val = row[2].trim();
      if (key.includes("最新收盘价")) {
        const num = Number(val.replace(/[^0-9.]/g, ""));
        if (Number.isFinite(num)) cur.close = num;
      }
    }

    // Reasons bullets: - xxx /   - xxx
    const b = line.match(/^\s*\-\s+(.+)$/);
    if (b && (line.includes("动量") || line.includes("EMA") || line.includes("波动率"))) {
      cur.reasons = cur.reasons ?? [];
      cur.reasons.push(b[1].trim());
    }
  }

  const picks = Object.values(byCode);
  return picks
    .filter((p) => p.rank && p.code)
    .sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999))
    .slice(0, 10);
}

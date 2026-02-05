"use client";

function clamp(x: number, a: number, b: number) {
  return Math.max(a, Math.min(b, x));
}

export default function RiskRewardBar({
  entry,
  stop,
  takeProfit,
}: {
  entry?: number;
  stop?: number;
  takeProfit?: number;
}) {
  if (![entry, stop, takeProfit].every((x) => typeof x === "number" && Number.isFinite(x))) {
    return <div className="text-xs text-zinc-500">（缺少 Entry/Stop/TP）</div>;
  }

  const e = entry as number;
  const s = stop as number;
  const tp = takeProfit as number;

  // Ensure ordering
  const lo = Math.min(s, e, tp);
  const hi = Math.max(s, e, tp);
  const span = hi - lo || 1;

  const pos = (v: number) => clamp(((v - lo) / span) * 100, 0, 100);

  const ps = pos(s);
  const pe = pos(e);
  const pt = pos(tp);

  const left = Math.min(ps, pe);
  const right = Math.max(ps, pe);
  const rewardLeft = Math.min(pe, pt);
  const rewardRight = Math.max(pe, pt);

  return (
    <div className="space-y-2">
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-zinc-800">
        {/* Risk segment (Stop -> Entry) */}
        <div
          className="absolute top-0 h-full bg-red-500/50"
          style={{ left: `${left}%`, width: `${Math.max(2, right - left)}%` }}
        />
        {/* Reward segment (Entry -> TP) */}
        <div
          className="absolute top-0 h-full bg-emerald-500/50"
          style={{ left: `${rewardLeft}%`, width: `${Math.max(2, rewardRight - rewardLeft)}%` }}
        />

        {/* Markers */}
        <div className="absolute -top-1 h-5 w-[2px] bg-red-400" style={{ left: `${ps}%` }} title={`Stop ${s.toFixed(0)}`} />
        <div className="absolute -top-1 h-5 w-[2px] bg-zinc-200" style={{ left: `${pe}%` }} title={`Entry ${e.toFixed(0)}`} />
        <div className="absolute -top-1 h-5 w-[2px] bg-emerald-300" style={{ left: `${pt}%` }} title={`TP ${tp.toFixed(0)}`} />
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs text-zinc-300">
        <div className="rounded bg-zinc-950/40 px-2 py-1">
          <span className="text-zinc-400">Stop</span> {s.toFixed(0)}
        </div>
        <div className="rounded bg-zinc-950/40 px-2 py-1">
          <span className="text-zinc-400">Entry</span> {e.toFixed(0)}
        </div>
        <div className="rounded bg-zinc-950/40 px-2 py-1">
          <span className="text-zinc-400">TP</span> {tp.toFixed(0)}
        </div>
      </div>
    </div>
  );
}

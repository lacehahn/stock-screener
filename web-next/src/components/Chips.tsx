"use client";

export default function Chips({ items }: { items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((t, idx) => (
        <span
          key={idx}
          className="inline-flex items-center rounded-full border border-zinc-700 bg-zinc-950/40 px-2.5 py-1 text-xs text-zinc-200"
        >
          {t}
        </span>
      ))}
    </div>
  );
}

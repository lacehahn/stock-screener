import { NextResponse } from "next/server";

export const runtime = "nodejs";

function requireEnv(name: string) {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env: ${name}`);
  return v;
}

export async function GET() {
  // Simple health check (does not call upstream)
  const url = process.env.THIRD_AI_URL || "";
  return NextResponse.json({
    ok: true,
    configured: Boolean(url),
    thirdAiUrlHost: url ? (() => {
      try {
        return new URL(url).host;
      } catch {
        return "invalid";
      }
    })() : null,
  });
}

export async function POST(req: Request) {
  let payload: unknown;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid json" }, { status: 400 });
  }

  let upstreamUrl: string;
  try {
    upstreamUrl = requireEnv("THIRD_AI_URL");
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message ?? "THIRD_AI_URL not set" }, { status: 500 });
  }

  const apiKey = process.env.THIRD_AI_API_KEY;
  const authHeaderName = process.env.THIRD_AI_AUTH_HEADER || "Authorization";
  const authHeaderValue = apiKey
    ? (process.env.THIRD_AI_AUTH_PREFIX || "Bearer") === "" 
      ? apiKey
      : `${process.env.THIRD_AI_AUTH_PREFIX || "Bearer"} ${apiKey}`
    : "";

  const timeoutMs = Number(process.env.THIRD_AI_TIMEOUT_MS || 25000);
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);

  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "Accept": "application/json",
    };
    if (apiKey) headers[authHeaderName] = authHeaderValue;

    const r = await fetch(upstreamUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });

    const contentType = r.headers.get("content-type") || "";
    const text = await r.text();

    if (!r.ok) {
      return NextResponse.json(
        {
          ok: false,
          error: `upstream ${r.status}`,
          upstreamStatus: r.status,
          upstreamBody: text.slice(0, 4000),
        },
        { status: 502 }
      );
    }

    // If upstream returns JSON, pass it through; else wrap.
    if (contentType.includes("application/json")) {
      try {
        const j = JSON.parse(text);
        return NextResponse.json({ ok: true, data: j });
      } catch {
        // fall through
      }
    }

    return NextResponse.json({ ok: true, data: text });
  } catch (e: any) {
    const msg = e?.name === "AbortError" ? `timeout after ${timeoutMs}ms` : (e?.message ?? String(e));
    return NextResponse.json({ ok: false, error: msg }, { status: 502 });
  } finally {
    clearTimeout(t);
  }
}

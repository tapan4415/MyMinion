"use client";

import { useCallback, useEffect, useState } from "react";

type Memory = {
  index: string;
  kind: string;
  content: string;
  source?: string | null;
  created_at?: string | null;
  id?: string;
};
type Research = {
  title?: string;
  summary?: string;
  source_url?: string;
  confidence?: number;
  topic?: string;
  retrieved_at?: string;
  mock?: boolean;
};
type Data = {
  user_id: string;
  counts: { memories: number; research: number };
  memories: Memory[];
  research: Research[];
};

const KIND_COLOR: Record<string, string> = {
  preference: "bg-indigo-50 text-indigo-700 border-indigo-200",
  constraint: "bg-amber-50 text-amber-700 border-amber-200",
  decision: "bg-emerald-50 text-emerald-700 border-emerald-200",
  journey: "bg-sky-50 text-sky-700 border-sky-200",
  profile: "bg-zinc-100 text-zinc-700 border-zinc-200",
  rejection_reason: "bg-rose-50 text-rose-700 border-rose-200",
};

function timeAgo(iso?: string | null) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const s = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

export default function MemoryPage() {
  const [data, setData] = useState<Data | null>(null);
  const [userId, setUserId] = useState("demo-user");
  const [auto, setAuto] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const r = await fetch(`/api/moss/inspect?user_id=${encodeURIComponent(userId)}`, {
        cache: "no-store",
      });
      if (!r.ok) throw new Error("failed");
      setData((await r.json()) as Data);
    } catch {
      setErr("Could not reach the agent API. Is the backend running on :8000?");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (!auto) return;
    const t = setInterval(() => void load(), 5000);
    return () => clearInterval(t);
  }, [auto, load]);

  const byKind: Record<string, Memory[]> = {};
  for (const m of data?.memories ?? []) (byKind[m.kind] ??= []).push(m);
  const kinds = Object.keys(byKind).sort();

  return (
    <main className="min-h-dvh bg-[#0b0c10] text-zinc-100">
      <div className="mx-auto max-w-6xl px-5 py-8">
        <header className="flex flex-wrap items-center gap-3">
          <div>
            <h1 className="text-2xl font-black tracking-tight">MyMinion — Knowledge Inspector</h1>
            <p className="text-sm text-zinc-400">
              Live view of what Moss knows and what Bright Data has enriched. Auto-refreshes every 5s.
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2 text-sm">
            <input
              value={userId}
              onChange={e => setUserId(e.target.value)}
              className="w-36 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-indigo-500"
              placeholder="user_id"
            />
            <button
              onClick={() => void load()}
              className="rounded-lg bg-indigo-600 px-3 py-2 font-semibold text-white hover:bg-indigo-500"
            >
              {loading ? "…" : "Refresh"}
            </button>
            <label className="flex items-center gap-1 text-xs text-zinc-400">
              <input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} /> auto
            </label>
          </div>
        </header>

        {err && <p className="mt-4 rounded-lg bg-rose-500/10 p-3 text-sm text-rose-300">{err}</p>}

        <div className="mt-4 flex gap-3 text-sm">
          <span className="rounded-full bg-zinc-800 px-3 py-1">
            🧠 {data?.counts.memories ?? 0} memories
          </span>
          <span className="rounded-full bg-zinc-800 px-3 py-1">
            🔎 {data?.counts.research ?? 0} research docs
          </span>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.3fr_1fr]">
          {/* Memories */}
          <section>
            <h2 className="mb-3 text-sm font-bold uppercase tracking-wider text-zinc-500">
              Moss memory
            </h2>
            {kinds.length === 0 && (
              <p className="text-sm text-zinc-500">No memories yet. Talk to the Scribe in Listen mode.</p>
            )}
            <div className="space-y-5">
              {kinds.map(kind => (
                <div key={kind}>
                  <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-zinc-500">
                    {kind.replace("_", " ")} · {byKind[kind].length}
                  </p>
                  <div className="space-y-2">
                    {byKind[kind].map((m, i) => {
                      const other = m.source?.startsWith("scribe:about:");
                      return (
                        <div
                          key={m.id ?? i}
                          className={`rounded-xl border p-3 text-sm ${KIND_COLOR[kind] ?? "border-zinc-700 bg-zinc-900 text-zinc-200"}`}
                        >
                          <p className="leading-5">{m.content}</p>
                          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] opacity-70">
                            <span>{timeAgo(m.created_at)}</span>
                            {m.source && (
                              <span
                                className={`rounded px-1.5 py-0.5 ${other ? "bg-rose-200/60 text-rose-900" : "bg-black/10"}`}
                              >
                                {other ? `about ${m.source.replace("scribe:about:", "")}` : m.source}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Research */}
          <section>
            <h2 className="mb-3 text-sm font-bold uppercase tracking-wider text-zinc-500">
              Bright Data enrichment
            </h2>
            {(data?.research.length ?? 0) === 0 && (
              <p className="text-sm text-zinc-500">No research yet.</p>
            )}
            <div className="space-y-2">
              {data?.research.map((r, i) => (
                <article key={i} className="rounded-xl border border-zinc-800 bg-zinc-900 p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold text-zinc-100">{r.title || r.topic || "Research"}</p>
                    <span
                      className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] ${r.mock ? "bg-amber-500/20 text-amber-300" : "bg-emerald-500/20 text-emerald-300"}`}
                    >
                      {r.mock ? "mock" : "live"}
                    </span>
                  </div>
                  {r.topic && <p className="mt-0.5 text-[11px] text-zinc-500">topic: {r.topic}</p>}
                  <p className="mt-1.5 text-xs leading-5 text-zinc-400">{r.summary}</p>
                  <div className="mt-2 flex items-center gap-2 text-[10px] text-zinc-500">
                    {typeof r.confidence === "number" && <span>{Math.round(r.confidence * 100)}% conf</span>}
                    <span>{timeAgo(r.retrieved_at)}</span>
                    {r.source_url && (
                      <a href={r.source_url} target="_blank" rel="noreferrer" className="truncate text-indigo-400 underline">
                        {r.source_url}
                      </a>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

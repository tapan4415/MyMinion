"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type Memory = {
  index: string;
  kind: string;
  content: string;
  name?: string | null;
  identity?: string | null;
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

const KIND_META: Record<string, { label: string; dot: string }> = {
  preference: { label: "Preferences", dot: "bg-indigo-400" },
  constraint: { label: "Constraints", dot: "bg-amber-400" },
  decision: { label: "Decisions", dot: "bg-emerald-400" },
  journey: { label: "Journeys", dot: "bg-sky-400" },
  profile: { label: "Profile", dot: "bg-zinc-400" },
  rejection_reason: { label: "Rejected", dot: "bg-rose-400" },
  contact: { label: "Contacts", dot: "bg-fuchsia-400" },
};
function meta(kind: string) {
  return KIND_META[kind] ?? { label: kind, dot: "bg-zinc-300" };
}

function timeAgo(iso?: string | null) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const s = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

function sourceTag(source?: string | null): { text: string; className: string } | null {
  if (!source) return null;
  if (source.startsWith("scribe:about:"))
    return { text: `about ${source.replace("scribe:about:", "")}`, className: "bg-fuchsia-100 text-fuchsia-700" };
  if (source === "scribe:person") return { text: "person lookup", className: "bg-fuchsia-100 text-fuchsia-700" };
  if (source === "scribe") return { text: "scribe", className: "bg-emerald-100 text-emerald-700" };
  if (source === "conversation") return { text: "conversation", className: "bg-zinc-100 text-zinc-500" };
  return { text: source, className: "bg-zinc-100 text-zinc-500" };
}

type Person = { name: string; detail: string; created_at?: string | null };

export default function MemoryPage() {
  const [data, setData] = useState<Data | null>(null);
  const [userId, setUserId] = useState("demo-user");
  const [auto, setAuto] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const r = await fetch(`/api/moss/inspect?user_id=${encodeURIComponent(userId)}`, { cache: "no-store" });
      if (!r.ok) throw new Error("failed");
      setData((await r.json()) as Data);
      setUpdatedAt(Date.now());
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
    const t = setInterval(() => void load(), 8000);
    return () => clearInterval(t);
  }, [auto, load]);

  const { people, byKind, kindOrder, restCount } = useMemo(() => {
    const mems = data?.memories ?? [];
    const isPerson = (m: Memory) => m.kind === "contact" || m.source === "scribe:person";

    // Dedupe people by name, keeping the richest detail.
    const map = new Map<string, Person>();
    for (const m of mems.filter(isPerson)) {
      const name = (m.name || (m.content.includes(":") ? m.content.split(":")[0] : "") || "Contact").trim();
      const detail = (m.identity || (m.content.includes(":") ? m.content.split(":").slice(1).join(":") : m.content) || "").trim();
      const key = name.toLowerCase();
      const existing = map.get(key);
      if (!existing || detail.length > existing.detail.length) {
        map.set(key, { name, detail, created_at: m.created_at });
      }
    }
    const people = [...map.values()];

    const rest = mems.filter(m => !isPerson(m));
    const byKind: Record<string, Memory[]> = {};
    for (const m of rest) (byKind[m.kind] ??= []).push(m);
    const order = ["profile", "preference", "constraint", "decision", "journey", "rejection_reason"];
    const kindOrder = Object.keys(byKind).sort((a, b) => {
      const ia = order.indexOf(a), ib = order.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
    return { people, byKind, kindOrder, restCount: rest.length };
  }, [data]);

  const resCount = data?.counts.research ?? 0;

  return (
    <main className="min-h-dvh bg-[#fffdf5] text-[#20242c]">
      <header className="sticky top-0 z-10 border-b border-[#eee6b8] bg-[#fffdf5]/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-5 py-3">
          <span className="grid size-9 place-items-center rounded-xl bg-[#fff078] text-lg">🧠</span>
          <div>
            <h1 className="text-[15px] font-black leading-tight">MyMinion — Knowledge</h1>
            <p className="text-[11px] text-zinc-500">Everything Moss knows · what Bright Data enriched</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div className="flex items-center gap-1.5 rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs shadow-sm">
              <span className="text-zinc-400">user</span>
              <input value={userId} onChange={e => setUserId(e.target.value)} className="w-24 bg-transparent font-semibold outline-none" />
            </div>
            <button
              onClick={() => setAuto(a => !a)}
              className="flex items-center gap-1.5 rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-600 shadow-sm"
            >
              <span className={`size-1.5 rounded-full ${auto ? "animate-pulse bg-emerald-500" : "bg-zinc-300"}`} />
              {auto ? "Live" : "Paused"}
            </button>
            <button onClick={() => void load()} className="rounded-full bg-black px-4 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-zinc-800">
              {loading ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-5 py-6">
        <div className="flex flex-wrap items-center gap-2">
          <Stat value={data?.counts.memories ?? 0} label="memories" tone="bg-[#fff9d9] text-[#6b5600] border-[#ead66c]" />
          <Stat value={people.length} label="people" tone="bg-fuchsia-50 text-fuchsia-700 border-fuchsia-100" />
          <Stat value={resCount} label="research docs" tone="bg-emerald-50 text-emerald-700 border-emerald-100" />
          <span className="ml-auto text-[11px] text-zinc-400">{updatedAt ? `updated ${timeAgo(new Date(updatedAt).toISOString())}` : ""}</span>
        </div>

        {err && <p className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{err}</p>}

        {/* People — full width */}
        {people.length > 0 && (
          <section className="mt-6">
            <SectionTitle icon="👥" title="People" count={people.length} />
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {people.map((p, i) => (
                <article key={i} className="rounded-2xl border border-fuchsia-100 bg-white p-4 shadow-sm">
                  <div className="flex items-center gap-2.5">
                    <span className="grid size-9 shrink-0 place-items-center rounded-full bg-fuchsia-100 text-sm font-black text-fuchsia-700">
                      {p.name.charAt(0).toUpperCase()}
                    </span>
                    <p className="min-w-0 flex-1 truncate text-sm font-bold">{p.name}</p>
                    <span className="shrink-0 text-[10px] text-zinc-400">{timeAgo(p.created_at)}</span>
                  </div>
                  <p className="mt-2.5 line-clamp-4 text-[13px] leading-5 text-zinc-600">{p.detail}</p>
                </article>
              ))}
            </div>
          </section>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.3fr_1fr]">
          {/* Memories */}
          <section>
            <SectionTitle icon="🧠" title="Moss memory" count={restCount} />
            {kindOrder.length === 0 && (
              <p className="mt-3 rounded-2xl border border-dashed border-zinc-200 bg-white p-6 text-center text-sm text-zinc-400">
                No memories yet. Open the app in <b>Listen mode</b> and talk — facts appear here within seconds.
              </p>
            )}
            <div className="mt-3 space-y-5">
              {kindOrder.map(kind => {
                const m = meta(kind);
                return (
                  <div key={kind}>
                    <div className="mb-2 flex items-center gap-2">
                      <span className={`size-2 rounded-full ${m.dot}`} />
                      <span className="text-[11px] font-black uppercase tracking-wider text-zinc-500">{m.label}</span>
                      <span className="text-[11px] text-zinc-300">{byKind[kind].length}</span>
                    </div>
                    <div className="space-y-1.5">
                      {byKind[kind].map((item, i) => {
                        const tag = sourceTag(item.source);
                        return (
                          <div key={item.id ?? i} className="flex items-start gap-3 rounded-xl border border-zinc-100 bg-white px-3.5 py-2.5 shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:border-zinc-200">
                            <span className={`mt-1.5 size-1.5 shrink-0 rounded-full ${m.dot}`} />
                            <p className="flex-1 text-[13px] leading-5 text-zinc-700">{item.content}</p>
                            <div className="flex shrink-0 flex-col items-end gap-1">
                              <span className="text-[10px] text-zinc-300">{timeAgo(item.created_at)}</span>
                              {tag && <span className={`rounded px-1.5 py-0.5 text-[9px] font-semibold ${tag.className}`}>{tag.text}</span>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Research */}
          <section>
            <SectionTitle icon="🔎" title="Bright Data enrichment" count={resCount} />
            {resCount === 0 && (
              <p className="mt-3 rounded-2xl border border-dashed border-zinc-200 bg-white p-6 text-center text-sm text-zinc-400">
                No live research yet. Ask the agent to research something, or mention a person.
              </p>
            )}
            <div className="mt-3 space-y-2">
              {data?.research.map((r, i) => (
                <article key={i} className="rounded-2xl border border-zinc-100 bg-white p-3.5 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[13px] font-bold leading-5 text-zinc-800">{r.title || r.topic || "Research"}</p>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold ${r.mock ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>
                      {r.mock ? "mock" : "live"}
                    </span>
                  </div>
                  {r.topic && <p className="mt-0.5 text-[10px] font-medium text-fuchsia-500">↳ {r.topic}</p>}
                  <p className="mt-1.5 line-clamp-3 text-[12px] leading-5 text-zinc-500">{r.summary}</p>
                  <div className="mt-2 flex items-center gap-2 text-[10px] text-zinc-400">
                    {typeof r.confidence === "number" && <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-semibold">{Math.round(r.confidence * 100)}%</span>}
                    <span>{timeAgo(r.retrieved_at)}</span>
                    {r.source_url && (
                      <a href={r.source_url} target="_blank" rel="noreferrer" className="ml-auto max-w-[55%] truncate font-medium text-sky-600 hover:underline">
                        {r.source_url.replace(/^https?:\/\/(www\.)?/, "")}
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

function Stat({ value, label, tone }: { value: number; label: string; tone: string }) {
  return (
    <div className={`flex items-baseline gap-1.5 rounded-full border px-3.5 py-1.5 ${tone}`}>
      <span className="text-sm font-black">{value}</span>
      <span className="text-[11px] font-semibold opacity-80">{label}</span>
    </div>
  );
}

function SectionTitle({ icon, title, count }: { icon: string; title: string; count: number }) {
  return (
    <div className="flex items-center gap-2">
      <span>{icon}</span>
      <h2 className="text-sm font-black">{title}</h2>
      <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-bold text-zinc-500">{count}</span>
    </div>
  );
}

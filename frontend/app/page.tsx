"use client";

import {
  ArrowUp,
  Bot,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  Mic,
  Plane,
  Plus,
  ShoppingBag,
  Sparkles,
  Users,
  User,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import type { AgentResponse } from "../../shared/types/contracts";
import { Button } from "@/components/ui/button";
import { VoiceButton } from "@/components/voice-button";

type Message = { id: string; role: "user" | "agent"; text: string; result?: AgentResponse };

const starters = [
  { label: "Find the right product", prompt: "Help me choose noise-cancelling headphones under $400" },
  { label: "Plan a trip", prompt: "Plan a balanced 10-day trip to Japan" },
  { label: "Remember a conversation", prompt: "I spoke with Sarah at Acme about a partnership" },
];

const crew = [
  { name: "Buywise", job: "Finds & compares", icon: ShoppingBag, prompt: starters[0].prompt },
  { name: "Tripster", job: "Plans adventures", icon: Plane, prompt: starters[1].prompt },
  { name: "Connector", job: "Remembers people", icon: Users, prompt: starters[2].prompt },
];

export default function Chat() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeResult, setActiveResult] = useState<AgentResponse | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(event?: FormEvent, prompt = input) {
    event?.preventDefault();
    const text = prompt.trim();
    if (!text || loading) return;
    setMessages(current => [...current, { id: crypto.randomUUID(), role: "user", text }]);
    setInput("");
    setError("");
    setLoading(true);
    try {
      const response = await fetch("/api/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "demo-user", session_id: "web-demo", message: text }),
      });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Agent request failed");
      const result = (await response.json()) as AgentResponse;
      setMessages(current => [...current, {
        id: crypto.randomUUID(), role: "agent", text: result.message, result,
      }]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "MyMinion is unavailable");
    } finally {
      setLoading(false);
    }
  }

  function newChat() {
    setMessages([]);
    setActiveResult(null);
    setInput("");
  }

  function keepVoiceTranscript(line: { id: string; role: "user" | "agent"; text: string }) {
    setMessages(current => {
      const existing = current.findIndex(message => message.id === `voice-${line.id}`);
      const next = {
        id: `voice-${line.id}`,
        role: line.role,
        text: line.text,
      } as Message;
      if (existing < 0) return [...current, next];
      return current.map((message, index) => index === existing ? next : message);
    });
  }

  return (
    <main className="myminion-light flex h-dvh bg-white text-[#202124]">
      <section className="flex min-w-0 flex-1 flex-col bg-white">
        <header className="flex h-16 shrink-0 items-center border-b border-[#eee6b8] px-4 sm:px-6">
          <button onClick={newChat} className="flex items-center gap-3 text-left"><span className="minion-face size-9"/><span><span className="block text-sm font-black">Mission Control</span><span className="block text-[9px] font-bold uppercase tracking-wider text-zinc-400">MyMinion</span></span></button>
          <span className="ml-4 rounded-full bg-[#fff078] px-2.5 py-1 text-[10px] font-bold text-[#725b00]">3 specialists ready</span>
          <div className="ml-auto flex items-center gap-2 text-xs text-zinc-500">
            <span className="size-2 rounded-full bg-emerald-400"/> Voice ready
          </div>
        </header>

        <div className="flex min-h-0 flex-1">
          <div className="mx-auto flex min-w-0 w-full max-w-5xl flex-1 flex-col">
            <div className="flex-1 overflow-y-auto">
              {messages.length === 0 ? (
                <div className="mx-auto flex h-full max-w-3xl flex-col justify-center px-6 pb-20">
                  <div className="flex -space-x-3">{crew.map((member, index) => <span key={member.name} className="minion-face size-14 border-[3px] border-white" style={{transform:`rotate(${(index-1)*5}deg)`, zIndex:3-index}}/>)}</div>
                  <h1 className="mt-6 text-3xl font-black tracking-tight">Give your minions a mission.</h1>
                  <p className="mt-3 max-w-xl text-sm leading-6 text-zinc-500">Speak naturally. The right specialist will research, compare, remember, and keep working until the mission is done.</p>
                  <div className="mt-8 grid gap-3 sm:grid-cols-3">
                    {starters.map(item => <button key={item.label} onClick={() => void send(undefined, item.prompt)} className="crew-card group rounded-2xl border border-zinc-200 bg-white p-4 text-left"><p className="text-sm font-bold">{item.label}</p><p className="mt-2 text-xs leading-5 text-zinc-500">{item.prompt}</p><ChevronRight className="mt-4 text-[#315fae]" size={16}/></button>)}
                  </div>
                </div>
              ) : (
                <div className="mx-auto w-full max-w-4xl px-5 py-8">
                  {messages.map(message => <article key={message.id} className="mb-8 flex gap-4">
                    <span className={`grid size-8 shrink-0 place-items-center rounded-full ${message.role === "agent" ? "bg-acid text-black" : "bg-zinc-800"}`}>{message.role === "agent" ? <Bot size={16}/> : <User size={15}/>}</span>
                    <div className="min-w-0 flex-1 pt-1"><p className="mb-1 text-xs font-semibold text-zinc-500">{message.role === "agent" ? "MyMinion" : "You"}</p><p className="whitespace-pre-wrap text-[15px] leading-7 text-zinc-700">{message.text}</p>{message.result && hasResults(message.result) && <MissionResult result={message.result}/>}</div>
                  </article>)}
                  {activeResult && hasResults(activeResult) && <article className="mb-8 flex gap-4"><span className="minion-face size-9 shrink-0"/><div className="min-w-0 flex-1"><p className="mb-2 text-xs font-bold text-zinc-500">Voice mission completed</p><MissionResult result={activeResult}/></div></article>}
                  {loading && <div className="mb-8 flex gap-4"><span className="minion-face minion-working size-9 shrink-0"/><div className="pt-1"><p className="text-xs font-bold text-zinc-700">A minion is working…</p><div className="minion-progress mt-2 h-2 w-44 rounded-full bg-[#315fae]"/></div></div>}
                  {error && <p className="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
                  <div ref={endRef}/>
                </div>
              )}
            </div>

            <div className="bg-gradient-to-t from-white via-white to-transparent px-4 pb-5 pt-4">
              <form onSubmit={event => void send(event)} className="mx-auto flex min-h-[66px] max-w-4xl items-center gap-2 rounded-[34px] border-2 border-[#ead66c] bg-white px-3 py-2 shadow-[0_8px_30px_rgba(95,77,0,.10)] focus-within:border-[#e3bd00]">
                <button type="button" className="grid size-10 shrink-0 place-items-center rounded-full text-zinc-800 hover:bg-zinc-100" aria-label="Add attachment"><Plus size={25}/></button>
                <textarea value={input} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }} rows={1} placeholder="Give your minions a mission…" className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-3 text-[17px] text-zinc-800 outline-none placeholder:text-zinc-400"/>
                <span className="hidden text-sm text-zinc-400 sm:block">Instant</span>
                <Mic size={21} className="mx-1 hidden text-zinc-800 sm:block"/>
                <VoiceButton onResult={setActiveResult} onTranscript={keepVoiceTranscript}/>
                {input.trim() && <Button type="submit" size="icon" disabled={loading} className="size-10 shrink-0 rounded-full bg-black text-white hover:bg-zinc-800"><ArrowUp size={17}/></Button>}
              </form>
              <p className="mt-2 text-center text-[10px] text-zinc-700">MyMinion researches current sources and may ask before taking consequential actions.</p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function hasResults(result: AgentResponse) {
  return Boolean(result.recommendations.length || result.research.length || result.contact_intelligence || result.journey.tasks.length);
}

function MissionResult({ result }: { result: AgentResponse }) {
  const buywise = result.recommendations[0]?.attributes.provider === "buywise";
  return <section className="mt-5 rounded-3xl border border-[#e1d9ab] bg-[#f7f3ea] p-4 text-zinc-900 shadow-[0_12px_36px_rgba(80,65,0,.08)] sm:p-5">
    <div><p className="text-[10px] font-semibold uppercase tracking-[.16em] text-[#806800]">{result.use_case.replaceAll("_", " ")}</p><h2 className="mt-1 font-black">Mission results</h2></div>
    <MissionReceipt result={result}/>
    {buywise ? <BuywiseResults recommendations={result.recommendations}/> : result.recommendations.length > 0 && <section className="mt-6 space-y-3"><Label text="Recommendations"/>{result.recommendations.map((item, index) => <RecommendationCard key={item.id} item={item} index={index}/>)}</section>}
    {result.research.length > 0 && <section className="mt-7 space-y-3"><Label text="Bright Data evidence"/>{result.research.map(item => <article key={item.id} className="rounded-2xl border border-[#dedbd2] bg-white p-4"><div className="flex items-center justify-between"><span className="rounded-full bg-emerald-50 px-2 py-1 text-[9px] font-bold text-emerald-700">Bright Data · {Math.round(item.confidence * 100)}% confidence</span><span className="text-[9px] text-zinc-400">{new Date(item.retrieved_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span></div><h3 className="mt-3 text-sm font-bold">{item.title}</h3><p className="mt-2 text-xs leading-5 text-zinc-500">{item.summary}</p><a href={item.source} target="_blank" rel="noreferrer" className="mt-3 flex items-center gap-1 truncate text-[10px] font-bold text-[#315fae]">Open source <ExternalLink size={10}/></a></article>)}</section>}
    {result.contact_intelligence && <section className="mt-7"><Label text="Contact intelligence"/><article className="mt-3 rounded-2xl border border-white/10 p-4"><h3 className="font-semibold">{result.contact_intelligence.name ?? "Contact"}</h3><p className="mt-1 text-xs text-zinc-500">{[result.contact_intelligence.role, result.contact_intelligence.company].filter(Boolean).join(" · ")}</p>{result.contact_intelligence.follow_ups.map(item => <p key={item} className="mt-3 text-xs leading-5 text-zinc-300">→ {item}</p>)}</article></section>}
    {[...result.memories_saved, ...result.memories_used].length > 0 && <section className="mt-7"><Label text="Moss persona"/><div className="mt-3 space-y-2">{[...result.memories_saved, ...result.memories_used].map(memory => <article key={memory.id} className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-3"><p className="text-[9px] font-semibold uppercase tracking-wider text-indigo-500">{memory.kind.replaceAll("_", " ")}</p><p className="mt-1 text-xs text-zinc-700">{memory.content}</p></article>)}</div></section>}
    <section className="mt-7"><Label text="What I’m working on"/><div className="mt-3 space-y-3">{result.journey.tasks.map(task => <div key={task.id} className="flex gap-3 text-xs"><CheckCircle2 size={15} className={task.status === "completed" ? "text-emerald-400" : "text-zinc-700"}/><div><p className="font-medium text-zinc-300">{task.title}</p><p className="mt-1 leading-5 text-zinc-600">{task.description}</p></div></div>)}</div></section>
  </section>;
}

function MissionReceipt({ result }: { result: AgentResponse }) {
  const steps = [
    { label: "Goal understood", detail: result.journey.goal, complete: true },
    { label: "Moss memory recalled", detail: result.memories_used.length ? `${result.memories_used.length} relevant memories influenced this mission` : "No prior matching memory—clean first run", complete: true },
    { label: "Bright Data researched", detail: `${result.research.length} current sources retrieved`, complete: result.research.length > 0 },
    { label: "Specialist ranked options", detail: `${result.recommendations.length} recommendations compared`, complete: result.recommendations.length > 0 || Boolean(result.contact_intelligence) },
    { label: "Moss updated", detail: `${result.memories_saved.length} new memories plus journey evidence persisted`, complete: result.memories_saved.length > 0 },
  ];
  return <section className="mt-5 rounded-2xl border border-[#dfce69] bg-[#fff9d9] p-4">
    <div className="flex items-center justify-between"><div><p className="text-[9px] font-black uppercase tracking-[.16em] text-[#806800]">Live mission receipt</p><p className="mt-1 text-xs text-zinc-600">Only completed backend activity is shown.</p></div><span className="rounded-full bg-emerald-100 px-2.5 py-1 text-[9px] font-black text-emerald-700">VERIFIED</span></div>
    <div className="mt-4 space-y-3">{steps.map((step, index) => <div key={step.label} className="grid grid-cols-[24px_1fr] gap-3"><span className={`grid size-6 place-items-center rounded-full text-[9px] font-black ${step.complete ? "bg-[#315fae] text-white" : "bg-white text-zinc-400"}`}>{step.complete ? <CheckCircle2 size={13}/> : index + 1}</span><div><p className="text-[11px] font-black text-zinc-800">{step.label}</p><p className="mt-0.5 text-[10px] leading-4 text-zinc-500">{step.detail}</p></div></div>)}</div>
    {result.memories_used.length > 0 && <div className="mt-4 border-t border-[#eadc8e] pt-3"><p className="text-[9px] font-black uppercase tracking-wider text-[#806800]">How Moss personalized this</p>{result.memories_used.map(memory => <p key={memory.id} className="mt-2 rounded-lg bg-white/70 px-3 py-2 text-[10px] leading-4 text-zinc-700"><span className="font-black text-[#315fae]">Recalled {memory.kind.replaceAll("_", " ")}:</span> {memory.content}</p>)}</div>}
    {result.memories_saved.length > 0 && <div className="mt-3"><p className="text-[9px] font-black uppercase tracking-wider text-[#806800]">What Moss remembers next time</p>{result.memories_saved.map(memory => <p key={memory.id} className="mt-2 rounded-lg bg-white/70 px-3 py-2 text-[10px] leading-4 text-zinc-700"><span className="font-black text-emerald-700">Saved {memory.kind.replaceAll("_", " ")}:</span> {memory.content}</p>)}</div>}
  </section>;
}

function Label({ text }: { text: string }) { return <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-zinc-600">{text}</p>; }

function RecommendationCard({ item, index }: { item: AgentResponse["recommendations"][number]; index: number }) {
  const price = typeof item.attributes.price === "number" ? item.attributes.price : null;
  const url = typeof item.attributes.url === "string" ? item.attributes.url : null;
  const retailer = typeof item.attributes.retailer === "string" ? item.attributes.retailer : null;
  const fromBuywise = item.attributes.provider === "buywise";
  return <article className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
    <div className="flex items-center justify-between"><span className="text-xs font-medium text-indigo-600">#{index + 1}</span><span className="text-[10px] text-zinc-500">{Math.round(item.score * 100)}% match</span></div>
    {fromBuywise && <p className="mt-3 text-[9px] font-semibold uppercase tracking-wider text-indigo-500">Bright Data Browser API → Buywise</p>}
    <h3 className="mt-2 text-sm font-semibold">{item.title}</h3>
    <div className="mt-2 flex items-center gap-2 text-xs text-zinc-500">{retailer && <span>{retailer}</span>}{price !== null && <span className="font-semibold text-zinc-900">${price.toFixed(2)}</span>}</div>
    <p className="mt-2 text-xs leading-5 text-zinc-500">{item.rationale}</p>
    {item.tradeoffs.length > 0 && <p className="mt-2 text-[10px] leading-4 text-amber-700">Check: {item.tradeoffs.slice(0, 2).join(" · ")}</p>}
    {url && <a href={url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-indigo-600">View verified offer <ExternalLink size={11}/></a>}
  </article>;
}

function BuywiseResults({ recommendations }: { recommendations: AgentResponse["recommendations"] }) {
  const winner = recommendations[0];
  if (!winner) return null;
  const attrs = winner.attributes;
  const price = typeof attrs.price === "number" ? attrs.price : null;
  const url = typeof attrs.url === "string" ? attrs.url : null;
  const retailer = typeof attrs.retailer === "string" ? attrs.retailer : "Verified retailer";
  const coverage = (attrs.coverage ?? {}) as { discovered?: number; scraped?: number; failed?: number; notes?: string[] };
  const themes = Array.isArray(attrs.customer_themes) ? attrs.customer_themes as Array<{ theme?: string; sentiment?: string; mentions?: number; summary?: string; sources?: string[] }> : [];
  const activities = Array.isArray(attrs.activities) ? attrs.activities as Array<{ id?: string; title?: string; detail?: string; status?: string }> : [];
  const checklist = Array.isArray(attrs.buying_checklist) ? attrs.buying_checklist as string[] : [];
  const confidence = typeof attrs.recommendation_confidence === "number" ? attrs.recommendation_confidence : winner.score;
  return <div className="mt-6 space-y-6">
    <section className="rounded-[22px] bg-[#173f35] p-5 text-white shadow-[0_12px_35px_rgba(23,63,53,.18)]">
      <p className="text-[10px] font-black uppercase tracking-[.14em] text-[#9bc4b8]">Best available match</p>
      <h2 className="mt-2 text-xl font-black leading-tight">{winner.title}</h2>
      <p className="mt-1 text-xs text-[#b8d2cb]">Sold by {retailer}</p>
      {price !== null && <p className="mt-3 font-serif text-4xl font-bold">${price.toFixed(2)}</p>}
      <p className="mt-3 text-xs leading-5 text-[#d5e2de]">{winner.rationale}</p>
      <div className="mt-4 flex flex-wrap gap-2"><ResultPill text={`${Math.round(winner.score * 100)}/100`}/><ResultPill text={`${Math.round(confidence * 100)}% confidence`}/><ResultPill text="Bright Data Browser API"/><ResultPill text="Buywise verified"/></div>
      {url && <a href={url} target="_blank" rel="noreferrer" className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-[#e95d32] px-4 py-3 text-xs font-black text-white">View verified offer <ExternalLink size={13}/></a>}
    </section>
    <section><div className="flex items-end justify-between"><div><Label text="Offer coverage"/><h3 className="mt-1 text-lg font-black">Compare top offers</h3></div><span className="text-[10px] text-zinc-500">{coverage.discovered ?? 0} pages · {coverage.scraped ?? recommendations.length} extracted · {coverage.failed ?? 0} unavailable</span></div><div className="mt-3 space-y-2">{recommendations.map((item, index) => <BuywiseOffer key={item.id} item={item} index={index}/>)}</div></section>
    {themes.length > 0 && <section><Label text="Voice of customer"/><div className="mt-3 space-y-2">{themes.slice(0, 5).map(theme => <article key={theme.theme} className="grid grid-cols-[30px_1fr] gap-3 rounded-xl border border-[#dedbd2] bg-white p-3"><span className={`grid size-7 place-items-center rounded-full text-xs font-black ${theme.sentiment === "positive" ? "bg-emerald-100 text-emerald-700" : theme.sentiment === "negative" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}>{theme.sentiment === "positive" ? "+" : theme.sentiment === "negative" ? "−" : "±"}</span><div><p className="text-xs font-bold">{theme.theme}</p><p className="mt-1 text-[11px] leading-4 text-zinc-500">{theme.summary}</p><p className="mt-1 text-[9px] text-zinc-400">{theme.mentions ?? 0} supporting sources</p></div></article>)}</div></section>}
    {activities.length > 0 && <section><Label text="Agent investigation"/><div className="mt-3 rounded-2xl border border-[#dedbd2] bg-white p-4">{activities.slice(-6).map((activity, index) => <div key={activity.id ?? index} className="flex gap-3 border-b border-zinc-100 py-2 last:border-0"><span className="font-black text-[#e95d32]">{activity.status === "failed" ? "!" : "✓"}</span><div><p className="text-xs font-bold">{activity.title}</p><p className="mt-0.5 text-[10px] leading-4 text-zinc-500">{activity.detail}</p></div></div>)}</div></section>}
    {checklist.length > 0 && <section><Label text="Before you buy"/><div className="mt-3 rounded-2xl border border-[#dedbd2] bg-white p-4">{checklist.map(item => <p key={item} className="flex gap-2 py-1.5 text-xs text-zinc-600"><CheckCircle2 size={14} className="shrink-0 text-[#173f35]"/>{item}</p>)}</div><p className="mt-3 text-center text-[10px] text-zinc-400">Your minion never purchases without approval.</p></section>}
  </div>;
}

function BuywiseOffer({ item, index }: { item: AgentResponse["recommendations"][number]; index: number }) {
  const attrs = item.attributes;
  const price = typeof attrs.price === "number" ? attrs.price : null;
  const url = typeof attrs.url === "string" ? attrs.url : null;
  const retailer = typeof attrs.retailer === "string" ? attrs.retailer : "Retailer";
  const returnDays = typeof attrs.return_days === "number" ? `${attrs.return_days}-day returns` : "Verify returns";
  const warranty = typeof attrs.warranty === "string" ? attrs.warranty : "Verify warranty";
  return <article className="grid grid-cols-[30px_1fr_auto] gap-3 rounded-xl border border-[#dedbd2] bg-white p-3"><span className="grid size-7 place-items-center rounded-lg bg-[#e6ebe8] text-[10px] font-black">{index + 1}</span><div className="min-w-0"><h4 className="text-xs font-black leading-4">{item.title}</h4><p className="mt-1 text-[10px] text-zinc-500">{retailer} · {String(attrs.condition ?? "new")} · {String(attrs.match ?? "verified")}</p><div className="mt-2 space-y-0.5 text-[9px] leading-4 text-[#516b64]"><p>• {returnDays}</p><p>• {warranty}</p><p>• {String(attrs.availability ?? "Availability verified at research time")}</p></div>{item.tradeoffs.slice(0, 2).map(warning => <p key={warning} className="mt-1 text-[9px] text-[#a74e2f]">⚠ {warning}</p>)}{url && <a href={url} target="_blank" rel="noreferrer" className="mt-2 inline-flex text-[10px] font-bold text-[#0b6251] underline">Verify at retailer ↗</a>}</div><div className="text-right">{price !== null && <p className="text-sm font-black">${price.toFixed(2)}</p>}<p className="text-[9px] text-zinc-400">{Math.round(item.score * 100)}/100</p></div></article>;
}

function ResultPill({ text }: { text: string }) { return <span className="rounded-full bg-white/10 px-2.5 py-1 text-[9px] font-bold">{text}</span>; }

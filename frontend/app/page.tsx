"use client";

import {
  ArrowUp,
  Bot,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  Menu,
  Mic,
  PanelRightClose,
  Plus,
  Sparkles,
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

export default function Chat() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeResult, setActiveResult] = useState<AgentResponse | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, loading]);

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
      setActiveResult(result);
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

  return (
    <main className="myminion-light flex h-dvh bg-white text-[#202124]">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-zinc-200 bg-[#f7f7f8] p-3 md:flex">
        <button onClick={newChat} className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm hover:bg-white/5">
          <span className="grid size-8 place-items-center rounded-xl bg-acid text-black"><Sparkles size={16}/></span>
          <span className="font-semibold">MyMinion</span><Plus className="ml-auto" size={16}/>
        </button>
        <p className="mt-8 px-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-600">Recent</p>
        <button className="mt-2 truncate rounded-lg bg-white/5 px-3 py-2 text-left text-sm text-zinc-300">
          {messages.find(message => message.role === "user")?.text ?? "New conversation"}
        </button>
        <div className="mt-auto rounded-xl border border-white/10 p-3 text-xs leading-5 text-zinc-500">
          <p className="font-medium text-zinc-300">Memory is on</p>
          Preferences and decisions carry into future conversations through Moss.
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col bg-white">
        <header className="flex h-14 shrink-0 items-center border-b border-white/10 px-4">
          <Button variant="ghost" size="icon" className="md:hidden"><Menu size={18}/></Button>
          <div className="ml-2 flex items-center gap-2 text-sm font-semibold md:ml-0">
            MyMinion <span className="rounded-md bg-white/5 px-2 py-1 text-[10px] font-medium text-zinc-500">Agent</span>
          </div>
          <div className="ml-auto flex items-center gap-2 text-xs text-zinc-500">
            <span className="size-2 rounded-full bg-emerald-400"/> Voice ready
          </div>
        </header>

        <div className="flex min-h-0 flex-1">
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="flex-1 overflow-y-auto">
              {messages.length === 0 ? (
                <div className="mx-auto flex h-full max-w-3xl flex-col justify-center px-6 pb-20">
                  <div className="grid size-12 place-items-center rounded-2xl bg-acid text-black shadow-[0_0_35px_rgba(205,255,64,.12)]"><Sparkles size={22}/></div>
                  <h1 className="mt-6 text-3xl font-semibold tracking-tight">What can I take care of?</h1>
                  <p className="mt-3 max-w-xl text-sm leading-6 text-zinc-500">Talk naturally. I’ll understand whether you’re buying, traveling, following up with someone, or handling another life task—then plan, research, and remember what matters.</p>
                  <div className="mt-8 grid gap-3 sm:grid-cols-3">
                    {starters.map(item => <button key={item.label} onClick={() => void send(undefined, item.prompt)} className="group rounded-2xl border border-white/10 bg-white/[.025] p-4 text-left transition hover:border-white/20 hover:bg-white/5"><p className="text-sm font-medium">{item.label}</p><p className="mt-2 text-xs leading-5 text-zinc-600">{item.prompt}</p><ChevronRight className="mt-4 text-zinc-700 group-hover:text-acid" size={16}/></button>)}
                  </div>
                </div>
              ) : (
                <div className="mx-auto max-w-3xl px-5 py-8">
                  {messages.map(message => <article key={message.id} className="mb-8 flex gap-4">
                    <span className={`grid size-8 shrink-0 place-items-center rounded-full ${message.role === "agent" ? "bg-acid text-black" : "bg-zinc-800"}`}>{message.role === "agent" ? <Bot size={16}/> : <User size={15}/>}</span>
                    <div className="min-w-0 pt-1"><p className="mb-1 text-xs font-semibold text-zinc-500">{message.role === "agent" ? "MyMinion" : "You"}</p><p className="whitespace-pre-wrap text-[15px] leading-7 text-zinc-200">{message.text}</p>{message.result && hasResults(message.result) && <button onClick={() => setActiveResult(message.result ?? null)} className="mt-4 rounded-lg border border-white/10 px-3 py-2 text-xs text-zinc-400 hover:bg-white/5 hover:text-white">View results</button>}</div>
                  </article>)}
                  {loading && <div className="mb-8 flex gap-4"><span className="grid size-8 place-items-center rounded-full bg-acid text-black"><Bot size={16}/></span><div className="flex gap-1 pt-3">{[0,1,2].map(i => <span key={i} className="size-1.5 animate-pulse rounded-full bg-zinc-500" style={{animationDelay:`${i*150}ms`}}/>)}</div></div>}
                  {error && <p className="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
                  <div ref={endRef}/>
                </div>
              )}
            </div>

            <div className="bg-gradient-to-t from-white via-white to-transparent px-4 pb-5 pt-4">
              <form onSubmit={event => void send(event)} className="mx-auto flex min-h-[66px] max-w-4xl items-center gap-2 rounded-[34px] border border-zinc-200 bg-white px-3 py-2 shadow-[0_8px_30px_rgba(0,0,0,.08)] focus-within:border-zinc-300">
                <button type="button" className="grid size-10 shrink-0 place-items-center rounded-full text-zinc-800 hover:bg-zinc-100" aria-label="Add attachment"><Plus size={25}/></button>
                <textarea value={input} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }} rows={1} placeholder="Ask MyMinion" className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-3 text-[17px] text-zinc-800 outline-none placeholder:text-zinc-400"/>
                <span className="hidden text-sm text-zinc-400 sm:block">Instant</span>
                <Mic size={21} className="mx-1 hidden text-zinc-800 sm:block"/>
                <VoiceButton onResult={setActiveResult}/>
                {input.trim() && <Button type="submit" size="icon" disabled={loading} className="size-10 shrink-0 rounded-full bg-black text-white hover:bg-zinc-800"><ArrowUp size={17}/></Button>}
              </form>
              <p className="mt-2 text-center text-[10px] text-zinc-700">MyMinion researches current sources and may ask before taking consequential actions.</p>
            </div>
          </div>

          {activeResult && hasResults(activeResult) && <ResultsPanel result={activeResult} close={() => setActiveResult(null)}/>} 
        </div>
      </section>
    </main>
  );
}

function hasResults(result: AgentResponse) {
  return Boolean(result.recommendations.length || result.research.length || result.contact_intelligence || result.journey.tasks.length);
}

function ResultsPanel({ result, close }: { result: AgentResponse; close: () => void }) {
  return <aside className="fixed inset-y-0 right-0 z-40 w-[min(92vw,380px)] shrink-0 overflow-y-auto border-l border-zinc-200 bg-white p-4 text-zinc-900 shadow-2xl xl:static xl:z-auto xl:w-[360px] xl:shadow-none">
    <div className="flex items-center justify-between"><div><p className="text-[10px] font-semibold uppercase tracking-[.16em] text-acid">{result.use_case.replaceAll("_", " ")}</p><h2 className="mt-1 font-semibold">Results</h2></div><Button variant="ghost" size="icon" onClick={close}><PanelRightClose size={17}/></Button></div>
    {result.recommendations.length > 0 && <section className="mt-6 space-y-3"><Label text="Recommendations"/>{result.recommendations.map((item, index) => <article key={item.id} className="rounded-2xl border border-white/10 bg-white/[.025] p-4"><div className="flex items-center justify-between"><span className="text-xs font-medium text-acid">#{index + 1}</span><span className="text-[10px] text-zinc-600">{Math.round(item.score * 100)}% match</span></div><h3 className="mt-2 text-sm font-semibold">{item.title}</h3><p className="mt-2 text-xs leading-5 text-zinc-500">{item.rationale}</p></article>)}</section>}
    {result.research.length > 0 && <section className="mt-7 space-y-3"><Label text="Research"/>{result.research.map(item => <article key={item.id} className="rounded-2xl border border-white/10 p-4"><div className="flex items-center justify-between"><span className="text-[10px] text-zinc-600">{Math.round(item.confidence * 100)}% confidence</span><ExternalLink size={12} className="text-zinc-600"/></div><h3 className="mt-2 text-sm font-medium">{item.title}</h3><p className="mt-2 text-xs leading-5 text-zinc-500">{item.summary}</p><p className="mt-3 truncate text-[10px] text-zinc-700">{item.source}</p></article>)}</section>}
    {result.contact_intelligence && <section className="mt-7"><Label text="Contact intelligence"/><article className="mt-3 rounded-2xl border border-white/10 p-4"><h3 className="font-semibold">{result.contact_intelligence.name ?? "Contact"}</h3><p className="mt-1 text-xs text-zinc-500">{[result.contact_intelligence.role, result.contact_intelligence.company].filter(Boolean).join(" · ")}</p>{result.contact_intelligence.follow_ups.map(item => <p key={item} className="mt-3 text-xs leading-5 text-zinc-300">→ {item}</p>)}</article></section>}
    <section className="mt-7"><Label text="What I’m working on"/><div className="mt-3 space-y-3">{result.journey.tasks.map(task => <div key={task.id} className="flex gap-3 text-xs"><CheckCircle2 size={15} className={task.status === "completed" ? "text-emerald-400" : "text-zinc-700"}/><div><p className="font-medium text-zinc-300">{task.title}</p><p className="mt-1 leading-5 text-zinc-600">{task.description}</p></div></div>)}</div></section>
  </aside>;
}

function Label({ text }: { text: string }) { return <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-zinc-600">{text}</p>; }

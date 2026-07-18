"use client";

import { AudioLines, Check, ExternalLink, Mic, MicOff, X } from "lucide-react";
import { Participant, Room, RoomEvent, Track, TranscriptionSegment } from "livekit-client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { AgentResponse } from "../../shared/types/contracts";

type TokenResponse = { server_url: string; participant_token: string };

type TranscriptLine = { id: string; role: "user" | "agent"; text: string; final: boolean };

export function VoiceButton({
  onResult,
  onTranscript,
  mode = "ask",
}: {
  onResult?: (result: AgentResponse) => void;
  onTranscript?: (line: TranscriptLine) => void;
  mode?: "ambient" | "ask";
}) {
  const roomRef = useRef<Room | null>(null);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [speaker, setSpeaker] = useState<"user" | "agent" | "idle">("idle");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [progress, setProgress] = useState("");
  const [progressMemories, setProgressMemories] = useState<string[]>([]);
  const [connectionError, setConnectionError] = useState("");
  const [missionError, setMissionError] = useState("");
  const [muted, setMuted] = useState(false);
  const [voiceResult, setVoiceResult] = useState<AgentResponse | null>(null);
  const [scribe, setScribe] = useState<{ heard: string; saved: number; researched: number } | null>(null);

  useEffect(() => {
    return () => {
      const room = roomRef.current;
      roomRef.current = null;
      if (room) void room.disconnect();
    };
  }, []);

  async function toggleVoice() {
    if (roomRef.current) {
      await roomRef.current.disconnect();
      roomRef.current = null;
      setConnected(false);
      return;
    }
    setBusy(true);
    setConnectionError("");
    setMissionError("");
    setVoiceResult(null);
    setProgress("");
    setProgressMemories([]);
    setTranscript([]);
    try {
      const response = await fetch("/api/livekit/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ participant_name: "Web user", mode }),
      });
      if (!response.ok) throw new Error("Unable to start voice");
      const credentials = (await response.json()) as TokenResponse;
      const room = new Room({ adaptiveStream: true, dynacast: true });
      room.on(RoomEvent.ActiveSpeakersChanged, (speakers: Participant[]) => {
        if (speakers.some(person => person.identity === room.localParticipant.identity)) {
          setSpeaker("user");
        } else if (speakers.length) {
          setSpeaker("agent");
        } else {
          setSpeaker("idle");
        }
      });
      room.on(RoomEvent.TranscriptionReceived, (
        segments: TranscriptionSegment[], participant?: Participant,
      ) => {
        const role: TranscriptLine["role"] =
          participant?.identity === room.localParticipant.identity ? "user" : "agent";
        const lines = segments.map(segment => ({
          id: segment.id,
          role,
          text: segment.text,
          final: segment.final,
        }));
        setTranscript(current => {
          const next = [...current];
          for (const line of lines) {
            const index = next.findIndex(item => item.id === line.id);
            if (index >= 0) next[index] = line; else next.push(line);
          }
          return next.slice(-12);
        });
        for (const line of lines) {
          if (line.final) onTranscript?.(line);
        }
      });
      room.on(RoomEvent.DataReceived, (payload, _participant, _kind, topic) => {
        try {
          const data = JSON.parse(new TextDecoder().decode(payload)) as AgentResponse & { stage?: string; memories?: string[]; error?: string; retrying?: boolean };
          if (topic === "myminion.progress") {
            setVoiceResult(null);
            setMissionError("");
            setProgress(data.stage ?? "Working on it");
            setProgressMemories(
              Array.isArray(data.memories) ? Array.from(new Set(data.memories)) : [],
            );
          }
          if (topic === "myminion.agent_result") {
            setProgress("Results ready");
            setMissionError("");
            setVoiceResult(data);
            onResult?.(data);
          }
          if (topic === "myminion.scribe") {
            setScribe(data as unknown as { heard: string; saved: number; researched: number });
          }
          if (topic === "myminion.error") {
            setProgress(data.stage ?? "Mission error");
            setMissionError(data.error ?? "A provider failed");
          }
        } catch { /* Ignore malformed third-party packets. */ }
      });
      room.on(RoomEvent.TrackSubscribed, track => {
        if (track.kind === Track.Kind.Audio) {
          const element = track.attach();
          element.dataset.myminionAudio = "true";
          document.body.appendChild(element);
        }
      });
      room.on(RoomEvent.TrackUnsubscribed, track => {
        track.detach().forEach(element => element.remove());
      });
      room.on(RoomEvent.Disconnected, () => {
        document.querySelectorAll("[data-myminion-audio]").forEach(element => element.remove());
        roomRef.current = null;
        setConnected(false);
        setSpeaker("idle");
        setProgress("");
        setScribe(null);
        setProgressMemories([]);
        setMissionError("");
      });
      await room.connect(credentials.server_url, credentials.participant_token);
      await room.startAudio();
      await room.localParticipant.setMicrophoneEnabled(true);
      setMuted(false);
      roomRef.current = room;
      setConnected(true);
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : "Voice could not start");
    } finally {
      setBusy(false);
    }
  }

  async function toggleMute() {
    const room = roomRef.current;
    if (!room) return;
    const next = !muted;
    await room.localParticipant.setMicrophoneEnabled(!next);
    setMuted(next);
    setSpeaker("idle");
  }

  const missionSteps = [
    "Listen & understand",
    "Retrieve Moss persona",
    "Research with Bright Data",
    "Run specialist minion",
    "Save evidence to Moss",
    "Deliver results",
  ];

  return <>
    <Button type="button" size="icon" disabled={busy}
      aria-label={connected ? "Stop voice" : "Start voice"}
      onClick={() => void toggleVoice()} className="size-11 shrink-0 rounded-full bg-black text-white hover:bg-zinc-800">
      {connected ? <MicOff size={19} /> : <AudioLines size={21} />}
    </Button>
    {connectionError && <p role="alert" className="absolute bottom-[-26px] right-2 text-[10px] font-semibold text-red-600">{connectionError}</p>}
    {connected && <div className="fixed inset-0 z-50 flex flex-col bg-[#fbfbfc] text-zinc-900">
      <header className="flex h-20 items-center justify-between px-6"><div className="flex items-center gap-3 text-sm font-black"><span className="minion-face size-9"/> {mode === "ambient" ? "Listening mode" : "Voice mission"} <span className="ml-1 inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-bold text-red-600"><span className="size-1.5 animate-pulse rounded-full bg-red-500"/> Scribe listening</span></div><button onClick={() => void toggleVoice()} className="grid size-10 place-items-center rounded-full border border-zinc-200 bg-white text-zinc-700 shadow-sm hover:bg-zinc-50"><X size={18}/></button></header>
      <div className="mx-auto grid min-h-0 w-full max-w-6xl flex-1 gap-8 overflow-y-auto px-6 pb-4 lg:grid-cols-[1fr_380px] lg:items-center">
        <div className="flex flex-col items-center justify-center">
        <div className={`minion-orb relative size-48 overflow-hidden rounded-full transition-all duration-500 sm:size-56 ${speaker === "agent" ? "opacity-100" : speaker === "user" ? "opacity-90" : "opacity-75"}`}>
          <span className="sr-only">{speaker === "agent" ? "MyMinion is speaking" : speaker === "user" ? "Listening to you" : "Listening"}</span>
        </div>
        <p className="mt-8 text-[15px] font-medium text-zinc-600">{speaker === "agent" ? "MyMinion is speaking" : speaker === "user" ? "Listening to you" : "Listening…"}</p>
        <p className="mt-2 text-center text-[11px] text-zinc-400">You can interrupt naturally. Once captured, your mission keeps running.</p>
        {progress && <p className="mt-3 rounded-full bg-indigo-50 px-4 py-2 text-xs text-indigo-600">{progress}</p>}
        {scribe && <p className="mt-3 max-w-md rounded-full bg-emerald-50 px-4 py-2 text-center text-xs text-emerald-700">Scribe noted &ldquo;{scribe.heard.slice(0, 60)}{scribe.heard.length > 60 ? "…" : ""}&rdquo; · saved {scribe.saved} · researched {scribe.researched}</p>}
        {missionError && <div role="alert" className="mt-3 max-w-xl rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-center"><p className="text-xs font-black text-amber-800">{missionError}</p><p className="mt-1 text-[10px] text-amber-700">{progress.toLowerCase().includes("retry") ? "MyMinion is retrying automatically." : "The complete retry also failed. You can start the mission again."}</p></div>}
        {progressMemories.length > 0 && !voiceResult && <div className="mt-3 flex max-w-xl flex-wrap justify-center gap-2">{progressMemories.map((memory, index) => <span key={`${index}-${memory}`} className="rounded-full border border-[#ead66c] bg-[#fff9d9] px-3 py-1.5 text-[10px] font-bold text-[#675400]">Moss → {memory}</span>)}</div>}
        <div className="mt-8 max-h-[28vh] w-full max-w-2xl space-y-3 overflow-y-auto px-4 text-center">
          {transcript.length === 0 ? <p className="text-sm text-zinc-400">Start speaking. Your live transcript will appear here.</p> : transcript.slice(-5).map(line => <div key={line.id}><p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">{line.role === "user" ? "You" : "MyMinion"}</p><p className={`mt-1 text-[15px] leading-6 ${line.final ? "text-zinc-700" : "text-zinc-400"}`}>{line.text}</p></div>)}
        </div>
        </div>
        <aside className="rounded-3xl border border-[#ead66c] bg-white p-5 shadow-[0_16px_50px_rgba(80,65,0,.10)]">
          <div className="flex items-center justify-between"><div><p className="text-[10px] font-black uppercase tracking-[.15em] text-[#806800]">Mission flow</p><h2 className="mt-1 font-black">Minions at work</h2></div><span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${voiceResult ? "bg-emerald-100 text-emerald-700" : progress ? "bg-amber-100 text-amber-700" : "bg-zinc-100 text-zinc-500"}`}>{voiceResult ? "Complete" : progress ? "Working" : "Ready"}</span></div>
          <div className="mt-5 space-y-3">{missionSteps.map((step, index) => { const done = Boolean(voiceResult) || index === 0 || (Boolean(progress) && index < 4); const active = !voiceResult && Boolean(progress) && index === 3; return <div key={step} className="flex items-center gap-3"><span className={`grid size-7 place-items-center rounded-full text-[10px] font-bold ${done ? "bg-[#315fae] text-white" : "bg-zinc-100 text-zinc-400"}`}>{done ? <Check size={13}/> : index + 1}</span><span className={`text-xs ${active ? "font-bold text-[#806800]" : "text-zinc-600"}`}>{step}</span>{active && <span className="ml-auto size-2 animate-pulse rounded-full bg-amber-400"/>}</div>})}</div>
          {voiceResult?.recommendations.length ? <div className="mt-6 border-t border-zinc-100 pt-4"><div className="grid grid-cols-3 gap-2 pb-3"><Metric value={voiceResult.memories_used.length} label="Moss recalled"/><Metric value={voiceResult.research.length} label="Bright sources"/><Metric value={voiceResult.memories_saved.length} label="Moss saved"/></div><div className="flex items-center justify-between"><p className="text-[10px] font-black uppercase tracking-wider text-zinc-400">Ranked verified offers</p><span className="text-[9px] font-bold text-emerald-600">Price required</span></div><div className="mt-3 max-h-[36vh] space-y-3 overflow-y-auto pr-1">{voiceResult.recommendations.slice(0, 5).map((item, index) => { const price = typeof item.attributes.price === "number" ? item.attributes.price : null; const url = typeof item.attributes.url === "string" ? item.attributes.url : null; const retailer = typeof item.attributes.retailer === "string" ? item.attributes.retailer : null; return <article key={item.id} className={`rounded-xl border p-3 ${index === 0 ? "border-[#e3bd00] bg-[#fff6b8]" : "border-zinc-200 bg-white"}`}><div className="flex items-start justify-between gap-3"><div><p className="text-[9px] font-black uppercase tracking-wider text-[#806800]">{index === 0 ? "Best priced match" : `Option ${index + 1}`}</p><p className="mt-1 text-xs font-bold leading-4">{item.title}</p></div>{price !== null && <span className="shrink-0 text-sm font-black">${price.toFixed(2)}</span>}</div><p className="mt-1 text-[10px] text-zinc-500">{Math.round(item.score * 100)}% match{retailer ? ` · ${retailer}` : ""}</p><p className="mt-2 text-[10px] leading-4 text-zinc-600">{item.rationale}</p><p className="mt-2 text-[9px] font-semibold text-[#315fae]">Bright Data SERP → retailer page verification → ranking</p>{url && <a href={url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[10px] font-bold text-[#315fae]">View verified offer <ExternalLink size={10}/></a>}</article>})}</div><p className="mt-3 text-[10px] leading-4 text-zinc-400">Close voice mode anytime—the complete comparison remains in Mission Results.</p></div> : voiceResult ? <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4"><p className="text-xs font-black text-amber-800">No verified priced offers yet</p><p className="mt-1 text-[10px] leading-4 text-amber-700">MyMinion will not show generic recommendations. Try again when an approved retailer returns a product page with a dollar price.</p></div> : <p className="mt-6 border-t border-zinc-100 pt-4 text-xs leading-5 text-zinc-400">Results will appear here only after priced retailer offers are verified.</p>}
        </aside>
      </div>
      <footer className="flex justify-center gap-4 p-7"><button onClick={() => void toggleMute()} className={`grid size-14 place-items-center rounded-full shadow-sm ${muted ? "bg-red-100 text-red-600" : "border border-zinc-200 bg-white text-zinc-800"}`} aria-label={muted ? "Unmute microphone" : "Mute microphone"}>{muted ? <MicOff size={22}/> : <Mic size={22}/>}</button><button onClick={() => void toggleVoice()} className="grid size-14 place-items-center rounded-full bg-black text-white shadow-lg hover:bg-zinc-800" aria-label="End voice mission"><X size={22}/></button></footer>
    </div>}
  </>;
}

function Metric({ value, label }: { value: number; label: string }) {
  return <div className="rounded-lg bg-zinc-50 p-2 text-center"><p className="text-sm font-black text-[#315fae]">{value}</p><p className="mt-0.5 text-[8px] font-bold uppercase tracking-wide text-zinc-400">{label}</p></div>;
}

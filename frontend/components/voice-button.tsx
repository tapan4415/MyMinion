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
}: {
  onResult?: (result: AgentResponse) => void;
  onTranscript?: (line: TranscriptLine) => void;
}) {
  const roomRef = useRef<Room | null>(null);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [speaker, setSpeaker] = useState<"user" | "agent" | "idle">("idle");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [progress, setProgress] = useState("");
  const [muted, setMuted] = useState(false);
  const [voiceResult, setVoiceResult] = useState<AgentResponse | null>(null);

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
    try {
      const response = await fetch("/api/livekit/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ participant_name: "Web user" }),
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
          const data = JSON.parse(new TextDecoder().decode(payload)) as AgentResponse & { stage?: string };
          if (topic === "myminion.progress") setProgress(data.stage ?? "Working on it");
          if (topic === "myminion.agent_result") {
            setProgress("Results ready");
            setVoiceResult(data);
            onResult?.(data);
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
      });
      await room.connect(credentials.server_url, credentials.participant_token);
      await room.startAudio();
      await room.localParticipant.setMicrophoneEnabled(true);
      setMuted(false);
      roomRef.current = room;
      setConnected(true);
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
    {connected && <div className="fixed inset-0 z-50 flex flex-col bg-[#fbfbfc] text-zinc-900">
      <header className="flex h-20 items-center justify-between px-6"><div className="flex items-center gap-3 text-sm font-black"><span className="minion-face size-9"/> Voice mission</div><button onClick={() => void toggleVoice()} className="grid size-10 place-items-center rounded-full border border-zinc-200 bg-white text-zinc-700 shadow-sm hover:bg-zinc-50"><X size={18}/></button></header>
      <div className="mx-auto grid min-h-0 w-full max-w-6xl flex-1 gap-8 overflow-y-auto px-6 pb-4 lg:grid-cols-[1fr_380px] lg:items-center">
        <div className="flex flex-col items-center justify-center">
        <div className={`minion-orb relative size-48 overflow-hidden rounded-full transition-all duration-500 sm:size-56 ${speaker === "agent" ? "opacity-100" : speaker === "user" ? "opacity-90" : "opacity-75"}`}>
          <span className="sr-only">{speaker === "agent" ? "MyMinion is speaking" : speaker === "user" ? "Listening to you" : "Listening"}</span>
        </div>
        <p className="mt-8 text-[15px] font-medium text-zinc-600">{speaker === "agent" ? "MyMinion is speaking" : speaker === "user" ? "Listening to you" : "Listening…"}</p>
        {progress && <p className="mt-3 rounded-full bg-indigo-50 px-4 py-2 text-xs text-indigo-600">{progress}</p>}
        <div className="mt-8 max-h-[28vh] w-full max-w-2xl space-y-3 overflow-y-auto px-4 text-center">
          {transcript.length === 0 ? <p className="text-sm text-zinc-400">Start speaking. Your live transcript will appear here.</p> : transcript.slice(-5).map(line => <div key={line.id}><p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">{line.role === "user" ? "You" : "MyMinion"}</p><p className={`mt-1 text-[15px] leading-6 ${line.final ? "text-zinc-700" : "text-zinc-400"}`}>{line.text}</p></div>)}
        </div>
        </div>
        <aside className="rounded-3xl border border-[#ead66c] bg-white p-5 shadow-[0_16px_50px_rgba(80,65,0,.10)]">
          <div className="flex items-center justify-between"><div><p className="text-[10px] font-black uppercase tracking-[.15em] text-[#806800]">Mission flow</p><h2 className="mt-1 font-black">Minions at work</h2></div><span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${voiceResult ? "bg-emerald-100 text-emerald-700" : progress ? "bg-amber-100 text-amber-700" : "bg-zinc-100 text-zinc-500"}`}>{voiceResult ? "Complete" : progress ? "Working" : "Ready"}</span></div>
          <div className="mt-5 space-y-3">{missionSteps.map((step, index) => { const done = Boolean(voiceResult) || index === 0 || (Boolean(progress) && index < 4); const active = !voiceResult && Boolean(progress) && index === 3; return <div key={step} className="flex items-center gap-3"><span className={`grid size-7 place-items-center rounded-full text-[10px] font-bold ${done ? "bg-[#315fae] text-white" : "bg-zinc-100 text-zinc-400"}`}>{done ? <Check size={13}/> : index + 1}</span><span className={`text-xs ${active ? "font-bold text-[#806800]" : "text-zinc-600"}`}>{step}</span>{active && <span className="ml-auto size-2 animate-pulse rounded-full bg-amber-400"/>}</div>})}</div>
          {voiceResult?.recommendations.length ? <div className="mt-6 border-t border-zinc-100 pt-4"><p className="text-[10px] font-black uppercase tracking-wider text-zinc-400">Mission results</p><div className="mt-3 space-y-3">{voiceResult.recommendations.slice(0, 3).map((item, index) => { const price = typeof item.attributes.price === "number" ? item.attributes.price : null; const url = typeof item.attributes.url === "string" ? item.attributes.url : null; return <article key={item.id} className="rounded-xl bg-[#fff9d9] p-3"><div className="flex justify-between"><p className="text-xs font-bold">#{index + 1} {item.title}</p>{price !== null && <span className="text-xs font-black">${price.toFixed(2)}</span>}</div><p className="mt-1 text-[10px] text-zinc-500">{Math.round(item.score * 100)}% match · Bright Data → Buywise</p>{url && <a href={url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[10px] font-bold text-[#315fae]">View offer <ExternalLink size={10}/></a>}</article>})}</div></div> : <p className="mt-6 border-t border-zinc-100 pt-4 text-xs leading-5 text-zinc-400">Results will appear here without leaving the voice mission.</p>}
        </aside>
      </div>
      <footer className="flex justify-center gap-4 p-7"><button onClick={() => void toggleMute()} className={`grid size-14 place-items-center rounded-full shadow-sm ${muted ? "bg-red-100 text-red-600" : "border border-zinc-200 bg-white text-zinc-800"}`} aria-label={muted ? "Unmute microphone" : "Mute microphone"}>{muted ? <MicOff size={22}/> : <Mic size={22}/>}</button><button onClick={() => void toggleVoice()} className="grid size-14 place-items-center rounded-full bg-black text-white shadow-lg hover:bg-zinc-800" aria-label="End voice mission"><X size={22}/></button></footer>
    </div>}
  </>;
}

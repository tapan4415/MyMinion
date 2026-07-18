"use client";

import { AudioLines, MicOff, Sparkles, X } from "lucide-react";
import { Participant, Room, RoomEvent, Track, TranscriptionSegment } from "livekit-client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { AgentResponse } from "../../shared/types/contracts";

type TokenResponse = { server_url: string; participant_token: string };

type TranscriptLine = { id: string; role: "user" | "agent"; text: string; final: boolean };

export function VoiceButton({ onResult }: { onResult?: (result: AgentResponse) => void }) {
  const roomRef = useRef<Room | null>(null);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [speaker, setSpeaker] = useState<"user" | "agent" | "idle">("idle");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [progress, setProgress] = useState("");

  useEffect(() => () => { void roomRef.current?.disconnect(); }, []);

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
        setTranscript(current => {
          const next = [...current];
          for (const segment of segments) {
            const line = { id: segment.id, role, text: segment.text, final: segment.final };
            const index = next.findIndex(item => item.id === segment.id);
            if (index >= 0) next[index] = line; else next.push(line);
          }
          return next.slice(-12);
        });
      });
      room.on(RoomEvent.DataReceived, (payload, _participant, _kind, topic) => {
        try {
          const data = JSON.parse(new TextDecoder().decode(payload)) as AgentResponse & { stage?: string };
          if (topic === "myminion.progress") setProgress(data.stage ?? "Working on it");
          if (topic === "myminion.agent_result") {
            setProgress("Results ready");
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
      roomRef.current = room;
      setConnected(true);
    } finally {
      setBusy(false);
    }
  }

  return <>
    <Button type="button" size="icon" disabled={busy}
      aria-label={connected ? "Stop voice" : "Start voice"}
      onClick={() => void toggleVoice()} className="size-11 shrink-0 rounded-full bg-black text-white hover:bg-zinc-800">
      {connected ? <MicOff size={19} /> : <AudioLines size={21} />}
    </Button>
    {connected && <div className="fixed inset-0 z-50 flex flex-col bg-[#fbfbfc] text-zinc-900">
      <header className="flex h-20 items-center justify-between px-6"><div className="flex items-center gap-2 text-sm font-semibold"><Sparkles size={17} className="text-indigo-500"/> MyMinion</div><button onClick={() => void toggleVoice()} className="grid size-10 place-items-center rounded-full border border-zinc-200 bg-white text-zinc-700 shadow-sm hover:bg-zinc-50"><X size={18}/></button></header>
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-6 pb-4">
        <div className={`minion-orb relative size-48 overflow-hidden rounded-full transition-all duration-500 sm:size-56 ${speaker === "agent" ? "opacity-100" : speaker === "user" ? "opacity-90" : "opacity-75"}`}>
          <span className="sr-only">{speaker === "agent" ? "MyMinion is speaking" : speaker === "user" ? "Listening to you" : "Listening"}</span>
        </div>
        <p className="mt-8 text-[15px] font-medium text-zinc-600">{speaker === "agent" ? "MyMinion is speaking" : speaker === "user" ? "Listening to you" : "Listening…"}</p>
        {progress && <p className="mt-3 rounded-full bg-indigo-50 px-4 py-2 text-xs text-indigo-600">{progress}</p>}
        <div className="mt-8 max-h-[28vh] w-full max-w-2xl space-y-3 overflow-y-auto px-4 text-center">
          {transcript.length === 0 ? <p className="text-sm text-zinc-400">Start speaking. Your live transcript will appear here.</p> : transcript.slice(-5).map(line => <div key={line.id}><p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">{line.role === "user" ? "You" : "MyMinion"}</p><p className={`mt-1 text-[15px] leading-6 ${line.final ? "text-zinc-700" : "text-zinc-400"}`}>{line.text}</p></div>)}
        </div>
      </div>
      <footer className="flex justify-center p-7"><button onClick={() => void toggleVoice()} className="grid size-14 place-items-center rounded-full bg-black text-white shadow-lg hover:bg-zinc-800"><X size={22}/></button></footer>
    </div>}
  </>;
}

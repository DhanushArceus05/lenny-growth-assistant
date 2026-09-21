"use client";

import { useCallback, useRef, useState } from "react";
import { streamChat } from "@/lib/api";
import type { ArtifactData, ChatMode, ProviderName, SourceCitation } from "@/lib/types";

interface StreamState {
  isStreaming: boolean;
  statusLine: string | null;
  streamingText: string;
  sources: SourceCitation[];
  artifacts: ArtifactData[];
  error: string | null;
}

const initialState: StreamState = {
  isStreaming: false,
  statusLine: null,
  streamingText: "",
  sources: [],
  artifacts: [],
  error: null,
};

/** Reads the backend's `text/event-stream` chat response and exposes incremental
 * state. Deliberately hand-rolled (no SSE library) — the wire format is simple
 * `data: {...}\n\n` frames and a real EventSource can't POST a body, so a manual
 * fetch + ReadableStream reader is the simplest reliable option here. */
export function useChatStream(onComplete: (finalText: string, sources: SourceCitation[], artifacts: ArtifactData[], grounded: boolean) => void) {
  const [state, setState] = useState<StreamState>(initialState);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (args: { sessionId: string; message: string; mode: ChatMode; provider: ProviderName | null }) => {
      setState({ ...initialState, isStreaming: true });
      const controller = new AbortController();
      abortRef.current = controller;

      let accumulatedText = "";
      let accumulatedSources: SourceCitation[] = [];
      let accumulatedArtifacts: ArtifactData[] = [];

      try {
        const res = await streamChat(args);
        if (!res.ok || !res.body) {
          throw new Error(`Chat request failed (${res.status})`);
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";

          for (const frame of frames) {
            const line = frame.trim();
            if (!line.startsWith("data:")) continue;
            const jsonStr = line.slice("data:".length).trim();
            if (!jsonStr) continue;
            const event = JSON.parse(jsonStr);

            if (event.type === "status") {
              setState((s) => ({ ...s, statusLine: event.content }));
            } else if (event.type === "sources") {
              accumulatedSources = event.sources;
              setState((s) => ({ ...s, sources: accumulatedSources, statusLine: null }));
            } else if (event.type === "token") {
              accumulatedText += event.content;
              setState((s) => ({ ...s, streamingText: accumulatedText, statusLine: null }));
            } else if (event.type === "artifact") {
              accumulatedArtifacts = [
                ...accumulatedArtifacts,
                { artifact_type: event.artifact_type, title: event.title, content: event.content },
              ];
              setState((s) => ({ ...s, artifacts: accumulatedArtifacts }));
            } else if (event.type === "error") {
              setState((s) => ({ ...s, error: event.message, isStreaming: false }));
              return;
            } else if (event.type === "done") {
              setState((s) => ({ ...s, isStreaming: false }));
              onComplete(accumulatedText, accumulatedSources, accumulatedArtifacts, event.grounded);
              return;
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setState((s) => ({ ...s, error: (err as Error).message, isStreaming: false }));
      }
    },
    [onComplete]
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setState((s) => ({ ...s, isStreaming: false }));
  }, []);

  return { ...state, send, stop };
}

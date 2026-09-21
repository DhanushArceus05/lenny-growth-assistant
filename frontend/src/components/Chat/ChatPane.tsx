"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Square } from "lucide-react";
import { getSession } from "@/lib/api";
import { useChatStream } from "@/hooks/useChatStream";
import type { ArtifactData, ChatMode, Message, ProviderName, ProviderStatus } from "@/lib/types";
import { MessageItem } from "./MessageItem";
import { ModelSelector } from "./ModelSelector";

interface ChatPaneProps {
  sessionId: string | null;
  providers: ProviderStatus[];
  onOpenArtifact: (artifact: ArtifactData) => void;
  onSessionTouched: () => void;
}

const SUGGESTIONS = [
  "How should I structure onboarding for a PLG product?",
  "What have guests said about pricing experiments?",
  "Explain the difference between growth loops and funnels.",
];

export function ChatPane({ sessionId, providers, onOpenArtifact, onSessionTouched }: ChatPaneProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<ChatMode>("default");
  const [provider, setProvider] = useState<ProviderName>("ollama");
  const [loadError, setLoadError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    setLoadError(null);
    getSession(sessionId)
      .then((detail) => setMessages(detail.messages))
      .catch((err) => setLoadError(err.message));
  }, [sessionId]);

  const { isStreaming, statusLine, streamingText, sources, artifacts, error, send, stop } = useChatStream(
    (finalText, finalSources, finalArtifacts, grounded) => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: finalText,
          sources: grounded ? finalSources : [],
          provider,
          created_at: new Date().toISOString(),
          artifacts: finalArtifacts,
        },
      ]);
      if (finalArtifacts[0]) onOpenArtifact(finalArtifacts[0]);
      onSessionTouched();
    }
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  const handleSend = () => {
    if (!input.trim() || !sessionId || isStreaming) return;
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input,
      sources: [],
      provider: null,
      created_at: new Date().toISOString(),
      artifacts: [],
    };
    setMessages((prev) => [...prev, userMessage]);
    send({ sessionId, message: input, mode, provider });
    setInput("");
  };

  if (!sessionId) {
    return (
      <div className="flex h-full items-center justify-center text-slate">
        <p className="text-sm">Start a new conversation to begin.</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-8" aria-live="polite">
        {messages.length === 0 && !isStreaming && (
          <div className="mx-auto max-w-lg pt-16 text-center">
            <p className="font-display text-2xl text-parchment">Ask the archive something.</p>
            <p className="mt-2 text-sm text-slate">Grounded in Lenny&apos;s Podcast transcripts. Try:</p>
            <div className="mt-4 flex flex-col gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setInput(s)}
                  className="rounded-lg border border-slate-soft px-3 py-2 text-left text-sm text-parchment/80 hover:border-amber/50 hover:text-parchment focus:outline-none focus:ring-2 focus:ring-amber"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {loadError && (
          <div className="mb-4 rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
            Couldn&apos;t load this conversation: {loadError}
          </div>
        )}

        <div className="mx-auto flex max-w-3xl flex-col gap-5">
          {messages.map((m) => (
            <MessageItem key={m.id} message={m} onOpenArtifact={onOpenArtifact} />
          ))}

          {isStreaming && (
            <div className="flex justify-start">
              <div className="w-full max-w-[75ch]">
                <div className="mb-1 text-xs capitalize text-slate">{provider}</div>
                <div className="rounded-2xl rounded-tl-sm border border-slate-soft px-4 py-3 text-parchment">
                  {statusLine && !streamingText ? (
                    <span className="text-sm text-slate">{statusLine}</span>
                  ) : (
                    <span className="whitespace-pre-wrap text-sm leading-relaxed">
                      {streamingText}
                      <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-amber align-middle" />
                    </span>
                  )}
                </div>
                {sources.length > 0 && <div className="mx-1"><SourcesPreview count={sources.length} /></div>}
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
              {error}
              {error.toLowerCase().includes("ollama") && (
                <button
                  onClick={() => setProvider("anthropic")}
                  className="ml-2 underline decoration-red-400 underline-offset-2 hover:text-red-200"
                >
                  Switch to Claude
                </button>
              )}
            </div>
          )}
        </div>
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-soft px-4 py-3 sm:px-8">
        <div className="mx-auto max-w-3xl">
          <div className="mb-2">
            <ModelSelector
              providers={providers}
              selectedProvider={provider}
              onProviderChange={setProvider}
              mode={mode}
              onModeChange={setMode}
            />
          </div>
          <div className="flex items-end gap-2 rounded-xl border border-slate-soft bg-ink-raised p-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder={mode === "ship30" ? "What should the Ship 30 essay be about?" : "Ask a product or growth question…"}
              rows={1}
              className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-parchment placeholder:text-slate focus:outline-none"
            />
            {isStreaming ? (
              <button
                onClick={stop}
                aria-label="Stop generating"
                className="shrink-0 rounded-lg bg-slate-soft p-2 text-parchment hover:bg-slate/40 focus:outline-none focus:ring-2 focus:ring-amber"
              >
                <Square size={16} />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                aria-label="Send message"
                className="shrink-0 rounded-lg bg-amber p-2 text-ink disabled:opacity-30 focus:outline-none focus:ring-2 focus:ring-amber"
              >
                <Send size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SourcesPreview({ count }: { count: number }) {
  return <p className="mt-1 text-xs text-slate">Found {count} relevant excerpt{count === 1 ? "" : "s"}…</p>;
}

"use client";

import type { ArtifactData, Message } from "@/lib/types";
import { MarkdownRenderer } from "@/components/Artifact/MarkdownRenderer";
import { SourceCitations } from "./SourceCitations";

interface MessageItemProps {
  message: Message;
  onOpenArtifact: (artifact: ArtifactData) => void;
}

export function MessageItem({ message, onOpenArtifact }: MessageItemProps) {
  const isUser = message.role === "user";
  const isRefusal = !isUser && message.sources.length === 0 && message.artifacts.length === 0;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[75ch] ${isUser ? "" : "w-full"}`}>
        {!isUser && (
          <div className="mb-1 flex items-center gap-2 text-xs text-slate">
            <span className="font-medium capitalize">{message.provider ?? "assistant"}</span>
            {isRefusal && (
              <span className="rounded-full border border-slate-soft px-2 py-0.5 text-[10px] uppercase tracking-wide">
                No archive match
              </span>
            )}
          </div>
        )}
        <div
          className={
            isUser
              ? "rounded-2xl rounded-tr-sm bg-amber-soft px-4 py-2.5 text-parchment"
              : "rounded-2xl rounded-tl-sm border border-slate-soft px-4 py-3 text-parchment"
          }
        >
          <MarkdownRenderer content={message.content} />
        </div>

        {message.artifacts.map((artifact, i) => (
          <button
            key={i}
            onClick={() => onOpenArtifact(artifact)}
            className="mt-2 flex items-center gap-2 rounded-md border border-amber/30 bg-amber-soft px-3 py-2 text-left text-xs text-amber hover:border-amber/60 focus:outline-none focus:ring-2 focus:ring-amber"
          >
            📄 <span className="truncate">{artifact.title}</span>
            <span className="ml-auto shrink-0 uppercase tracking-wide opacity-70">{artifact.artifact_type}</span>
          </button>
        ))}

        {!isUser && <SourceCitations sources={message.sources} />}
      </div>
    </div>
  );
}

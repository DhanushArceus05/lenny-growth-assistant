"use client";

import { FileText, X } from "lucide-react";
import type { ArtifactData } from "@/lib/types";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { SandboxedIframe } from "./SandboxedIframe";

interface ArtifactViewerProps {
  artifact: ArtifactData | null;
  onClose: () => void;
}

export function ArtifactViewer({ artifact, onClose }: ArtifactViewerProps) {
  if (!artifact) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center text-slate">
        <FileText size={28} strokeWidth={1.5} />
        <p className="max-w-[24ch] text-sm">
          Generated documents and rendered snippets will open here, beside the conversation.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-slate-soft px-4 py-3">
        <div className="min-w-0">
          <p className="truncate font-display text-base text-parchment">{artifact.title}</p>
          <p className="text-xs uppercase tracking-wide text-slate">{artifact.artifact_type}</p>
        </div>
        <button
          onClick={onClose}
          aria-label="Collapse artifact pane"
          className="rounded p-1.5 text-slate hover:bg-ink-raised hover:text-parchment focus:outline-none focus:ring-2 focus:ring-amber"
        >
          <X size={18} />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {artifact.artifact_type === "html" ? (
          <div className="h-full min-h-[400px]">
            <SandboxedIframe content={artifact.content} title={artifact.title} />
          </div>
        ) : (
          <MarkdownRenderer content={artifact.content} />
        )}
      </div>
    </div>
  );
}

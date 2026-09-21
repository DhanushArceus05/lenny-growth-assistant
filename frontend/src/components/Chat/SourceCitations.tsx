"use client";

import { useState } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import type { SourceCitation } from "@/lib/types";

export function SourceCitations({ sources }: { sources: SourceCitation[] }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  if (sources.length === 0) return null;

  return (
    <div className="mt-3 flex flex-col gap-1.5">
      {sources.map((s, i) => (
        <div key={i} className="rounded-md border border-slate-soft bg-ink-raised">
          <button
            onClick={() => setOpenIndex(openIndex === i ? null : i)}
            className="flex w-full items-center gap-2 px-3 py-2 text-left focus:outline-none focus:ring-2 focus:ring-amber"
            aria-expanded={openIndex === i}
          >
            <span className="h-1.5 w-8 shrink-0 overflow-hidden rounded-full bg-slate-soft">
              <span className="block h-full bg-amber" style={{ width: `${Math.round(s.score * 100)}%` }} />
            </span>
            <span className="min-w-0 flex-1 truncate text-xs text-parchment/90">
              {s.episode}
              {s.guest ? ` · ${s.guest}` : ""}
              {s.timestamp ? ` · ${s.timestamp}` : ""}
            </span>
            <ChevronDown
              size={14}
              className={`shrink-0 text-slate transition-transform ${openIndex === i ? "rotate-180" : ""}`}
            />
          </button>
          {openIndex === i && (
            <div className="border-t border-slate-soft px-3 py-2">
              <p className="text-xs leading-relaxed text-slate">&ldquo;{s.excerpt}&rdquo;</p>
              {s.source_url && (
                <a
                  href={s.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1.5 inline-flex items-center gap-1 text-xs text-amber hover:underline focus:outline-none focus:ring-2 focus:ring-amber"
                >
                  Open source <ExternalLink size={11} />
                </a>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

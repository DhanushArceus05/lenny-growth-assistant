"use client";

import { Menu, Plus, X } from "lucide-react";
import type { SessionSummary } from "@/lib/types";

interface SessionSidebarProps {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNewSession: () => void;
  isOpen: boolean;
  onToggle: () => void;
}

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function SessionSidebar({ sessions, activeSessionId, onSelect, onNewSession, isOpen, onToggle }: SessionSidebarProps) {
  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={onToggle}
        aria-label={isOpen ? "Close sessions" : "Open sessions"}
        className="fixed left-3 top-3 z-30 rounded-md border border-slate-soft bg-ink-raised p-2 text-parchment md:hidden"
      >
        {isOpen ? <X size={18} /> : <Menu size={18} />}
      </button>

      {/* Mobile overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-20 bg-black/50 md:hidden" onClick={onToggle} aria-hidden="true" />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-20 flex w-64 shrink-0 flex-col border-r border-slate-soft bg-ink-raised transition-transform md:static md:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-soft px-4 py-4">
          <span className="font-display text-lg text-parchment">Lenny Assistant</span>
        </div>
        <div className="p-3">
          <button
            onClick={onNewSession}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-amber/40 px-3 py-2 text-sm text-amber hover:bg-amber-soft focus:outline-none focus:ring-2 focus:ring-amber"
          >
            <Plus size={15} /> New conversation
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 pb-4" aria-label="Past conversations">
          {sessions.length === 0 && (
            <p className="px-2 py-4 text-center text-xs text-slate">No conversations yet.</p>
          )}
          <ul className="flex flex-col gap-0.5">
            {sessions.map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => onSelect(s.id)}
                  aria-current={activeSessionId === s.id}
                  className={`w-full truncate rounded-md px-3 py-2 text-left text-sm focus:outline-none focus:ring-2 focus:ring-amber ${
                    activeSessionId === s.id
                      ? "bg-amber-soft text-parchment"
                      : "text-parchment/70 hover:bg-ink hover:text-parchment"
                  }`}
                >
                  <span className="block truncate">{s.title}</span>
                  <span className="block text-[11px] text-slate">{relativeTime(s.updated_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
    </>
  );
}

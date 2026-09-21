"use client";

import { useCallback, useEffect, useState } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { createSession, getHealth, listSessions } from "@/lib/api";
import type { ArtifactData, ProviderStatus, SessionSummary } from "@/lib/types";
import { SessionSidebar } from "@/components/SessionSidebar";
import { ChatPane } from "@/components/Chat/ChatPane";
import { ArtifactViewer } from "@/components/Artifact/ArtifactViewer";

export default function Home() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [artifact, setArtifact] = useState<ArtifactData | null>(null);
  const [artifactPaneOpen, setArtifactPaneOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const refreshSessions = useCallback(async () => {
    try {
      const list = await listSessions();
      setSessions(list);
      return list;
    } catch {
      return [];
    }
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      const h = await getHealth();
      setProviders(h.providers);
      setHealthError(h.database ? null : "Backend reports the database is unreachable.");
    } catch {
      setHealthError("Can't reach the backend API. Is it running?");
    }
  }, []);

  useEffect(() => {
    (async () => {
      const list = await refreshSessions();
      if (list.length > 0) setActiveSessionId(list[0].id);
    })();
    refreshHealth();
    const interval = setInterval(refreshHealth, 15000);
    return () => clearInterval(interval);
  }, [refreshSessions, refreshHealth]);

  const handleNewSession = useCallback(async () => {
    try {
      const session = await createSession();
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setArtifact(null);
      setArtifactPaneOpen(false);
      setSidebarOpen(false);
    } catch {
      setHealthError("Couldn't create a new conversation. Is the backend running?");
    }
  }, []);

  const handleOpenArtifact = useCallback((a: ArtifactData) => {
    setArtifact(a);
    setArtifactPaneOpen(true);
  }, []);

  return (
    <main className="flex h-screen overflow-hidden bg-ink">
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={(id) => {
          setActiveSessionId(id);
          setArtifact(null);
          setArtifactPaneOpen(false);
          setSidebarOpen(false);
        }}
        onNewSession={handleNewSession}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((o) => !o)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-soft px-4 py-2.5 pl-16 md:pl-4">
          <div className="flex items-center gap-2 text-xs text-slate">
            {healthError ? (
              <span className="flex items-center gap-1.5 text-red-300">
                <span className="h-1.5 w-1.5 rounded-full bg-red-400" /> {healthError}
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Connected
              </span>
            )}
          </div>
          <button
            onClick={() => setArtifactPaneOpen((o) => !o)}
            aria-label={artifactPaneOpen ? "Collapse artifact pane" : "Open artifact pane"}
            className="rounded-md p-1.5 text-slate hover:bg-ink-raised hover:text-parchment focus:outline-none focus:ring-2 focus:ring-amber"
          >
            {artifactPaneOpen ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
          </button>
        </header>

        <div className="flex min-h-0 flex-1">
          <div className={`min-w-0 flex-1 ${artifactPaneOpen ? "hidden md:block" : "block"}`}>
            <ChatPane
              sessionId={activeSessionId}
              providers={providers}
              onOpenArtifact={handleOpenArtifact}
              onSessionTouched={refreshSessions}
            />
          </div>

          {artifactPaneOpen && (
            <div className="fixed inset-0 z-30 flex flex-col bg-ink md:static md:z-auto md:w-[45%] md:max-w-xl md:border-l md:border-slate-soft">
              <button
                onClick={() => setArtifactPaneOpen(false)}
                className="self-end p-3 text-slate hover:text-parchment md:hidden"
                aria-label="Close artifact view"
              >
                <PanelRightClose size={18} />
              </button>
              <div className="min-h-0 flex-1">
                <ArtifactViewer artifact={artifact} onClose={() => setArtifactPaneOpen(false)} />
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

import type { ChatMode, HealthStatus, ProviderName, SessionDetail, SessionSummary } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function handleJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.error?.message || detail;
    } catch {
      // response wasn't JSON — fall back to statusText
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function createSession(title?: string): Promise<SessionSummary> {
  const res = await fetch(`${API_URL}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title ?? null }),
  });
  return handleJson<SessionSummary>(res);
}

export async function listSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${API_URL}/api/sessions`);
  return handleJson<SessionSummary[]>(res);
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`${API_URL}/api/sessions/${sessionId}`);
  return handleJson<SessionDetail>(res);
}

export async function getHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_URL}/api/health`);
  return handleJson<HealthStatus>(res);
}

export interface StreamChatArgs {
  sessionId: string;
  message: string;
  mode: ChatMode;
  provider: ProviderName | null;
}

/** Opens the chat SSE stream. Returns the raw Response so the caller (useChatStream)
 * owns the reading loop — kept here only to centralize the URL/fetch-options. */
export async function streamChat({ sessionId, message, mode, provider }: StreamChatArgs): Promise<Response> {
  return fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message, mode, provider }),
  });
}

export { API_URL };

export type Role = "user" | "assistant" | "system";
export type ArtifactType = "markdown" | "html";
export type ProviderName = "ollama" | "anthropic";

export interface SourceCitation {
  episode: string;
  guest: string | null;
  timestamp: string | null;
  score: number;
  excerpt: string;
  source_url: string | null;
}

export interface ArtifactData {
  id?: string;
  artifact_type: ArtifactType;
  title: string;
  content: string;
  created_at?: string;
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  sources: SourceCitation[];
  provider: ProviderName | null;
  created_at: string;
  artifacts: ArtifactData[];
}

export interface SessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail extends SessionSummary {
  messages: Message[];
}

export interface ProviderStatus {
  name: ProviderName;
  available: boolean;
  reason: string | null;
}

export interface HealthStatus {
  status: "ok" | "degraded";
  database: boolean;
  ollama_reachable: boolean;
  vector_index_populated: boolean;
  providers: ProviderStatus[];
}

export type ChatMode = "default" | "ship30";

/** Discriminated union mirroring the backend's SSE event `type` field. */
export type ChatStreamEvent =
  | { type: "status"; content: string }
  | { type: "sources"; sources: SourceCitation[] }
  | { type: "token"; content: string }
  | { type: "artifact"; artifact_type: ArtifactType; title: string; content: string }
  | { type: "done"; grounded: boolean; message_id: string }
  | { type: "error"; code: string; message: string };

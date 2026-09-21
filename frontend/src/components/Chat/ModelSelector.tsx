"use client";

import type { ChatMode, ProviderName, ProviderStatus } from "@/lib/types";

interface ModelSelectorProps {
  providers: ProviderStatus[];
  selectedProvider: ProviderName;
  onProviderChange: (p: ProviderName) => void;
  mode: ChatMode;
  onModeChange: (m: ChatMode) => void;
}

export function ModelSelector({ providers, selectedProvider, onProviderChange, mode, onModeChange }: ModelSelectorProps) {
  const providerStatus = (name: ProviderName) => providers.find((p) => p.name === name);

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <div className="flex items-center gap-1 rounded-full border border-slate-soft bg-ink-raised p-0.5">
        {(["ollama", "anthropic"] as ProviderName[]).map((name) => {
          const status = providerStatus(name);
          const disabled = status ? !status.available : false;
          const active = selectedProvider === name;
          return (
            <button
              key={name}
              disabled={disabled}
              title={disabled ? status?.reason ?? "unavailable" : undefined}
              onClick={() => onProviderChange(name)}
              className={`rounded-full px-3 py-1 capitalize transition-colors focus:outline-none focus:ring-2 focus:ring-amber ${
                active ? "bg-amber text-ink font-medium" : "text-parchment/70 hover:text-parchment"
              } ${disabled ? "cursor-not-allowed opacity-40" : ""}`}
            >
              {name === "ollama" ? "Ollama (local)" : "Claude (cloud)"}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-1 rounded-full border border-slate-soft bg-ink-raised p-0.5">
        {(["default", "ship30"] as ChatMode[]).map((m) => (
          <button
            key={m}
            onClick={() => onModeChange(m)}
            className={`rounded-full px-3 py-1 transition-colors focus:outline-none focus:ring-2 focus:ring-amber ${
              mode === m ? "bg-amber text-ink font-medium" : "text-parchment/70 hover:text-parchment"
            }`}
          >
            {m === "default" ? "Ask" : "Ship 30 for 30"}
          </button>
        ))}
      </div>
    </div>
  );
}

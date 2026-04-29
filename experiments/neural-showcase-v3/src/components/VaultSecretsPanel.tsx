/**
 * Read-only vault status: env vs Keychain vs missing per key. No secret values.
 * Offers a copyable ``security add-generic-password`` line for macOS.
 */

import { useState } from "react";
import { Check, Copy, KeyRound, Loader2, RefreshCw } from "lucide-react";

import { CornerFrame } from "@/components/Glyphs";
import {
  macOSKeychainAddCommand,
  useVaultStatus,
  type VaultKey,
} from "@/lib/vault";

function sourceBadge(k: VaultKey): { label: string; className: string } {
  if (k.source === "env") {
    return {
      label: "env",
      className:
        "border-accent/40 bg-accent/[0.06] text-accent",
    };
  }
  if (k.source === "keychain") {
    return {
      label: "keychain",
      className:
        "border-line bg-[rgba(34,197,94,0.08)] text-[var(--color-success)]",
    };
  }
  return {
    label: "missing",
    className:
      "border-alert/35 bg-alert/[0.06] text-alert",
  };
}

export function VaultSecretsPanel() {
  const { status, loading, error, refresh } = useVaultStatus(20000);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copyCmd = async (keyName: string) => {
    const cmd = macOSKeychainAddCommand(keyName);
    try {
      await navigator.clipboard.writeText(cmd);
      setCopiedKey(keyName);
      setTimeout(() => setCopiedKey(null), 2200);
    } catch {
      /* clipboard denied */
    }
  };

  return (
    <div
      id="vault-keys"
      className="relative rounded-[14px] border border-line bg-bg-1 p-5"
      aria-labelledby="vault-secrets-heading"
    >
      <CornerFrame />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-ink-2" aria-hidden />
          <span
            id="vault-secrets-heading"
            className="font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2"
          >
            api keys · vault
          </span>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md border border-line px-2 py-1 font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink disabled:opacity-50"
          title="Refresh vault status"
        >
          <RefreshCw
            size={12}
            strokeWidth={1.6}
            className={loading ? "animate-spin" : ""}
          />
          refresh
        </button>
      </div>

      <p className="mb-4 max-w-[58ch] text-[12.5px] leading-[1.6] text-ink-2">
        Resolution order is env, then macOS Keychain (<span className="font-mono-tech text-[11px] text-ink">security find-generic-password -a tars -s KEY</span>).
        Values are never shown here.
      </p>

      {error && (
        <div
          role="status"
          aria-live="polite"
          className="mb-3 rounded-md border border-alert/35 bg-alert/[0.04] px-3 py-2 font-mono-tech text-[11px] text-alert"
        >
          {error}
        </div>
      )}

      {loading && !status?.keys?.length ? (
        <div className="flex items-center gap-2 font-mono-tech text-[11px] text-ink-3">
          <Loader2 size={14} className="animate-spin" strokeWidth={1.6} aria-hidden />
          loading vault status…
        </div>
      ) : (
        <ul className="grid max-h-[min(52vh,420px)] gap-1.5 overflow-auto pr-1">
          {(status?.keys ?? []).map((k) => {
            const b = sourceBadge(k);
            return (
              <li
                key={k.key}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-[rgba(0,0,0,0.25)] px-2.5 py-2"
              >
                <div className="min-w-0 flex-1">
                  <code className="block truncate font-mono-tech text-[11px] tracking-[0.6px] text-ink">
                    {k.key}
                  </code>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <span
                    className={`rounded border px-2 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.8px] ${b.className}`}
                  >
                    {b.label}
                  </span>
                  <button
                    type="button"
                    title="Copy macOS Keychain add command (Terminal will prompt for the secret)"
                    onClick={() => void copyCmd(k.key)}
                    className="inline-flex items-center gap-1 rounded border border-line px-2 py-1 font-mono-tech text-[9px] uppercase tracking-[1.6px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
                  >
                    {copiedKey === k.key ? (
                      <Check size={11} strokeWidth={2} className="text-[var(--color-success)]" />
                    ) : (
                      <Copy size={11} strokeWidth={1.8} />
                    )}
                    copy cmd
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-4 font-mono-tech text-[10px] leading-[1.55] tracking-[0.4px] text-ink-3">
        After pasting the command in Terminal, type the secret when prompted. Re-run refresh when done.
      </p>
    </div>
  );
}

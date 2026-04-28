/**
 * Client + hook for the TARS secrets vault.
 *
 * Read-only; values are NEVER returned by the server. The hook lets
 * the cockpit render per-pack auth badges (e.g. "anthropic: keychain"
 * vs "openai: missing").
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "./api";

export interface VaultKey {
  key: string;
  source: "env" | "keychain" | "missing";
  available: boolean;
}

export interface VaultStatus {
  ok: boolean;
  count: number;
  keys: VaultKey[];
}

export async function getVaultStatus(): Promise<VaultStatus> {
  const r = await fetch(`${API_BASE}/api/vault/status`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<VaultStatus>;
}

export function useVaultStatus(intervalMs = 30000): {
  status: VaultStatus | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [status, setStatus] = useState<VaultStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelled = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const out = await getVaultStatus();
      if (!cancelled.current) {
        setStatus(out);
        setError(null);
      }
    } catch (e) {
      if (!cancelled.current) setError((e as Error).message);
    } finally {
      if (!cancelled.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    cancelled.current = false;
    void refresh();
    if (intervalMs > 0) {
      const id = window.setInterval(refresh, intervalMs);
      return () => {
        cancelled.current = true;
        window.clearInterval(id);
      };
    }
    return () => {
      cancelled.current = true;
    };
  }, [refresh, intervalMs]);

  return { status, loading, error, refresh };
}

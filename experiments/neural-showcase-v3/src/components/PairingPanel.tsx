/**
 * Host-side device pairing UI (Phase L5 K4).
 *
 * Companion app calls `POST /api/pairing/begin` with its pubkey; operator
 * pastes `accept_token` here and taps Accept — or confirms fingerprint
 * out-of-band on the phone vs `host_fingerprint`.
 */

import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, Smartphone, Copy, Check } from "lucide-react";
import {
  acceptPairing,
  formatFingerprint,
  getIdentity,
  listDevices,
  revokeDevice,
  type IdentityStatus,
  type PairedDevice,
  PairingError,
} from "@/lib/pairing";
import { CornerFrame } from "@/components/Glyphs";
import { BrandHairline } from "@/components/BrandHairline";

export function PairingPanel() {
  const [identity, setIdentity] = useState<IdentityStatus | null>(null);
  const [devices, setDevices] = useState<PairedDevice[]>([]);
  const [busy, setBusy] = useState(false);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [copiedPk, setCopiedPk] = useState(false);

  const refreshAll = useCallback(async () => {
    setBusy(true);
    setLoadErr(null);
    try {
      const [id, devs] = await Promise.all([getIdentity(), listDevices()]);
      setIdentity(id);
      setDevices(devs.devices ?? []);
    } catch (e: unknown) {
      setIdentity(null);
      setDevices([]);
      setLoadErr((e as Error)?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  const onAcceptToken = async () => {
    const t = token.trim();
    if (!t) return;
    setBusy(true);
    setActionErr(null);
    setActionMsg(null);
    try {
      const r = await acceptPairing(t);
      setActionMsg(`Linked device ${r.device_id}`);
      setToken("");
      await refreshAll();
    } catch (e: unknown) {
      const msg =
        e instanceof PairingError ? e.message : (e as Error)?.message ?? String(e);
      setActionErr(msg);
    } finally {
      setBusy(false);
    }
  };

  const onRevoke = async (device_id: string) => {
    setBusy(true);
    setActionErr(null);
    setActionMsg(null);
    try {
      await revokeDevice(device_id);
      setActionMsg(`Revoked ${device_id}`);
      await refreshAll();
    } catch (e: unknown) {
      setActionErr((e as Error)?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  const copyPk = async () => {
    if (!identity?.host_public_key) return;
    try {
      await navigator.clipboard.writeText(identity.host_public_key);
      setCopiedPk(true);
      setTimeout(() => setCopiedPk(false), 2000);
    } catch {
      setActionErr("Clipboard unavailable");
    }
  };

  const fp = identity?.host_fingerprint
    ? formatFingerprint(identity.host_fingerprint)
    : "…";

  return (
    <div className="relative overflow-hidden rounded-[14px] border border-line bg-bg-1 p-5">
      <BrandHairline />
      <CornerFrame />

      <div className="mb-4 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Smartphone className="h-4 w-4 text-ink-2" aria-hidden />
          <span className="font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
            device pairing
          </span>
        </div>
        <button
          type="button"
          onClick={() => void refreshAll()}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md border border-line px-2 py-1 font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink disabled:opacity-50"
          title="Refresh identity + devices"
        >
          <RefreshCw className={`h-3 w-3 ${busy ? "animate-spin" : ""}`} />
          sync
        </button>
      </div>

      {loadErr && (
        <p className="mb-4 font-mono-tech text-[11px] uppercase tracking-[1px] text-alert">{loadErr}</p>
      )}

      {!loadErr && identity && (
        <>
          <div className="mb-4 rounded-md border border-line bg-bg-0 px-3 py-2.5 font-mono-tech text-[12px] text-ink">
            <span className="block text-[9px] uppercase tracking-[2.2px] text-ink-3">host fingerprint</span>
            <span className="font-display text-[22px] font-medium tracking-[0.12em] text-ink">
              {fp}
            </span>
            <p className="mt-2 max-w-[60ch] text-[11px] leading-[1.45] uppercase tracking-[0.12em] text-ink-2">
              Confirm this matches your phone before approving the link.
            </p>
          </div>

          <div className="mb-5 flex flex-wrap items-center gap-2">
            <span className="truncate font-mono-tech text-[10px] uppercase tracking-[1px] text-ink-3">
              pubkey
            </span>
            <code className="max-w-full truncate rounded bg-bg-0 px-2 py-1 text-[10px] text-ink">
              {identity.host_public_key}
            </code>
            <button
              type="button"
              onClick={() => void copyPk()}
              className="inline-flex items-center gap-1 rounded border border-line px-2 py-1 font-mono-tech text-[9px] uppercase text-ink-2 hover:text-ink"
            >
              {copiedPk ? <Check size={11} /> : <Copy size={11} />} copy
            </button>
          </div>

          <div className="border-t border-line pt-4">
            <label className="block">
              <span className="mb-2 block font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3">
                accept_token (paste from companion)
              </span>
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                className="w-full rounded-md border border-line bg-bg-0 px-3 py-2 font-mono-tech text-[12px] uppercase tracking-[0.06em] text-ink placeholder:text-ink-3 focus:border-line-strong focus:outline-none"
                placeholder="9f20ef353462ea44…"
                autoComplete="off"
                spellCheck={false}
              />
            </label>
            <button
              type="button"
              disabled={busy || !token.trim()}
              onClick={() => void onAcceptToken()}
              className="mt-3 rounded-md border border-line-hot px-4 py-2 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink transition-opacity hover:bg-accent-deep hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Accept link
            </button>
          </div>

          {devices.length > 0 && (
            <ul className="mt-6 space-y-2 border-t border-line pt-4">
              <li className="font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3">
                paired devices · {devices.length}
              </li>
              {devices.map((d) => (
                <li
                  key={d.device_id}
                  className="flex flex-col gap-2 rounded-md border border-line bg-bg-0 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <div className="truncate font-mono-tech text-[11px] uppercase text-ink">
                      {d.device_id}
                    </div>
                    <div className="text-[10px] uppercase tracking-[1px] text-ink-3">
                      {d.kind}
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void onRevoke(d.device_id)}
                    className="shrink-0 self-start rounded border border-alert/40 px-2 py-1 font-mono-tech text-[9px] uppercase tracking-[1.5px] text-alert hover:bg-alert/10 sm:self-center disabled:opacity-50"
                  >
                    revoke
                  </button>
                </li>
              ))}
            </ul>
          )}

          {actionMsg && (
            <p className="mt-4 font-mono-tech text-[11px] text-success" aria-live="polite">
              {actionMsg}
            </p>
          )}
          {actionErr && (
            <p className="mt-4 font-mono-tech text-[11px] text-alert" aria-live="assertive">
              {actionErr}
            </p>
          )}
        </>
      )}

      {busy && !identity && (
        <div className="flex items-center gap-2 text-ink-3">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> loading pairing…
        </div>
      )}
    </div>
  );
}

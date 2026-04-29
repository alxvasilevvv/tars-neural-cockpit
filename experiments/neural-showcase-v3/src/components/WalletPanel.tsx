/**
 * Wallet management surface (Phase M2).
 *
 * Operator can:
 *   - Mint a new wallet (mnemonic shown EXACTLY ONCE).
 *   - Browse existing wallets (no secrets).
 *   - Build an unsigned send envelope for review.
 *   - Delete a wallet (soft confirmation in the UI; gated server-side).
 */

import { useState } from "react";
import {
  Check,
  Copy,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
  Wallet,
} from "lucide-react";

import { ChainSendForm } from "@/components/ChainSendForm";
import { CornerFrame } from "@/components/Glyphs";
import { MnemonicReveal } from "@/components/MnemonicReveal";
import {
  buildSend,
  chainBadgeClass,
  createWallet,
  deleteWallet,
  fetchBalance,
  shortenAddress,
  signMessage,
  useWallets,
  type BalanceResult,
  type Wallet as WalletRow,
  type WalletChain,
} from "@/lib/wallet";

const CHAINS: WalletChain[] = ["solana", "evm", "ton"];

export function WalletPanel() {
  const { wallets, loading, error, refresh } = useWallets();
  const [draftLabel, setDraftLabel] = useState("");
  const [draftChain, setDraftChain] = useState<WalletChain>("solana");
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [revealMnemonic, setRevealMnemonic] = useState<{
    walletId: string;
    mnemonic: string;
  } | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [sendOpen, setSendOpen] = useState<string | null>(null);
  const [sendTo, setSendTo] = useState("");
  const [sendAmount, setSendAmount] = useState("");
  const [sendEnvelope, setSendEnvelope] =
    useState<Record<string, unknown> | null>(null);
  const [balances, setBalances] = useState<Record<string, BalanceResult>>({});
  const [balanceLoading, setBalanceLoading] = useState<Record<string, boolean>>({});
  const [signatures, setSignatures] = useState<Record<string, string>>({});
  const [signingId, setSigningId] = useState<string | null>(null);

  const onProveOwnership = async (w: WalletRow) => {
    setSigningId(w.id);
    setActionErr(null);
    try {
      const proof = `meeet.world ownership proof — ${new Date().toISOString()}`;
      const r = await signMessage(w.id, proof);
      setSignatures((prev) => ({
        ...prev,
        [w.id]: r.signature_b64.slice(0, 20) + "…",
      }));
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSigningId(null);
    }
  };

  const loadBalance = async (id: string) => {
    setBalanceLoading((prev) => ({ ...prev, [id]: true }));
    try {
      const r = await fetchBalance(id);
      setBalances((prev) => ({ ...prev, [id]: r }));
    } catch (e) {
      setBalances((prev) => ({
        ...prev,
        [id]: { ok: false, error: (e as Error).message },
      }));
    } finally {
      setBalanceLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  const onCreate = async () => {
    if (!draftLabel.trim()) return;
    setBusy(true);
    setActionErr(null);
    try {
      const r = await createWallet(draftLabel.trim(), draftChain);
      setRevealMnemonic({ walletId: r.wallet.id, mnemonic: r.mnemonic ?? "" });
      setDraftLabel("");
      await refresh();
    } catch (e) {
      setActionErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async (id: string) => {
    if (!window.confirm("Delete this wallet? Make sure your seed is backed up.")) {
      return;
    }
    setBusy(true);
    try {
      await deleteWallet(id);
      await refresh();
    } catch (e) {
      setActionErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onCopy = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedKey(label);
      setTimeout(() => setCopiedKey(null), 2200);
    } catch {
      /* clipboard denied */
    }
  };

  const onBuildSend = async (id: string) => {
    if (!sendTo.trim() || !sendAmount.trim()) return;
    setBusy(true);
    try {
      const r = await buildSend(id, sendTo.trim(), sendAmount.trim());
      setSendEnvelope(r.envelope);
    } catch (e) {
      setActionErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      id="wallets"
      className="relative rounded-[14px] border border-line bg-bg-1 p-5"
      aria-labelledby="wallets-heading"
    >
      <CornerFrame />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Wallet className="h-4 w-4 text-ink-2" aria-hidden />
          <span
            id="wallets-heading"
            className="font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2"
          >
            wallets · self-custodial
          </span>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading || busy}
          className="inline-flex items-center gap-1.5 rounded-md border border-line px-2 py-1 font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink disabled:opacity-50"
          title="Refresh wallets"
        >
          <RefreshCw size={12} strokeWidth={1.6} className={loading ? "animate-spin" : ""} />
          refresh
        </button>
      </div>

      {error ? (
        <p className="mb-3 rounded border border-alert/40 bg-alert/[0.06] p-2 text-[12px] text-alert">
          {error}
        </p>
      ) : null}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void onCreate();
        }}
        className="mb-4 grid grid-cols-1 gap-2 rounded-md border border-line bg-bg-0 p-3 sm:grid-cols-[1fr_auto_auto]"
      >
        <input
          aria-label="wallet label"
          value={draftLabel}
          onChange={(e) => setDraftLabel(e.target.value)}
          placeholder="wallet label"
          className="rounded border border-line bg-bg-1 px-2 py-1 font-mono-tech text-[12px] text-ink placeholder:text-ink-2 focus:border-accent focus:outline-none"
        />
        <select
          aria-label="chain"
          value={draftChain}
          onChange={(e) => setDraftChain(e.target.value as WalletChain)}
          className="rounded border border-line bg-bg-1 px-2 py-1 font-mono-tech text-[12px] text-ink focus:border-accent focus:outline-none"
        >
          {CHAINS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={busy || !draftLabel.trim()}
          className="inline-flex items-center gap-1.5 rounded border border-accent/40 bg-accent/[0.06] px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-accent hover:bg-accent/10 disabled:opacity-50"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} strokeWidth={1.7} />}
          mint
        </button>
      </form>

      {revealMnemonic ? (
        <MnemonicReveal
          walletId={revealMnemonic.walletId}
          mnemonic={revealMnemonic.mnemonic}
          copiedKey={copiedKey}
          onCopy={onCopy}
          onDismiss={() => setRevealMnemonic(null)}
        />
      ) : null}

      {actionErr ? (
        <p className="mb-2 rounded border border-alert/40 bg-alert/[0.06] p-2 font-mono-tech text-[10.5px] text-alert">
          {actionErr}
        </p>
      ) : null}

      <ul className="space-y-2">
        {wallets.length === 0 ? (
          <li className="rounded border border-dashed border-line p-3 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">
            no wallets yet — mint one above
          </li>
        ) : (
          wallets.map((w: WalletRow) => (
            <li key={w.id} className="rounded border border-line bg-bg-0 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-col">
                  <span className="font-mono-tech text-[12.5px] text-ink">{w.label}</span>
                  <span className="font-mono-tech text-[10.5px] text-ink-2">
                    {shortenAddress(w.address)}
                  </span>
                </div>
                <span
                  className={`inline-flex items-center rounded-md px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] ring-1 ${chainBadgeClass(
                    w.chain,
                  )}`}
                >
                  {w.chain}
                </span>
              </div>
              {balances[w.id] ? (
                <p
                  className={`mt-1 font-mono-tech text-[11.5px] ${
                    balances[w.id].ok ? "text-emerald-300" : "text-alert"
                  }`}
                >
                  {balances[w.id].ok && balances[w.id].balance
                    ? `${balances[w.id].balance!.display} ${balances[w.id].balance!.symbol}`
                    : `balance unavailable: ${balances[w.id].error ?? "rpc"}`}
                </p>
              ) : null}
              <div className="mt-2 flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => void loadBalance(w.id)}
                  disabled={balanceLoading[w.id]}
                  className="inline-flex items-center gap-1 rounded border border-line px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink disabled:opacity-50"
                >
                  {balanceLoading[w.id] ? <Loader2 size={10} className="animate-spin" /> : null}
                  balance
                </button>
                <button
                  type="button"
                  onClick={() => void onCopy(`addr-${w.id}`, w.address)}
                  className="inline-flex items-center gap-1 rounded border border-line px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink"
                >
                  {copiedKey === `addr-${w.id}` ? <Check size={10} /> : <Copy size={10} />}
                  copy address
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSendOpen(sendOpen === w.id ? null : w.id);
                    setSendEnvelope(null);
                  }}
                  className="inline-flex items-center gap-1 rounded border border-line px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink"
                >
                  {sendOpen === w.id ? "close" : "send"}
                </button>
                {w.signing_supported ? (
                  <button
                    type="button"
                    onClick={() => void onProveOwnership(w)}
                    disabled={signingId === w.id}
                    className="inline-flex items-center gap-1 rounded border border-emerald-400/40 px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] text-emerald-300 hover:bg-emerald-400/[0.05] disabled:opacity-50"
                  >
                    {signingId === w.id ? (
                      <Loader2 size={10} className="animate-spin" />
                    ) : null}
                    {signatures[w.id] ? "✓ signed" : "prove ownership"}
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => void onDelete(w.id)}
                  className="inline-flex items-center gap-1 rounded border border-alert/40 px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] text-alert hover:bg-alert/[0.06]"
                >
                  <Trash2 size={10} />
                  remove
                </button>
              </div>
              {signatures[w.id] ? (
                <p className="mt-1 break-all font-mono-tech text-[10.5px] text-emerald-300/80">
                  signature {signatures[w.id]}
                </p>
              ) : null}
              {sendOpen === w.id ? (
                w.signing_supported ? (
                  // Phase P1 — chain-specific signed-send form.
                  <ChainSendForm wallet={w} />
                ) : (
                  // Fallback: legacy build-only envelope for chains
                  // that don't yet support local signing.
                  <div className="mt-2 rounded border border-line bg-bg-1 p-2">
                    <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-[1fr_120px_auto]">
                      <input
                        value={sendTo}
                        onChange={(e) => setSendTo(e.target.value)}
                        placeholder="recipient address"
                        className="rounded border border-line bg-bg-0 px-2 py-1 font-mono-tech text-[11.5px] text-ink placeholder:text-ink-2 focus:border-accent focus:outline-none"
                      />
                      <input
                        value={sendAmount}
                        onChange={(e) => setSendAmount(e.target.value)}
                        placeholder="amount"
                        className="rounded border border-line bg-bg-0 px-2 py-1 font-mono-tech text-[11.5px] text-ink placeholder:text-ink-2 focus:border-accent focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => void onBuildSend(w.id)}
                        disabled={busy || !sendTo.trim() || !sendAmount.trim()}
                        className="rounded border border-accent/40 bg-accent/[0.06] px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-accent hover:bg-accent/10 disabled:opacity-50"
                      >
                        build
                      </button>
                    </div>
                    {sendEnvelope ? (
                      <pre className="mt-2 max-h-40 overflow-auto rounded border border-line bg-bg-0 p-2 font-mono-tech text-[10.5px] text-ink-2">
                        {JSON.stringify(sendEnvelope, null, 2)}
                      </pre>
                    ) : null}
                  </div>
                )
              ) : null}
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

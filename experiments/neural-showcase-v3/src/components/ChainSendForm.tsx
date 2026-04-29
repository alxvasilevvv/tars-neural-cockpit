/**
 * Chain-specific send form (Phase P1).
 *
 * Three flavours, one UX:
 *
 * - **Solana**: ``to``, ``amount`` (SOL or lamports), ``recent_blockhash``
 *   with auto-fetch button, optional ``memo``.
 * - **EVM**: ``to``, ``value`` (ETH or wei), ``nonce`` with auto-fetch,
 *   ``chainId`` (default 1 = Ethereum mainnet), ``maxFeePerGas`` /
 *   ``maxPriorityFeePerGas`` (EIP-1559).
 * - **TON**: ``to``, ``amount`` (TON or nanoton), ``seqno`` with
 *   auto-fetch, optional ``payload``.
 *
 * Sign flow:
 *
 * 1. Call ``fetchPolicyStatus`` once per panel mount to learn whether
 *    the HTTP policy gate is enabled.
 * 2. If required, mint a confirm token via ``mintConfirmToken`` with
 *    the prepared params, then attach it to the ``X-TARS-Confirm``
 *    header on the sign call.
 * 3. Display the signed payload (truncated raw + tx_signature/hash/
 *    body_hash) and copy buttons.
 *
 * Privacy: when ``audit_raw_attached`` is on (server-side env flag),
 * the meeet event for this signing carries the raw bytes.
 */

import { useEffect, useMemo, useState } from "react";
import { Check, Copy, Loader2, Shield, Wand2, Zap } from "lucide-react";

import {
  fetchEVMNonce,
  fetchPolicyStatus,
  fetchSolanaBlockhash,
  fetchTONSeqno,
  mintConfirmToken,
  signEVMTransaction,
  signSolanaTransfer,
  signTONTransfer,
  type EVMSigned,
  type SolanaSigned,
  type TONSigned,
  type Wallet,
} from "@/lib/wallet";

export interface ChainSendFormProps {
  wallet: Wallet;
  onSigned?: (kind: "solana" | "evm" | "ton", payload: unknown) => void;
}

type SignedResult =
  | { kind: "solana"; signed: SolanaSigned }
  | { kind: "evm"; signed: EVMSigned }
  | { kind: "ton"; signed: TONSigned };

const TIN = "rounded border border-line bg-bg-0 px-2 py-1 font-mono-tech text-[11.5px] text-ink placeholder:text-ink-2 focus:border-accent focus:outline-none";
const LBL = "font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-2";
const CHIP = "inline-flex items-center gap-1 rounded border border-accent/40 bg-accent/[0.06] px-2 py-[3px] font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-accent hover:bg-accent/10 disabled:opacity-50";
const PRIMARY = "rounded border border-accent/40 bg-accent/[0.08] px-3 py-1 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-accent hover:bg-accent/15 disabled:opacity-50";

export function ChainSendForm({ wallet, onSigned }: ChainSendFormProps) {
  const [to, setTo] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<SignedResult | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [policyRequired, setPolicyRequired] = useState(false);

  // Solana-only
  const [blockhash, setBlockhash] = useState("");
  const [memo, setMemo] = useState("");

  // EVM-only
  const [nonce, setNonce] = useState("");
  const [chainId, setChainId] = useState("1");
  const [maxFeePerGas, setMaxFeePerGas] = useState("30000000000");
  const [maxPriorityFeePerGas, setMaxPriorityFeePerGas] = useState("1000000000");
  const [gas, setGas] = useState("21000");

  // TON-only
  const [seqno, setSeqno] = useState("");
  const [payload, setPayload] = useState("");

  const tokenSymbol = useMemo(() => {
    if (wallet.chain === "solana") return "SOL";
    if (wallet.chain === "evm") return "ETH";
    return "TON";
  }, [wallet.chain]);

  useEffect(() => {
    void fetchPolicyStatus()
      .then((r) => setPolicyRequired(r.required))
      .catch(() => setPolicyRequired(false));
  }, []);

  const onCopy = async (key: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(key);
      setTimeout(() => setCopied(null), 1800);
    } catch {
      /* clipboard denied */
    }
  };

  const onAutofill = async () => {
    setErr(null);
    setBusy(true);
    try {
      if (wallet.chain === "solana") {
        const r = await fetchSolanaBlockhash();
        setBlockhash(r.blockhash);
      } else if (wallet.chain === "evm") {
        const r = await fetchEVMNonce(wallet.address);
        setNonce(String(r.nonce));
      } else {
        const r = await fetchTONSeqno(wallet.address);
        setSeqno(String(r.seqno));
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onSign = async () => {
    setErr(null);
    setResult(null);
    if (!to.trim() || !amount.trim()) {
      setErr("recipient and amount are required");
      return;
    }
    setBusy(true);
    try {
      // Build the request body shaped for each chain.
      let action = "";
      let params: unknown = null;
      if (wallet.chain === "solana") {
        if (!blockhash.trim()) {
          throw new Error("recent_blockhash is required (use ⚡ to autofill)");
        }
        action = "wallet.sign_solana_transfer";
        params = {
          to: to.trim(),
          amount: amount.trim(),
          recent_blockhash: blockhash.trim(),
          ...(memo.trim() ? { memo: memo.trim() } : {}),
        };
      } else if (wallet.chain === "evm") {
        if (!nonce.trim()) {
          throw new Error("nonce is required (use ⚡ to autofill)");
        }
        action = "wallet.sign_evm_tx";
        params = {
          to: to.trim(),
          value: amount.trim(),
          gas: gas.trim() || "21000",
          nonce: nonce.trim(),
          chainId: parseInt(chainId, 10) || 1,
          maxFeePerGas: maxFeePerGas.trim() || undefined,
          maxPriorityFeePerGas: maxPriorityFeePerGas.trim() || undefined,
          type: 2,
        };
      } else {
        action = "wallet.sign_ton_transfer";
        params = {
          to: to.trim(),
          amount: amount.trim(),
          seqno: parseInt(seqno || "0", 10),
          ...(payload.trim() ? { payload: payload.trim() } : {}),
          send_mode: 3,
        };
      }

      // Mint a confirm token if the gate is on.
      let token: string | undefined;
      if (policyRequired) {
        const t = await mintConfirmToken(wallet.id, action, params);
        token = t.token;
      }

      if (wallet.chain === "solana") {
        const r = await signSolanaTransfer(
          wallet.id,
          params as Parameters<typeof signSolanaTransfer>[1],
          token,
        );
        setResult({ kind: "solana", signed: r.signed });
        onSigned?.("solana", r.signed);
      } else if (wallet.chain === "evm") {
        // EVM body sometimes has undefined fields the typed model
        // rejects with strict pydantic — strip them out.
        const evmBody = JSON.parse(
          JSON.stringify(params),
        ) as Parameters<typeof signEVMTransaction>[1];
        const r = await signEVMTransaction(wallet.id, evmBody, token);
        setResult({ kind: "evm", signed: r.signed });
        onSigned?.("evm", r.signed);
      } else {
        const r = await signTONTransfer(
          wallet.id,
          params as Parameters<typeof signTONTransfer>[1],
          token,
        );
        setResult({ kind: "ton", signed: r.signed });
        onSigned?.("ton", r.signed);
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const renderResult = () => {
    if (!result) return null;
    const rows: Array<{ label: string; value: string }> = [];
    if (result.kind === "solana") {
      rows.push({ label: "tx_signature", value: result.signed.tx_signature });
      rows.push({ label: "raw_b58", value: result.signed.raw_b58 });
    } else if (result.kind === "evm") {
      rows.push({ label: "hash", value: result.signed.hash });
      rows.push({ label: "raw", value: result.signed.raw });
    } else {
      rows.push({ label: "body_hash", value: result.signed.body_hash });
      rows.push({ label: "boc", value: result.signed.boc });
    }
    return (
      <div className="mt-3 rounded border border-emerald-400/40 bg-emerald-400/[0.04] p-2.5">
        <div className="mb-1.5 flex items-center gap-1.5 font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-emerald-300">
          <Shield size={10} />
          signed locally · ready to broadcast
        </div>
        <ul className="space-y-1">
          {rows.map((row) => (
            <li key={row.label} className="flex items-start gap-2">
              <span className="w-[88px] shrink-0 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2">
                {row.label}
              </span>
              <code
                className="flex-1 break-all font-mono-tech text-[10.5px] text-ink"
                title={row.value}
              >
                {row.value.length > 96 ? `${row.value.slice(0, 96)}…` : row.value}
              </code>
              <button
                type="button"
                onClick={() => void onCopy(`${result.kind}-${row.label}`, row.value)}
                className="inline-flex items-center gap-0.5 rounded border border-line px-1.5 py-[1px] font-mono-tech text-[9px] uppercase tracking-[1.6px] text-ink-2 hover:border-line-strong hover:text-ink"
              >
                {copied === `${result.kind}-${row.label}` ? (
                  <Check size={10} />
                ) : (
                  <Copy size={10} />
                )}
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <div className="mt-2 rounded border border-line bg-bg-1 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className={LBL}>send · {wallet.chain}</span>
        {policyRequired ? (
          <span className="inline-flex items-center gap-1 font-mono-tech text-[9px] uppercase tracking-[2px] text-amber-300">
            <Shield size={9} />
            policy gate ON
          </span>
        ) : null}
      </div>

      {/* recipient + amount — common to all three */}
      <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-[1fr_140px]">
        <input
          aria-label="recipient address"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          placeholder={
            wallet.chain === "solana"
              ? "recipient pubkey"
              : wallet.chain === "evm"
                ? "0x recipient"
                : "EQ recipient"
          }
          className={TIN}
        />
        <input
          aria-label="amount"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder={`amount · ${tokenSymbol}`}
          className={TIN}
        />
      </div>

      {/* chain-specific extras */}
      <div className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        {wallet.chain === "solana" ? (
          <>
            <div className="flex items-center gap-1.5">
              <input
                aria-label="recent_blockhash"
                value={blockhash}
                onChange={(e) => setBlockhash(e.target.value)}
                placeholder="recent_blockhash"
                className={`${TIN} flex-1`}
              />
              <button
                type="button"
                onClick={() => void onAutofill()}
                disabled={busy}
                title="Fetch latest blockhash"
                className={CHIP}
              >
                <Zap size={11} strokeWidth={1.7} />
              </button>
            </div>
            <input
              aria-label="memo"
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              placeholder="memo (optional)"
              className={TIN}
            />
          </>
        ) : null}

        {wallet.chain === "evm" ? (
          <>
            <div className="flex items-center gap-1.5">
              <input
                aria-label="nonce"
                value={nonce}
                onChange={(e) => setNonce(e.target.value)}
                placeholder="nonce"
                className={`${TIN} flex-1`}
              />
              <button
                type="button"
                onClick={() => void onAutofill()}
                disabled={busy}
                title="Fetch nonce (pending)"
                className={CHIP}
              >
                <Zap size={11} strokeWidth={1.7} />
              </button>
            </div>
            <input
              aria-label="chainId"
              value={chainId}
              onChange={(e) => setChainId(e.target.value)}
              placeholder="chainId · 1 = Ethereum"
              className={TIN}
            />
            <input
              aria-label="gas"
              value={gas}
              onChange={(e) => setGas(e.target.value)}
              placeholder="gas · 21000 default"
              className={TIN}
            />
            <input
              aria-label="maxFeePerGas"
              value={maxFeePerGas}
              onChange={(e) => setMaxFeePerGas(e.target.value)}
              placeholder="maxFeePerGas (wei)"
              className={TIN}
            />
            <input
              aria-label="maxPriorityFeePerGas"
              value={maxPriorityFeePerGas}
              onChange={(e) => setMaxPriorityFeePerGas(e.target.value)}
              placeholder="maxPriorityFeePerGas (wei)"
              className={TIN}
            />
          </>
        ) : null}

        {wallet.chain === "ton" ? (
          <>
            <div className="flex items-center gap-1.5">
              <input
                aria-label="seqno"
                value={seqno}
                onChange={(e) => setSeqno(e.target.value)}
                placeholder="seqno"
                className={`${TIN} flex-1`}
              />
              <button
                type="button"
                onClick={() => void onAutofill()}
                disabled={busy}
                title="Fetch seqno"
                className={CHIP}
              >
                <Zap size={11} strokeWidth={1.7} />
              </button>
            </div>
            <input
              aria-label="payload"
              value={payload}
              onChange={(e) => setPayload(e.target.value)}
              placeholder="payload (optional)"
              className={TIN}
            />
          </>
        ) : null}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={() => void onSign()}
          disabled={busy || !to.trim() || !amount.trim()}
          className={PRIMARY}
        >
          {busy ? (
            <Loader2 size={11} className="mr-1 inline animate-spin" />
          ) : (
            <Wand2 size={11} className="mr-1 inline" strokeWidth={1.7} />
          )}
          sign locally
        </button>
        <span className="font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-2">
          private key never leaves this device
        </span>
      </div>

      {err ? (
        <p className="mt-2 rounded border border-alert/40 bg-alert/[0.06] p-2 font-mono-tech text-[10.5px] text-alert">
          {err}
        </p>
      ) : null}

      {renderResult()}
    </div>
  );
}

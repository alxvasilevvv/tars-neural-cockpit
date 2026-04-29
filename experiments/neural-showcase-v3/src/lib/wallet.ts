/**
 * Cockpit client for the user-owned crypto wallets (Phase M2).
 *
 * Mnemonic safety:
 *
 * - The mnemonic is returned ONCE on `createWallet` and is never
 *   persisted in localStorage or sent over the wire again.
 * - All other endpoints return the public-only Wallet shape.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "./api";

export type WalletChain = "solana" | "evm" | "ton";

export interface Wallet {
  id: string;
  label: string;
  chain: WalletChain;
  address: string;
  public_key_hex: string;
  derivation_path: string;
  seed_fingerprint: string | null;
  signing_supported: boolean;
  created_at: number;
  updated_at: number;
  derivation_scheme?: string;
}

export interface CreateWalletResponse {
  ok: boolean;
  trace_id: string | null;
  wallet: Wallet;
  mnemonic: string | null;
  mnemonic_warning: string;
}

const WALLET = `${API_BASE}/api/wallet`;

async function jsonOr<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`HTTP ${resp.status} · ${text}`);
  }
  return (await resp.json()) as T;
}

export async function listWallets(
  chain?: WalletChain,
): Promise<{ ok: boolean; count: number; wallets: Wallet[] }> {
  const qs = chain ? `?chain=${chain}` : "";
  return jsonOr(await fetch(`${WALLET}${qs}`));
}

export async function getWallet(
  walletId: string,
): Promise<{ ok: boolean; wallet: Wallet }> {
  return jsonOr(await fetch(`${WALLET}/${encodeURIComponent(walletId)}`));
}

export async function createWallet(
  label: string,
  chain: WalletChain,
  index = 0,
  derivationScheme?: string,
): Promise<CreateWalletResponse> {
  const body: Record<string, unknown> = { label, chain, index };
  if (derivationScheme) body.derivation_scheme = derivationScheme;
  return jsonOr(
    await fetch(WALLET, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function importWallet(
  label: string,
  chain: WalletChain,
  mnemonic: string,
  passphrase = "",
): Promise<{ ok: boolean; wallet: Wallet }> {
  return jsonOr(
    await fetch(`${WALLET}/import`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ label, chain, mnemonic, passphrase }),
    }),
  );
}

export async function deleteWallet(
  walletId: string,
): Promise<{ ok: boolean }> {
  return jsonOr(
    await fetch(`${WALLET}/${encodeURIComponent(walletId)}`, {
      method: "DELETE",
    }),
  );
}

export interface BalanceReading {
  chain: WalletChain;
  address: string;
  raw: string;
  decimals: number;
  symbol: string;
  display: string;
  rpc_url: string;
}

export interface BalanceResult {
  ok: boolean;
  trace_id?: string | null;
  balance?: BalanceReading;
  error?: string;
}

export async function fetchBalance(
  walletId: string,
  rpcUrl?: string,
): Promise<BalanceResult> {
  const qs = rpcUrl ? `?rpc_url=${encodeURIComponent(rpcUrl)}` : "";
  return jsonOr(
    await fetch(`${WALLET}/${encodeURIComponent(walletId)}/balance${qs}`),
  );
}

export async function buildSend(
  walletId: string,
  to: string,
  amount: string,
  memo?: string,
): Promise<{ ok: boolean; envelope: Record<string, unknown> }> {
  return jsonOr(
    await fetch(`${WALLET}/${encodeURIComponent(walletId)}/build_send`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ to, amount, memo }),
    }),
  );
}

export async function signMessage(
  walletId: string,
  message: string,
): Promise<{ ok: boolean; signature_b64: string }> {
  return jsonOr(
    await fetch(`${WALLET}/${encodeURIComponent(walletId)}/sign`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
    }),
  );
}

export interface EVMSigned {
  raw: string;
  hash: string;
  r: string;
  s: string;
  v: number;
}

export interface EVMTxRequest {
  to: string;
  value: string;
  gas?: string;
  nonce: string;
  chainId: number;
  data?: string;
  maxFeePerGas?: string;
  maxPriorityFeePerGas?: string;
  gasPrice?: string;
  type?: number;
}

export async function signEVMTransaction(
  walletId: string,
  tx: EVMTxRequest,
  confirmToken?: string,
): Promise<{ ok: boolean; signed: EVMSigned }> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (confirmToken) headers["X-TARS-Confirm"] = confirmToken;
  return jsonOr(
    await fetch(`${WALLET}/${encodeURIComponent(walletId)}/sign_evm_tx`, {
      method: "POST",
      headers,
      body: JSON.stringify(tx),
    }),
  );
}

export interface TONSigned {
  boc: string;
  body_hash: string;
  address: string;
  to: string;
  amount_nanoton: number;
  seqno: number;
  workchain: number;
}

export interface TONTransferRequest {
  to: string;
  amount: string;
  seqno?: number;
  payload?: string;
  send_mode?: number;
}

export async function signTONTransfer(
  walletId: string,
  tx: TONTransferRequest,
  confirmToken?: string,
): Promise<{ ok: boolean; signed: TONSigned }> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (confirmToken) headers["X-TARS-Confirm"] = confirmToken;
  return jsonOr(
    await fetch(
      `${WALLET}/${encodeURIComponent(walletId)}/sign_ton_transfer`,
      {
        method: "POST",
        headers,
        body: JSON.stringify(tx),
      },
    ),
  );
}

export interface SolanaSigned {
  raw_b64: string;
  raw_b58: string;
  raw_hex: string;
  tx_signature: string;
  signer: string;
  recipient: string;
  lamports: number;
  blockhash: string;
  memo: string | null;
}

export interface SolanaTransferRequest {
  to: string;
  amount: string;
  recent_blockhash: string;
  memo?: string;
}

export async function signSolanaTransfer(
  walletId: string,
  tx: SolanaTransferRequest,
  confirmToken?: string,
): Promise<{ ok: boolean; signed: SolanaSigned }> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (confirmToken) headers["X-TARS-Confirm"] = confirmToken;
  return jsonOr(
    await fetch(
      `${WALLET}/${encodeURIComponent(walletId)}/sign_solana_transfer`,
      {
        method: "POST",
        headers,
        body: JSON.stringify(tx),
      },
    ),
  );
}

// ---------- live RPC helpers (P2/P3/P4) ------------------------------

export interface SolanaBlockhash {
  ok: boolean;
  blockhash: string;
  last_valid_block_height: number | null;
  rpc_url: string;
}

export async function fetchSolanaBlockhash(): Promise<SolanaBlockhash> {
  return jsonOr(await fetch(`${WALLET}/solana/blockhash`));
}

export interface EVMNonce {
  ok: boolean;
  address: string;
  nonce: number;
  nonce_hex: string;
  block_tag: string;
  rpc_url: string;
}

export async function fetchEVMNonce(
  address: string,
  blockTag: "pending" | "latest" | "earliest" = "pending",
): Promise<EVMNonce> {
  const qs = `?block_tag=${blockTag}`;
  return jsonOr(
    await fetch(
      `${WALLET}/evm/${encodeURIComponent(address)}/nonce${qs}`,
    ),
  );
}

export interface TONSeqno {
  ok: boolean;
  address: string;
  seqno: number;
  rpc_url: string;
}

export async function fetchTONSeqno(address: string): Promise<TONSeqno> {
  return jsonOr(
    await fetch(`${WALLET}/ton/${encodeURIComponent(address)}/seqno`),
  );
}

// ---------- policy gate (O2) ----------------------------------------

export interface PolicyStatus {
  ok: boolean;
  required: boolean;
}

export async function fetchPolicyStatus(): Promise<PolicyStatus> {
  return jsonOr(await fetch(`${WALLET}/policy/status`));
}

export interface ConfirmToken {
  ok: boolean;
  token: string;
  expires_at: number;
  ttl_s: number;
}

export async function mintConfirmToken(
  walletId: string,
  action: string,
  params: unknown,
  ttlS = 300,
): Promise<ConfirmToken> {
  return jsonOr(
    await fetch(
      `${WALLET}/${encodeURIComponent(walletId)}/confirm`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action, params, ttl_s: ttlS }),
      },
    ),
  );
}

export function useWallets(intervalMs = 0): {
  wallets: Wallet[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelled = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const out = await listWallets();
      if (!cancelled.current) {
        setWallets(out.wallets);
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

  return { wallets, loading, error, refresh };
}

export function shortenAddress(addr: string, head = 6, tail = 6): string {
  if (!addr || addr.length <= head + tail + 3) return addr;
  return `${addr.slice(0, head)}…${addr.slice(-tail)}`;
}

export function chainBadgeClass(chain: WalletChain): string {
  switch (chain) {
    case "solana":
      return "text-violet-300 ring-violet-400/40";
    case "evm":
      return "text-sky-300 ring-sky-400/40";
    case "ton":
      return "text-cyan-300 ring-cyan-400/40";
    default:
      return "text-zinc-300 ring-zinc-500/30";
  }
}

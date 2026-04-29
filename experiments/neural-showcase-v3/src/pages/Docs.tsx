import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowLeft, ExternalLink, Copy, Check } from "lucide-react";
import { useState } from "react";
import { useDocumentMeta } from "@/lib/meta";
import { BrandHairline } from "@/components/BrandHairline";
import { SitemapGrid } from "@/components/SitemapGrid";

/**
 * /docs — API reference index. Lists the public HTTP surface of the
 * local TARS daemon (`backend/...`) plus the cloud-side meeet.world
 * endpoints. Each row deep-links to either a contracts doc on GitHub
 * or to the page in the cockpit that exercises it.
 *
 * Source of truth for endpoint shapes lives in `docs/contracts/`.
 */

interface Endpoint {
  method: "GET" | "POST" | "PATCH" | "DELETE";
  path: string;
  body: string;
  contractPath?: string; // optional GitHub anchor
}

interface Group {
  num: string;
  name: string;
  intro: string;
  endpoints: Endpoint[];
}

const GROUPS: Group[] = [
  {
    num: "01",
    name: "Product downloads",
    intro: "Public, cache-friendly. Consumed by the marketing site and meeet.world SSR.",
    endpoints: [
      { method: "GET", path: "/api/product/downloads",            body: "Full release manifest, contract 1.0.0", contractPath: "MEEET_DOWNLOADS.md" },
      { method: "GET", path: "/api/product/downloads/latest",     body: "Latest release filtered by ?os= and ?channel=", contractPath: "MEEET_DOWNLOADS.md" },
      { method: "GET", path: "/api/product/version",              body: "Minimal version probe for Tauri updater", contractPath: "MEEET_DOWNLOADS.md" },
    ],
  },
  {
    num: "02",
    name: "Conversation (Phase L1 + L2)",
    intro: "Chat threads, streaming SSE, attachments, RAG with citations.",
    endpoints: [
      { method: "POST", path: "/api/chat/threads",                                  body: "Create a thread" },
      { method: "GET",  path: "/api/chat/threads",                                  body: "List threads" },
      { method: "POST", path: "/api/chat/threads/{id}/messages",                    body: "Send operator turn (SSE response)" },
      { method: "POST", path: "/api/chat/threads/{id}/attachments",                 body: "Upload + ingest attachment" },
      { method: "GET",  path: "/api/chat/threads/{id}/timeline",                    body: "Per-thread observability feed" },
    ],
  },
  {
    num: "03",
    name: "Search (Phase L8)",
    intro: "Cross-thread hybrid search — FTS5 BM25 + vector cosine, fused via reciprocal rank.",
    endpoints: [
      { method: "POST", path: "/api/search",          body: "Unified — chunks + messages + traces" },
      { method: "POST", path: "/api/search/chunks",   body: "Files only, with thread title + permalink" },
      { method: "POST", path: "/api/search/messages", body: "Operator + TARS messages" },
      { method: "POST", path: "/api/search/traces",   body: "Free-text over meeet event payloads" },
    ],
  },
  {
    num: "04",
    name: "Domain packs + actions",
    intro: "Pluggable packs. Destructive actions flow through the policy gate.",
    endpoints: [
      { method: "GET",  path: "/api/domains",                                       body: "List packs (live + composites)" },
      { method: "GET",  path: "/api/domains/manifest",                              body: "Static manifest of all registered packs" },
      { method: "GET",  path: "/api/domains/{slug}",                                body: "Pack details (actions + awareness)" },
      { method: "POST", path: "/api/domains/{slug}/actions/{action_id}",            body: "Invoke an action (policy-gated)" },
      { method: "GET",  path: "/api/domains/{slug}/awareness/{id}/snapshot",        body: "Awareness source snapshot" },
      { method: "GET",  path: "/api/awareness/stream",                              body: "SSE: hello / pulse / heartbeat / bye" },
    ],
  },
  {
    num: "05",
    name: "Council, policy, playbooks",
    intro: "Two-voice deliberation, destructive-action gate, multi-step automations.",
    endpoints: [
      { method: "POST", path: "/api/council/deliberate",                            body: "Run a council vote on a prompt" },
      { method: "GET",  path: "/api/policy/pending",                                body: "Destructive actions awaiting confirm" },
      { method: "POST", path: "/api/policy/confirm/{token}",                        body: "Operator-confirmed run" },
      { method: "POST", path: "/api/policy/cancel/{token}",                         body: "Operator-cancelled run" },
      { method: "GET",  path: "/api/playbooks",                                     body: "List registered playbooks" },
      { method: "POST", path: "/api/playbooks/{id}/run",                            body: "Run playbook (autopilot via header)" },
    ],
  },
  {
    num: "06",
    name: "Pairing (Phase L5)",
    intro: "Device pairing — X25519 identity, XChaCha20-Poly1305 envelope.",
    endpoints: [
      { method: "POST", path: "/api/pairing/begin",        body: "Mint pair_id, return host_fingerprint", contractPath: "L5_PAIRING_DRAFT.md" },
      { method: "POST", path: "/api/pairing/accept/{token}", body: "Operator-confirmed link",            contractPath: "L5_PAIRING_DRAFT.md" },
      { method: "POST", path: "/api/pairing/reject/{token}", body: "Operator declined",                  contractPath: "L5_PAIRING_DRAFT.md" },
      { method: "GET",  path: "/api/pairing/status",        body: "Poll pair state",                     contractPath: "L5_PAIRING_DRAFT.md" },
      { method: "GET",  path: "/api/pairing/devices",       body: "List paired devices",                 contractPath: "L5_PAIRING_DRAFT.md" },
      { method: "POST", path: "/api/pairing/revoke",        body: "Revoke a device, bump epoch",          contractPath: "L5_PAIRING_DRAFT.md" },
    ],
  },
  {
    num: "07",
    name: "Usage + meeet event store",
    intro: "Cost ledger and the durable buffer that powers replay.",
    endpoints: [
      { method: "GET",  path: "/api/usage",          body: "Spend rolled up by model / route / session" },
      { method: "GET",  path: "/api/usage/lines",    body: "Raw usage rows" },
      { method: "GET",  path: "/api/usage/prices",   body: "Active price overrides" },
      { method: "GET",  path: "/api/meeet/events",   body: "SQLite event trail (filterable)" },
      { method: "GET",  path: "/api/meeet/health",   body: "Buffer + replay status" },
      { method: "POST", path: "/api/meeet/replay",   body: "Trigger replay loop" },
    ],
  },
  {
    num: "08",
    name: "Health + identity",
    intro: "Probes for monitoring + the host identity surface.",
    endpoints: [
      { method: "GET",  path: "/health",                       body: "Liveness probe — JSON ok/uptime/meeet" },
      { method: "GET",  path: "/api/pairing/identity",         body: "Host fingerprint + master public key" },
    ],
  },
];

const METHOD_TONES: Record<Endpoint["method"], string> = {
  GET:    "#34D399",
  POST:   "#6366F1",
  PATCH:  "#F59E0B",
  DELETE: "#EF4444",
};

type VerbFilter = Endpoint["method"] | "ALL";

export function Docs() {
  useDocumentMeta({
    title: "API reference",
    description: "Public HTTP surface for TARS — local daemon endpoints plus meeet.world cloud APIs.",
  });
  const [filter, setFilter] = useState<VerbFilter>("ALL");
  const verbs: VerbFilter[] = ["ALL", "GET", "POST", "PATCH", "DELETE"];
  return (
    <div className="relative min-h-[calc(100vh-72px)]">
      <BrandHairline />

      <article className="mx-auto max-w-[920px] px-6 pb-28 pt-14 md:px-12 md:pt-20">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <Link
            to="/"
            className="inline-flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 transition-colors duration-150 hover:text-ink"
          >
            <ArrowLeft size={12} strokeWidth={1.8} /> back to home
          </Link>

          <header className="mb-12 mt-8 grid grid-cols-1 gap-3 border-b border-line pb-10">
            <div className="flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
              <span style={{ color: "var(--brand-indigo)" }}>05</span>
              <span>API reference</span>
              <span aria-hidden>·</span>
              <span className="text-ink-3">contract 1.1.0 · v9.0</span>
            </div>
            <h1
              className="font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
              style={{ fontSize: "var(--text-display-lg)" }}
            >
              The HTTP surface{" "}
              <span
                className="bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(95deg, var(--brand-indigo) 0%, var(--brand-violet) 50%, var(--brand-cyan) 100%)",
                }}
              >
                an operator can call
              </span>
              .
            </h1>
            <p className="mt-3 max-w-[64ch] text-[14.5px] leading-[1.65] text-ink-2">
              Local daemon binds to <code className="rounded bg-bg-2 px-1 py-0.5 font-mono text-[0.92em] text-ink">127.0.0.1:8765</code>.
              No inbound LAN. Wire shapes for cross-boundary contracts pinned in
              {" "}<a
                href="https://github.com/meeet-world/tars/tree/main/docs/contracts"
                target="_blank"
                rel="noopener"
                className="text-accent hover:underline"
              >
                docs/contracts/
              </a>.
            </p>
          </header>

          {/* Sitemap — every route on this domain at a glance */}
          <SitemapGrid />

          {/* Verb filter chips — quick narrow by HTTP method */}
          <div
            role="toolbar"
            aria-label="filter endpoints by verb"
            className="mb-10 flex flex-wrap items-center gap-2"
          >
            <span className="mr-1 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
              filter
            </span>
            {verbs.map(v => {
              const active = filter === v;
              const tone = v === "ALL" ? "var(--color-ink-2)" : METHOD_TONES[v];
              const total =
                v === "ALL"
                  ? GROUPS.reduce((n, g) => n + g.endpoints.length, 0)
                  : GROUPS.reduce(
                      (n, g) => n + g.endpoints.filter(e => e.method === v).length,
                      0,
                    );
              return (
                <button
                  key={v}
                  type="button"
                  onClick={() => setFilter(v)}
                  aria-pressed={active}
                  className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] transition-all duration-150"
                  style={{
                    borderColor: active ? tone : "var(--color-line)",
                    background: active
                      ? `color-mix(in srgb, ${tone} 14%, transparent)`
                      : "transparent",
                    color: active ? tone : "var(--color-ink-2)",
                  }}
                >
                  <span>{v}</span>
                  <span className="opacity-60 tabular-nums">{total}</span>
                </button>
              );
            })}
          </div>

          {GROUPS.map(g => {
            const filtered =
              filter === "ALL"
                ? g.endpoints
                : g.endpoints.filter(e => e.method === filter);
            if (filtered.length === 0) return null;
            return (
            <section key={g.num} className="mb-12">
              <header className="mb-4 flex items-baseline gap-3">
                <span className="font-mono-tech text-[11px] uppercase tracking-[3px]" style={{ color: "var(--brand-indigo)" }}>
                  {g.num}
                </span>
                <h2 className="font-display text-[20px] tracking-[-0.005em] text-ink">{g.name}</h2>
              </header>
              <p className="mb-5 max-w-[64ch] text-[13.5px] leading-[1.6] text-ink-2">{g.intro}</p>

              <ul className="overflow-hidden rounded-[12px] border border-line bg-bg-1/60">
                {filtered.map((e, i) => (
                  <li
                    key={`${e.method}${e.path}`}
                    className={`grid items-center gap-3 px-4 py-3 md:grid-cols-[64px_1fr_auto] md:px-5 ${
                      i < g.endpoints.length - 1 ? "border-b border-line" : ""
                    }`}
                  >
                    <span
                      className="inline-flex h-6 w-fit items-center rounded-md px-2 font-mono-tech text-[10px] uppercase tracking-[2px]"
                      style={{
                        color: METHOD_TONES[e.method],
                        background: `color-mix(in srgb, ${METHOD_TONES[e.method]} 14%, transparent)`,
                        boxShadow: `inset 0 0 0 1px ${METHOD_TONES[e.method]}55`,
                      }}
                    >
                      {e.method}
                    </span>
                    <div className="min-w-0">
                      <code className="block truncate font-mono text-[12.5px] text-ink">{e.path}</code>
                      <span className="mt-0.5 block truncate text-[11.5px] leading-[1.5] text-ink-3">
                        {e.body}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 justify-self-end">
                      <CurlCopyButton method={e.method} path={e.path} />
                      {e.contractPath && (
                        <a
                          href={`https://github.com/meeet-world/tars/blob/main/docs/contracts/${e.contractPath}`}
                          target="_blank"
                          rel="noopener"
                          className="inline-flex items-center gap-1.5 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3 transition-colors hover:text-ink"
                        >
                          contract <ExternalLink size={10} strokeWidth={1.6} />
                        </a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
            );
          })}

          <footer className="mt-12 border-t border-line pt-8 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3">
            Bigger surface? Read the full source on{" "}
            <a
              href="https://github.com/meeet-world/tars"
              target="_blank"
              rel="noopener"
              className="text-ink-2 hover:text-ink"
            >
              GitHub
            </a>{" "}
            or join{" "}
            <a
              href="https://discord.gg/meeet"
              target="_blank"
              rel="noopener"
              className="text-ink-2 hover:text-ink"
            >
              discord
            </a>{" "}
            and ask.
          </footer>
        </motion.div>
      </article>
    </div>
  );
}

/**
 * CurlCopyButton — generates a starter `curl` command for the row's
 * (method, path) tuple and copies it to the clipboard. Defaults to
 * the local daemon (127.0.0.1:8765) since this surface is meant for
 * operators trying things from their own machine; cross-boundary
 * calls already point at meeet.world via the contract docs.
 */
function CurlCopyButton({
  method,
  path,
}: {
  method: Endpoint["method"];
  path: string;
}) {
  const [copied, setCopied] = useState(false);
  const cmd = buildCurl(method, path);
  const onClick = () => {
    navigator.clipboard?.writeText(cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`copy curl for ${method} ${path}`}
      title={cmd}
      className="inline-flex items-center gap-1.5 rounded-md border border-line bg-bg-2/40 px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
    >
      {copied ? (
        <>
          <Check size={10} strokeWidth={2.2} className="text-success" /> copied
        </>
      ) : (
        <>
          <Copy size={10} strokeWidth={1.6} /> curl
        </>
      )}
    </button>
  );
}

function buildCurl(method: Endpoint["method"], path: string): string {
  // Concrete URL — operators can swap host trivially.
  const url = `http://127.0.0.1:8765${path}`;
  if (method === "GET") return `curl -fsSL ${url}`;
  return `curl -fsSL -X ${method} -H 'content-type: application/json' \\\n  -d '{}' ${url}`;
}

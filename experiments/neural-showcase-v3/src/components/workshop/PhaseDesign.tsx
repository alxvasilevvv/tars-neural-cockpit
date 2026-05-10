// SYNC: claude-w80-fe-only
/**
 * PhaseDesign — pick a domain pack and configure the agent that
 * will execute the playbook. Wraps `/api/agents` create plus two
 * new fields Cursor is shipping:
 *   - output_schema   — JSON-schema the agent must validate against.
 *   - hil_threshold   — confidence below which we ask the operator.
 *
 * Both fields gracefully no-op if the backend ignores them.
 */

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, Wand2, Save } from "lucide-react";
import { listDomains, type DomainPack } from "@/lib/api";
import { createAgent, type Agent } from "@/lib/agents";

interface PhaseDesignProps {
  onComplete: (agent: Agent) => void;
}

export function PhaseDesign({ onComplete }: PhaseDesignProps) {
  const [packs, setPacks] = useState<DomainPack[] | null>(null);
  const [pack, setPack] = useState<string>("traders");
  const [name, setName] = useState("Workshop agent");
  const [hil, setHil] = useState<number>(0.7);
  const [outputSchema, setOutputSchema] = useState<string>(
    JSON.stringify({ type: "object", properties: { decision: { type: "string" } } }, null, 2),
  );
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [agent, setAgent] = useState<Agent | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const ps = await listDomains();
        setPacks(ps);
        if (ps.length && !ps.some((p) => p.slug === pack)) setPack(ps[0].slug);
      } catch {
        setPacks([]);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreate = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await createAgent({
        name: name.trim() || "Workshop agent",
        pack_slug: pack,
        // Backend may not yet read these — stash in metadata so they
        // round-trip without breaking older servers.
        metadata: {
          output_schema: tryParse(outputSchema),
          hil_threshold: hil,
          source: "workshop",
        },
      });
      setAgent(r.agent);
      onComplete(r.agent);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <motion.section
      initial={{ opacity: 1 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="grid gap-6"
    >
      <header className="grid gap-2">
        <div className="inline-flex items-center gap-2 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
          <Wand2
            size={12}
            strokeWidth={1.7}
            aria-hidden
            style={{ color: "var(--brand-violet)" }}
          />
          <span>phase 02 · design</span>
        </div>
        <h2 className="font-display text-[28px] leading-[1.05] tracking-[-0.01em] text-ink md:text-[34px]">
          Pick a domain pack and tune the agent.
        </h2>
        <p className="max-w-[60ch] font-mono-tech text-[12px] leading-[1.6] text-ink-2">
          Output schema constrains what the agent can return. HIL threshold
          decides when the operator is asked to confirm.
        </p>
      </header>

      <div className="grid gap-5 md:grid-cols-2">
        <div className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <label className="block font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            agent name
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1.5 w-full rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-display text-[13.5px] text-ink outline-none focus:border-accent"
          />

          <label className="mt-4 block font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            domain pack
          </label>
          {packs === null ? (
            <p className="mt-1.5 font-mono-tech text-[10.5px] text-ink-3">loading…</p>
          ) : packs.length === 0 ? (
            <p className="mt-1.5 font-mono-tech text-[10.5px] text-ink-3">
              daemon offline · using fallback list
            </p>
          ) : null}
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {(packs && packs.length > 0
              ? packs.map((p) => p.slug)
              : ["traders", "business", "science", "wallet"]
            ).map((slug) => (
              <button
                key={slug}
                type="button"
                onClick={() => setPack(slug)}
                className={`rounded-md border px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[1.6px] transition-colors ${
                  pack === slug
                    ? "border-accent bg-accent/[0.08] text-ink"
                    : "border-line/60 text-ink-2 hover:border-accent/60"
                }`}
              >
                {slug}
              </button>
            ))}
          </div>

          <label className="mt-4 block font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            HIL threshold · {hil.toFixed(2)}
          </label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={hil}
            onChange={(e) => setHil(parseFloat(e.target.value))}
            className="mt-1.5 w-full accent-[color:var(--color-accent)]"
            aria-label="human-in-the-loop confidence threshold"
          />
          <p className="mt-1 font-mono-tech text-[10px] uppercase tracking-[1.4px] text-ink-3">
            Below this confidence, ask the operator before acting.
          </p>
        </div>

        <div className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <label className="block font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            output schema · JSON
          </label>
          <textarea
            value={outputSchema}
            onChange={(e) => setOutputSchema(e.target.value)}
            rows={12}
            spellCheck={false}
            className="mt-1.5 w-full resize-y rounded-md border border-line/60 bg-bg-0/60 p-3 font-mono-tech text-[11px] leading-[1.55] text-ink-2 outline-none focus:border-accent"
          />
          <p className="mt-1 font-mono-tech text-[10px] uppercase tracking-[1.4px] text-ink-3">
            Validates each agent response. Invalid → retry once, then HIL.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
          {agent
            ? `agent ready · ${agent.id}`
            : err
              ? err
              : "configure and create"}
        </span>
        <button
          type="button"
          onClick={handleCreate}
          disabled={busy || !pack}
          className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent disabled:opacity-50"
        >
          {busy ? (
            <Loader2 size={12} strokeWidth={2} className="animate-spin" aria-hidden />
          ) : (
            <Save size={12} strokeWidth={1.7} aria-hidden />
          )}
          <span>{busy ? "creating…" : "create agent"}</span>
        </button>
      </div>
    </motion.section>
  );
}

function tryParse(s: string): unknown {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

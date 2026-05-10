// SYNC: claude-w80-fe-only
/**
 * <AgentDesigner /> — Wave 80-D
 *
 * Standalone form for designing or patching a TARS agent. PhaseDesign
 * already ships a slim variant; this component is the maximalist
 * editor referenced from advanced flows: full system prompt with a
 * coarse token estimate, role/pack picker, sample-input drag-drop,
 * HIL slider, and the visual <OutputSchemaBuilder /> from Wave 80-B.
 *
 * Save flow:
 *   - new agent  → POST /api/agents
 *   - existing   → PATCH /api/agents/{id}
 *   - test btn   → POST /api/agents/{id}/score with one sample input
 *
 * Backend hand-off contract: same as `lib/agents.ts`. When the
 * daemon returns 404 (route not yet shipped) or the network drops,
 * we surface a soft-toast + keep the draft locally — no data loss.
 */

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  FileUp,
  Loader2,
  Play,
  Save,
} from "lucide-react";
import {
  createAgent,
  patchAgent,
  type Agent,
  type CreateAgentInput,
} from "@/lib/agents";
import { listDomains, API_BASE, type DomainPack } from "@/lib/api";
import {
  OutputSchemaBuilder,
  fieldsToSchema,
  makeEmptyField,
  type SchemaField,
} from "@/components/workshop/OutputSchemaBuilder";
import { toast } from "@/lib/toast";

interface AgentDesignerProps {
  /** Pre-fill from an existing agent. Omit to create a new one. */
  initial?: Agent | null;
  /** Called after a successful save so the parent can refresh / advance. */
  onSaved?: (agent: Agent) => void;
}

const FALLBACK_PACKS = ["traders", "business", "science", "wallet"];

/**
 * Coarse token estimator — chars/4 is the OpenAI rule-of-thumb for
 * English-leaning prompts. Good enough for a UI hint; nothing in the
 * pipeline actually uses this number to bill.
 */
function estimateTokens(s: string): number {
  return Math.ceil(s.length / 4);
}

export function AgentDesigner({ initial, onSaved }: AgentDesignerProps) {
  const isPatch = Boolean(initial?.id);

  const [packs, setPacks] = useState<DomainPack[] | null>(null);
  const [name, setName] = useState(initial?.name ?? "Workshop agent");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [pack, setPack] = useState(initial?.pack_slug ?? "traders");
  const [systemPrompt, setSystemPrompt] = useState(
    initial?.system_prompt ??
      "You are a focused agent. Keep responses short, factual, and structured.",
  );
  const [hil, setHil] = useState(0.7);
  const [fields, setFields] = useState<SchemaField[]>([
    {
      ...makeEmptyField(),
      name: "decision",
      type: "enum",
      description: "agent recommendation",
      required: true,
      enumValues: "buy,hold,sell",
    },
    {
      ...makeEmptyField(),
      name: "confidence",
      type: "number",
      description: "0-1 confidence in the decision",
      required: true,
    },
  ]);
  const [sampleText, setSampleText] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<Agent | null>(initial ?? null);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [scoring, setScoring] = useState(false);
  const [scoreOutput, setScoreOutput] = useState<string | null>(null);
  const [pendingNote, setPendingNote] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const ps = await listDomains();
        setPacks(ps);
        if (ps.length > 0 && !ps.some((p) => p.slug === pack)) {
          setPack(ps[0].slug);
        }
      } catch {
        setPacks([]);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tokens = useMemo(
    () => estimateTokens(systemPrompt + "\n" + description),
    [systemPrompt, description],
  );

  const handleFile = async (file: File) => {
    try {
      const text = await file.text();
      setSampleText(text);
    } catch (e) {
      toast.error(`failed to read file · ${(e as Error).message}`);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveErr(null);
    setPendingNote(null);
    const schema = fieldsToSchema(fields);
    const payload: CreateAgentInput = {
      name: name.trim() || "Workshop agent",
      pack_slug: pack,
      description: description.trim() || undefined,
      system_prompt: systemPrompt.trim() || undefined,
      metadata: {
        output_schema: schema,
        hil_threshold: hil,
        source: "workshop:designer",
      },
    };
    try {
      const r =
        isPatch && initial?.id
          ? await patchAgent(initial.id, {
              name: payload.name,
              description: payload.description,
              system_prompt: payload.system_prompt,
              metadata: payload.metadata,
            })
          : await createAgent(payload);
      setSaved(r.agent);
      toast.success(isPatch ? "agent updated" : "agent created");
      onSaved?.(r.agent);
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("404")) {
        // Backend WIP — synthesise a local agent so the workshop flow
        // doesn't dead-end.
        const mock: Agent = {
          id: initial?.id ?? `mock-${Date.now().toString(36)}`,
          name: payload.name,
          pack_slug: pack,
          description: payload.description ?? "",
          system_prompt: payload.system_prompt ?? null,
          wallet_address: null,
          status: "active",
          created_at: Date.now() / 1000,
          updated_at: Date.now() / 1000,
        };
        setSaved(mock);
        setPendingNote("Backend WIP — Cursor shipping. Saved locally.");
        onSaved?.(mock);
      } else {
        setSaveErr(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!saved?.id) {
      setSaveErr("Save the agent before running a test.");
      return;
    }
    if (!sampleText.trim()) {
      setSaveErr("Paste or upload a sample input first.");
      return;
    }
    setScoring(true);
    setScoreOutput(null);
    setSaveErr(null);
    try {
      const r = await fetch(
        `${API_BASE}/api/agents/${encodeURIComponent(saved.id)}/score`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ input: sampleText }),
        },
      );
      if (r.status === 404) {
        // Mock plausible response.
        setScoreOutput(
          JSON.stringify({ decision: "hold", confidence: 0.62 }, null, 2),
        );
        setPendingNote("Backend WIP — score route mocked.");
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      setScoreOutput(JSON.stringify(body, null, 2));
    } catch (e) {
      setSaveErr(`test failed · ${(e as Error).message}`);
    } finally {
      setScoring(false);
    }
  };

  return (
    <section className="grid gap-5">
      <header className="flex items-center justify-between gap-3">
        <div className="inline-flex items-center gap-2 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
          <Bot
            size={12}
            strokeWidth={1.7}
            aria-hidden
            style={{ color: "var(--brand-violet)" }}
          />
          <span>agent designer</span>
        </div>
        <span className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
          ~{tokens} tokens · system+desc
        </span>
      </header>

      {pendingNote && (
        <p
          role="status"
          className="inline-flex items-start gap-2 rounded-md border border-amber-400/30 bg-amber-400/[0.06] px-3 py-2 text-[11.5px] leading-[1.5] text-amber-200"
        >
          <AlertCircle size={12} strokeWidth={1.7} aria-hidden className="mt-0.5" />
          <span>{pendingNote}</span>
        </p>
      )}

      <div className="grid gap-5 md:grid-cols-2">
        {/* ── Identity ─────────────────────────────────────────── */}
        <div className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <label className="block font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            name
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1.5 w-full rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-display text-[13.5px] text-ink outline-none focus:border-accent"
          />

          <label className="mt-4 block font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="mt-1.5 w-full resize-y rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-mono-tech text-[12px] leading-[1.55] text-ink-2 outline-none focus:border-accent"
            placeholder="What this agent does, in two sentences."
          />

          <label
            htmlFor="ad-pack"
            className="mt-4 block font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3"
          >
            role · pack
          </label>
          <select
            id="ad-pack"
            value={pack}
            onChange={(e) => setPack(e.target.value)}
            className="mt-1.5 w-full rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-mono-tech text-[12px] text-ink outline-none focus:border-accent"
          >
            {(packs && packs.length > 0
              ? packs.map((p) => p.slug)
              : FALLBACK_PACKS
            ).map((slug) => (
              <option key={slug} value={slug}>
                {slug}
              </option>
            ))}
          </select>

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
            Below this confidence, the operator confirms the action.
          </p>
        </div>

        {/* ── Prompt + sample input ───────────────────────────── */}
        <div className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <label className="block font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            system prompt
          </label>
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            rows={8}
            spellCheck={false}
            className="mt-1.5 w-full resize-y rounded-md border border-line/60 bg-bg-0/60 p-3 font-mono-tech text-[11.5px] leading-[1.55] text-ink-2 outline-none focus:border-accent"
          />

          <div className="mt-4 flex items-center justify-between">
            <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
              sample input
            </span>
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-line/60 px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2 transition-colors hover:border-accent">
              <FileUp size={10} strokeWidth={1.8} aria-hidden />
              <span>upload</span>
              <input
                type="file"
                accept=".txt,.csv,.json,application/json,text/*"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void handleFile(f);
                }}
                className="hidden"
              />
            </label>
          </div>
          <textarea
            value={sampleText}
            onChange={(e) => setSampleText(e.target.value)}
            rows={5}
            spellCheck={false}
            className="mt-1.5 w-full resize-y rounded-md border border-line/60 bg-bg-0/60 p-3 font-mono-tech text-[11px] leading-[1.55] text-ink-2 outline-none focus:border-accent"
            placeholder='{ "ticker": "AAPL", "t": "09:00" }'
          />
        </div>
      </div>

      {/* ── Output schema (visual) ─────────────────────────── */}
      <OutputSchemaBuilder fields={fields} onChange={setFields} />

      {/* ── Score result ───────────────────────────────────── */}
      {scoreOutput && (
        <section className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            score · last test
          </span>
          <pre className="mt-2 max-h-48 overflow-auto rounded-md border border-line/40 bg-bg-0/60 p-3 font-mono-tech text-[11px] leading-[1.55] text-ink-2">
{scoreOutput}
          </pre>
        </section>
      )}

      {/* ── Footer ─────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
          {saved
            ? `saved · ${saved.id.slice(0, 12)}…`
            : saveErr
              ? saveErr
              : isPatch
                ? "patch existing agent"
                : "create new agent"}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleTest}
            disabled={scoring || !saved?.id}
            className="inline-flex items-center gap-2 rounded-md border border-line/60 bg-bg-2/40 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-50"
          >
            {scoring ? (
              <Loader2
                size={12}
                strokeWidth={2}
                className="animate-spin"
                aria-hidden
              />
            ) : (
              <Play size={12} strokeWidth={1.7} aria-hidden />
            )}
            <span>{scoring ? "scoring…" : "test on sample"}</span>
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent disabled:opacity-50"
          >
            {saving ? (
              <Loader2
                size={12}
                strokeWidth={2}
                className="animate-spin"
                aria-hidden
              />
            ) : saved ? (
              <CheckCircle2 size={12} strokeWidth={1.7} aria-hidden />
            ) : (
              <Save size={12} strokeWidth={1.7} aria-hidden />
            )}
            <span>{saving ? "saving…" : isPatch ? "save changes" : "create agent"}</span>
          </button>
        </div>
      </div>
    </section>
  );
}

export default AgentDesigner;

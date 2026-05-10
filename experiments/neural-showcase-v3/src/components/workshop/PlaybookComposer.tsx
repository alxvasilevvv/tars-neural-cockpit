// SYNC: claude-w80-fe-only
/**
 * PlaybookComposer — the workshop's centrepiece. Two ways in:
 *
 *   1) "Synthesize from text" — operator pastes 1-3 sentences
 *      describing the process; we POST to /api/playbooks/synthesize
 *      and surface the returned playbook for review.
 *   2) "Pick actions manually" — left rail lists actions per domain
 *      pack (live-fetched via /api/domains + per-pack manifest).
 *      Operator clicks to append to the working steps list.
 *
 * The output is a Playbook JSON visible + editable inline (
 * <pre contenteditable>). Save calls /api/playbooks; if the backend
 * isn't ready (404 / network), we surface the pending banner and
 * keep the JSON locally so nothing is lost.
 */

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, Plus, Save, Sparkles, X, AlertCircle } from "lucide-react";
import { listDomains, type DomainPack, type DomainAction } from "@/lib/api";
import {
  MOCK_PLAYBOOK,
  savePlaybook,
  synthesizePlaybook,
  type Playbook,
  type PlaybookStep,
} from "@/lib/workshop";

interface PlaybookComposerProps {
  initial?: Playbook;
  onSaved?: (pb: Playbook) => void;
}

export function PlaybookComposer({ initial, onSaved }: PlaybookComposerProps) {
  const [packs, setPacks] = useState<DomainPack[] | null>(null);
  const [activePackSlug, setActivePackSlug] = useState<string | null>(null);
  const [seedText, setSeedText] = useState("");
  const [synthesizing, setSynthesizing] = useState(false);
  const [pendingNote, setPendingNote] = useState<string | null>(null);
  const [playbook, setPlaybook] = useState<Playbook>(initial ?? MOCK_PLAYBOOK);
  const [jsonText, setJsonText] = useState<string>(() =>
    JSON.stringify(initial ?? MOCK_PLAYBOOK, null, 2),
  );
  const [jsonErr, setJsonErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const ps = await listDomains();
        setPacks(ps);
        if (ps.length > 0) setActivePackSlug(ps[0].slug);
      } catch {
        // Daemon offline — workshop still renders; left rail stays empty.
        setPacks([]);
      }
    })();
  }, []);

  const activePack = useMemo<DomainPack | null>(
    () => packs?.find((p) => p.slug === activePackSlug) ?? null,
    [packs, activePackSlug],
  );

  // Re-sync editor text whenever playbook is replaced from outside
  // (e.g. fresh synthesize). Internal edits flow the other way via
  // onBlur of the <pre>.
  useEffect(() => {
    setJsonText(JSON.stringify(playbook, null, 2));
    setJsonErr(null);
  }, [playbook]);

  const handleSynthesize = async () => {
    if (!seedText.trim()) return;
    setSynthesizing(true);
    setPendingNote(null);
    try {
      const out = await synthesizePlaybook({
        text: seedText.trim(),
        domain_pack: activePackSlug,
      });
      if (out.pending) {
        setPendingNote(out.reason);
        // Mock-mode: build a stub playbook from the seed text so the
        // operator can keep going without the backend.
        const mock: Playbook = {
          ...MOCK_PLAYBOOK,
          name: seedText.slice(0, 40) || MOCK_PLAYBOOK.name,
          description: seedText,
          domain_pack: activePackSlug,
        };
        setPlaybook(mock);
      } else {
        setPlaybook(out.value.playbook);
      }
    } finally {
      setSynthesizing(false);
    }
  };

  const handleAppendAction = (action: DomainAction) => {
    if (!activePack) return;
    const step: PlaybookStep = {
      id: `s${playbook.steps.length + 1}`,
      domain: activePack.slug,
      action: action.id,
      args: {},
      description: action.description,
    };
    setPlaybook((prev) => ({ ...prev, steps: [...prev.steps, step] }));
  };

  const handleRemoveStep = (id: string) => {
    setPlaybook((prev) => ({
      ...prev,
      steps: prev.steps.filter((s) => s.id !== id),
    }));
  };

  const handleJsonBlur = (e: React.FocusEvent<HTMLPreElement>) => {
    const text = e.currentTarget.innerText;
    try {
      const parsed = JSON.parse(text) as Playbook;
      if (!Array.isArray(parsed.steps)) throw new Error("`steps` must be an array");
      setPlaybook(parsed);
      setJsonErr(null);
    } catch (err) {
      setJsonErr((err as Error).message);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const out = await savePlaybook(playbook);
      if (out.pending) {
        setPendingNote(out.reason);
        // Cache locally so a refresh doesn't blow it away.
        try {
          localStorage.setItem("tars-workshop-playbook-draft", JSON.stringify(playbook));
        } catch {
          /* private mode — fine */
        }
        setSavedAt("draft (local)");
      } else {
        setPlaybook(out.value.playbook);
        setSavedAt(new Date().toLocaleTimeString());
        onSaved?.(out.value.playbook);
      }
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 1, y: 0 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="grid gap-5 md:grid-cols-[260px_1fr]"
    >
      {/* ── Left: action palette ─────────────────────────────────── */}
      <aside className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
        <header className="mb-3 flex items-center justify-between">
          <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3">
            Domain packs
          </span>
        </header>
        {packs === null ? (
          <p className="font-mono-tech text-[10.5px] text-ink-3">loading…</p>
        ) : packs.length === 0 ? (
          <p className="font-mono-tech text-[10.5px] text-ink-3">
            daemon offline · no packs available
          </p>
        ) : (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {packs.map((p) => (
              <button
                key={p.slug}
                type="button"
                onClick={() => setActivePackSlug(p.slug)}
                className={`rounded-md border px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[1.6px] transition-colors ${
                  activePackSlug === p.slug
                    ? "border-accent bg-accent/[0.08] text-ink"
                    : "border-line/60 text-ink-2 hover:border-accent/60"
                }`}
              >
                {p.slug}
              </button>
            ))}
          </div>
        )}

        {activePack ? (
          <ul className="grid gap-1.5">
            {activePack.actions.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => handleAppendAction(a)}
                  className="grid w-full grid-cols-[16px_1fr] items-start gap-2 rounded-md border border-transparent px-2 py-1.5 text-left transition-colors hover:border-line/60 hover:bg-bg-2/60"
                >
                  <Plus
                    size={11}
                    strokeWidth={2}
                    aria-hidden
                    className="mt-1 text-ink-3"
                  />
                  <span className="min-w-0">
                    <span className="block truncate font-display text-[12.5px] text-ink">
                      {a.name}
                    </span>
                    <span className="block truncate font-mono-tech text-[10px] uppercase tracking-[1.4px] text-ink-3">
                      {a.id}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </aside>

      {/* ── Right: synthesize + JSON editor ─────────────────────── */}
      <div className="grid gap-5">
        {/* Synthesize from text */}
        <section className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <header className="mb-2 flex items-center gap-2">
            <Sparkles
              size={12}
              strokeWidth={1.7}
              aria-hidden
              style={{ color: "var(--brand-violet)" }}
            />
            <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-2">
              Synthesize from natural language
            </span>
          </header>
          <textarea
            value={seedText}
            onChange={(e) => setSeedText(e.target.value)}
            placeholder="Every weekday at 9am, fetch portfolio prices, summarize movements, post to Slack #trading."
            rows={3}
            className="w-full resize-y rounded-md border border-line/60 bg-bg-0/50 px-3 py-2 font-mono-tech text-[12px] leading-[1.55] text-ink outline-none placeholder:text-ink-3 focus:border-accent"
          />
          <div className="mt-2 flex items-center justify-between gap-3">
            <span className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
              {activePackSlug ? `pack: ${activePackSlug}` : "no pack selected"}
            </span>
            <button
              type="button"
              disabled={!seedText.trim() || synthesizing}
              onClick={handleSynthesize}
              className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink transition-colors hover:border-accent disabled:opacity-50"
            >
              {synthesizing ? (
                <Loader2 size={11} strokeWidth={2} className="animate-spin" aria-hidden />
              ) : (
                <Sparkles size={11} strokeWidth={1.8} aria-hidden />
              )}
              <span>{synthesizing ? "synthesizing…" : "synthesize"}</span>
            </button>
          </div>
          {pendingNote && (
            <p className="mt-3 inline-flex items-start gap-2 rounded-md border border-amber-400/30 bg-amber-400/[0.06] px-2.5 py-1.5 text-[11px] leading-[1.5] text-amber-200">
              <AlertCircle size={11} strokeWidth={1.7} aria-hidden className="mt-0.5" />
              <span>{pendingNote} Workshop UI works in mock mode.</span>
            </p>
          )}
        </section>

        {/* Step chips (drag-drop ready) */}
        <section className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <header className="mb-2 flex items-center justify-between">
            <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-2">
              Steps · {playbook.steps.length}
            </span>
          </header>
          {playbook.steps.length === 0 ? (
            <p className="font-mono-tech text-[10.5px] text-ink-3">
              add an action from the left or synthesize from text above.
            </p>
          ) : (
            <ol className="grid gap-1.5">
              {playbook.steps.map((s, idx) => (
                <li
                  key={s.id}
                  className="grid grid-cols-[24px_1fr_auto] items-center gap-2 rounded-md border border-line/40 bg-bg-2/40 px-2.5 py-1.5"
                >
                  <span className="font-mono-tech text-[9.5px] text-ink-3">
                    {String(idx + 1).padStart(2, "0")}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate font-display text-[12.5px] text-ink">
                      {s.domain}.{s.action}
                    </span>
                    {s.description && (
                      <span className="block truncate font-mono-tech text-[10px] uppercase tracking-[1.4px] text-ink-3">
                        {s.description}
                      </span>
                    )}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleRemoveStep(s.id)}
                    aria-label={`remove step ${idx + 1}`}
                    className="text-ink-3 transition-colors hover:text-alert"
                  >
                    <X size={12} strokeWidth={2} />
                  </button>
                </li>
              ))}
            </ol>
          )}
        </section>

        {/* Editable JSON */}
        <section className="rounded-[12px] border border-line/60 bg-bg-1/40 p-4">
          <header className="mb-2 flex items-center justify-between">
            <span className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-2">
              Playbook JSON · click to edit
            </span>
            {jsonErr && (
              <span className="font-mono-tech text-[10px] text-rose-300">{jsonErr}</span>
            )}
          </header>
          <pre
            contentEditable
            suppressContentEditableWarning
            spellCheck={false}
            onBlur={handleJsonBlur}
            className="max-h-[320px] overflow-auto rounded-md border border-line/40 bg-bg-0/60 p-3 font-mono-tech text-[11px] leading-[1.55] text-ink-2 outline-none focus:border-accent"
          >
            {jsonText}
          </pre>
        </section>

        {/* Save */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
            {savedAt ? `saved · ${savedAt}` : saveError ? saveError : "unsaved"}
          </span>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || Boolean(jsonErr)}
            className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent disabled:opacity-50"
          >
            {saving ? (
              <Loader2 size={12} strokeWidth={2} className="animate-spin" aria-hidden />
            ) : (
              <Save size={12} strokeWidth={1.7} aria-hidden />
            )}
            <span>{saving ? "saving…" : "save playbook"}</span>
          </button>
        </div>
      </div>
    </motion.div>
  );
}

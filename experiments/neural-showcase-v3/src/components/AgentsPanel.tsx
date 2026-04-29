/**
 * Multi-agent surface (Phase M1).
 *
 * Operator can:
 *   - Mint a new agent bound to a domain pack persona.
 *   - Pause / resume / archive existing agents.
 *   - Queue + run a task; the result lands inline (council-shaped).
 */

import { useCallback, useEffect, useState } from "react";
import {
  Bot,
  CheckCircle2,
  Loader2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  XCircle,
} from "lucide-react";

import { CornerFrame } from "@/components/Glyphs";
import {
  autopilotTickNow,
  cancelTask,
  createAgent,
  listAgentTasks,
  patchAgent,
  queueTask,
  runTask,
  setAutopilot,
  statusBadgeClass,
  useAgents,
  type Agent,
  type AgentTask,
} from "@/lib/agents";

const KNOWN_PACKS: Array<{ slug: string; label: string }> = [
  { slug: "traders", label: "traders" },
  { slug: "business", label: "business" },
  { slug: "science", label: "science" },
  { slug: "mlm", label: "mlm" },
  { slug: "wallet", label: "wallet" },
];

export function AgentsPanel() {
  const { agents, loading, error, refresh } = useAgents();
  const [draftName, setDraftName] = useState("");
  const [draftPack, setDraftPack] = useState("traders");
  const [draftWallet, setDraftWallet] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [taskPrompt, setTaskPrompt] = useState("");
  const [autopilot, setAutopilotState] = useState<Record<string, boolean>>({});

  const loadTasks = useCallback(
    async (agentId: string | null) => {
      if (!agentId) {
        setTasks([]);
        return;
      }
      try {
        const r = await listAgentTasks(agentId);
        setTasks(r.tasks);
      } catch (e) {
        setActionErr((e as Error).message);
      }
    },
    [],
  );

  useEffect(() => {
    void loadTasks(selected);
  }, [selected, loadTasks]);

  const onCreate = async () => {
    const name = draftName.trim();
    if (!name) return;
    setBusy(true);
    setActionErr(null);
    setActionMsg(null);
    try {
      const r = await createAgent({
        name,
        pack_slug: draftPack,
        wallet_address: draftWallet.trim() || undefined,
      });
      setActionMsg(`agent ${r.agent.name} ready`);
      setDraftName("");
      setDraftWallet("");
      await refresh();
      setSelected(r.agent.id);
    } catch (e) {
      setActionErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const togglePause = async (a: Agent) => {
    setBusy(true);
    try {
      const next = a.status === "active" ? "paused" : "active";
      await patchAgent(a.id, { status: next });
      await refresh();
    } catch (e) {
      setActionErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const toggleAutopilot = async (a: Agent) => {
    setBusy(true);
    try {
      const next = !(autopilot[a.id] ?? false);
      await setAutopilot(a.id, next);
      setAutopilotState((prev) => ({ ...prev, [a.id]: next }));
      setActionMsg(next ? `${a.name} → autopilot` : `${a.name} → manual`);
    } catch (e) {
      setActionErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const tickNow = async () => {
    setBusy(true);
    try {
      const r = await autopilotTickNow();
      setActionMsg(
        `autopilot tick · visited ${r.agents_visited} · ran ${r.tasks_run}`,
      );
      await loadTasks(selected);
    } catch (e) {
      setActionErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const archive = async (a: Agent) => {
    setBusy(true);
    try {
      await patchAgent(a.id, { status: "archived" });
      await refresh();
      if (selected === a.id) setSelected(null);
    } catch (e) {
      setActionErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onQueue = async () => {
    if (!selected) return;
    const prompt = taskPrompt.trim();
    if (!prompt) return;
    setBusy(true);
    try {
      const q = await queueTask(selected, prompt);
      setTaskPrompt("");
      setTasks((prev) => [q.task, ...prev]);
      const r = await runTask(q.task.id);
      setTasks((prev) => prev.map((t) => (t.id === r.task.id ? r.task : t)));
    } catch (e) {
      setActionErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onCancel = async (taskId: string) => {
    try {
      const r = await cancelTask(taskId);
      setTasks((prev) => prev.map((t) => (t.id === r.task.id ? r.task : t)));
    } catch (e) {
      setActionErr((e as Error).message);
    }
  };

  const sel = agents.find((a) => a.id === selected) ?? null;

  return (
    <div
      id="agents"
      className="relative rounded-[14px] border border-line bg-bg-1 p-5"
      aria-labelledby="agents-heading"
    >
      <CornerFrame />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-ink-2" aria-hidden />
          <span
            id="agents-heading"
            className="font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2"
          >
            agents · roster
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void tickNow()}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-md border border-emerald-400/30 bg-emerald-400/[0.04] px-2 py-1 font-mono-tech text-[9px] uppercase tracking-[2px] text-emerald-300 hover:bg-emerald-400/[0.08] disabled:opacity-50"
            title="Run one autopilot tick now"
          >
            <Play size={11} strokeWidth={1.6} />
            tick
          </button>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading || busy}
            className="inline-flex items-center gap-1.5 rounded-md border border-line px-2 py-1 font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink disabled:opacity-50"
            title="Refresh agents"
          >
            <RefreshCw
              size={12}
              strokeWidth={1.6}
              className={loading ? "animate-spin" : ""}
            />
            refresh
          </button>
        </div>
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
          aria-label="agent name"
          value={draftName}
          onChange={(e) => setDraftName(e.target.value)}
          placeholder="agent name"
          className="rounded border border-line bg-bg-1 px-2 py-1 font-mono-tech text-[12px] text-ink placeholder:text-ink-2 focus:border-accent focus:outline-none"
        />
        <select
          aria-label="persona pack"
          value={draftPack}
          onChange={(e) => setDraftPack(e.target.value)}
          className="rounded border border-line bg-bg-1 px-2 py-1 font-mono-tech text-[12px] text-ink focus:border-accent focus:outline-none"
        >
          {KNOWN_PACKS.map((p) => (
            <option key={p.slug} value={p.slug}>
              {p.label}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={busy || !draftName.trim()}
          className="inline-flex items-center gap-1.5 rounded border border-accent/40 bg-accent/[0.06] px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-accent hover:bg-accent/10 disabled:opacity-50"
        >
          <Plus size={12} strokeWidth={1.7} />
          mint
        </button>
        <input
          aria-label="optional wallet address binding"
          value={draftWallet}
          onChange={(e) => setDraftWallet(e.target.value)}
          placeholder="wallet address (optional)"
          className="col-span-full rounded border border-line bg-bg-1 px-2 py-1 font-mono-tech text-[11px] text-ink-2 placeholder:text-ink-2/60"
        />
      </form>

      {actionMsg ? (
        <p className="mb-2 inline-flex items-center gap-1 rounded border border-emerald-400/40 bg-emerald-400/[0.06] px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-emerald-300">
          <CheckCircle2 size={11} /> {actionMsg}
        </p>
      ) : null}
      {actionErr ? (
        <p className="mb-2 inline-flex items-center gap-1 rounded border border-alert/40 bg-alert/[0.06] px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-alert">
          <XCircle size={11} /> {actionErr}
        </p>
      ) : null}

      <ul className="space-y-2">
        {agents.length === 0 ? (
          <li className="rounded border border-dashed border-line p-3 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">
            no agents yet — mint one above
          </li>
        ) : (
          agents.map((a) => (
            <li
              key={a.id}
              className={`rounded border p-2 ${
                selected === a.id
                  ? "border-accent/60 bg-accent/[0.04]"
                  : "border-line bg-bg-0"
              }`}
            >
              <button
                type="button"
                onClick={() => setSelected(a.id)}
                className="flex w-full items-center justify-between gap-2 text-left"
              >
                <span className="flex flex-col">
                  <span className="font-mono-tech text-[12.5px] text-ink">
                    {a.name}
                  </span>
                  <span className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2">
                    pack: {a.pack_slug}
                    {a.wallet_address ? (
                      <>
                        {" · "}
                        <span className="text-amber-300">
                          {a.wallet_address.slice(0, 6)}…{a.wallet_address.slice(-4)}
                        </span>
                      </>
                    ) : null}
                  </span>
                </span>
                <span
                  className={`inline-flex items-center rounded-md px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] ring-1 ${statusBadgeClass(
                    a.status,
                  )}`}
                >
                  {a.status}
                </span>
              </button>
              {a.status !== "archived" ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => void togglePause(a)}
                    disabled={busy}
                    className="inline-flex items-center gap-1 rounded border border-line px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink disabled:opacity-50"
                  >
                    {a.status === "active" ? <Pause size={10} /> : <Play size={10} />}
                    {a.status === "active" ? "pause" : "resume"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void toggleAutopilot(a)}
                    disabled={busy || a.status !== "active"}
                    className={`inline-flex items-center gap-1 rounded border px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] disabled:opacity-50 ${
                      autopilot[a.id]
                        ? "border-emerald-400/40 bg-emerald-400/[0.08] text-emerald-300"
                        : "border-line text-ink-2 hover:border-line-strong hover:text-ink"
                    }`}
                  >
                    autopilot {autopilot[a.id] ? "on" : "off"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void archive(a)}
                    disabled={busy}
                    className="inline-flex items-center gap-1 rounded border border-line px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink disabled:opacity-50"
                  >
                    archive
                  </button>
                </div>
              ) : null}
            </li>
          ))
        )}
      </ul>

      {sel ? (
        <div className="mt-5 rounded-md border border-line bg-bg-0 p-3">
          <div className="mb-2 flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-accent" aria-hidden />
            <span className="font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
              tasks · {sel.name}
            </span>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void onQueue();
            }}
            className="mb-3 flex flex-wrap items-center gap-2"
          >
            <input
              value={taskPrompt}
              onChange={(e) => setTaskPrompt(e.target.value)}
              placeholder="give the agent a task…"
              className="min-w-[260px] flex-1 rounded border border-line bg-bg-1 px-2 py-1 font-mono-tech text-[12px] text-ink placeholder:text-ink-2 focus:border-accent focus:outline-none"
            />
            <button
              type="submit"
              disabled={busy || sel.status !== "active" || !taskPrompt.trim()}
              className="inline-flex items-center gap-1.5 rounded border border-accent/40 bg-accent/[0.06] px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-accent hover:bg-accent/10 disabled:opacity-50"
            >
              {busy ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Send size={12} strokeWidth={1.7} />
              )}
              run
            </button>
          </form>

          <ul className="space-y-2">
            {tasks.length === 0 ? (
              <li className="rounded border border-dashed border-line p-2 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2">
                no tasks yet
              </li>
            ) : (
              tasks.map((t) => (
                <li
                  key={t.id}
                  className="rounded border border-line bg-bg-1 p-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono-tech text-[11.5px] text-ink">
                      {t.prompt}
                    </span>
                    <span
                      className={`inline-flex items-center rounded-md px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] ring-1 ${statusBadgeClass(
                        t.status,
                      )}`}
                    >
                      {t.status}
                    </span>
                  </div>
                  {t.error ? (
                    <p className="mt-1 font-mono-tech text-[10.5px] text-alert">
                      {t.error}
                    </p>
                  ) : null}
                  {t.result ? (
                    <p className="mt-1 font-mono-tech text-[11px] text-ink-2">
                      <span className="text-ink">chosen:</span> {t.result.chosen ?? "—"}{" "}
                      ·{" "}
                      <span className="text-ink">agreement:</span>{" "}
                      {t.result.agreement?.toFixed(3) ?? "—"}
                    </p>
                  ) : null}
                  {(t.status === "pending" || t.status === "running") ? (
                    <button
                      type="button"
                      onClick={() => void onCancel(t.id)}
                      className="mt-1 inline-flex items-center gap-1 rounded border border-line px-2 py-[2px] font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink"
                    >
                      cancel
                    </button>
                  ) : null}
                </li>
              ))
            )}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

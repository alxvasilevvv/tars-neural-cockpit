"""Per-thread structured timeline.

Joins together every signal that touched a thread — chat messages,
tool-calls, attachment ingests, voice TTS, usage tokens, council
deliberations, sampler decisions — and returns a single chronological
feed the cockpit can render below the conversation as a "what
happened on this thread" panel.

Sources fanned in:

- ``messages``      → ``message`` rows (role + content preview).
- ``tool_calls``    → ``tool_call`` rows (slug.action + status).
- ``attachments``   → ``attachment.ingested`` rows (filename + chunk count).
- ``meeet events``  → ``event`` rows filtered by session id, trace id,
                      or thread id payload key. Supports ``voice.tts``,
                      ``usage.tokens``, ``council.*``, ``sampler.*``,
                      ``policy.*`` etc.

The fan-in is bounded (``limit`` per source) and merged in-memory by
``ts``. Rows carry a stable ``id`` so the React layer can keep them
keyed across rerenders.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from backend.core.chat.store import ChatStore, get_chat_store
from backend.core.meeet import StoredEvent, get_store as get_meeet_store


_RELEVANT_EVENT_KINDS = (
    "chat.message.received",
    "chat.message.completed",
    "chat.tool_call.proposed",
    "chat.tool_call.completed",
    "chat.tool_call.failed",
    "chat.context.retrieved",
    "attachment.ingested",
    "voice.tts",
    "usage.tokens",
    "council.deliberation.started",
    "council.deliberation.completed",
    "policy.allowed",
    "policy.queued",
    "policy.blocked",
    "policy.confirm",
    "policy.cancelled",
    "policy.expired",
    "sampler.decision",
    "playbook.started",
    "playbook.step.completed",
    "playbook.completed",
    "plan.proposed",
    "planner.approved",
    "planner.rejected",
    "planner.cloned",
    "plan.run.started",
    "plan.step.requested",
    "plan.step.allowed",
    "plan.step.completed",
    "plan.run.usage",
    "plan.completed",
    "plan.aborted",
    "plan.abort.requested",
)


@dataclass(frozen=True)
class ThreadTimelineEntry:
    id: str
    ts: float
    kind: str
    source: str  # 'message' | 'tool_call' | 'attachment' | 'event'
    title: str
    summary: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "kind": self.kind,
            "source": self.source,
            "title": self.title,
            "summary": self.summary,
            "payload": dict(self.payload),
        }


async def get_thread_timeline(
    thread_id: str,
    *,
    limit_per_source: int = 250,
    chat: ChatStore | None = None,
) -> list[ThreadTimelineEntry]:
    chat = chat or get_chat_store()
    if not chat.enabled or not thread_id:
        return []

    messages_task = chat.list_messages(thread_id, limit=limit_per_source)
    rows_task = asyncio.to_thread(_load_thread_extras, chat, thread_id, limit_per_source)
    events_task = _load_thread_events(thread_id, limit_per_source)

    msgs, extras, events = await asyncio.gather(
        messages_task, rows_task, events_task
    )

    out: list[ThreadTimelineEntry] = []
    for m in msgs:
        out.append(_message_to_entry(m))
    for tc in extras["tool_calls"]:
        out.append(_tool_call_to_entry(tc))
    for att in extras["attachments"]:
        out.append(_attachment_to_entry(att))
    for ev in events:
        entry = _event_to_entry(ev)
        if entry is not None:
            out.append(entry)

    out.sort(key=lambda e: e.ts)
    return out


# ---------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------


def _load_thread_extras(
    chat: ChatStore, thread_id: str, limit: int
) -> dict[str, list[dict[str, Any]]]:
    conn = chat._connect()
    try:
        tool_rows = conn.execute(
            """
            SELECT tc.* FROM tool_calls tc
            JOIN messages m ON m.id = tc.message_id
            WHERE m.thread_id = ?
            ORDER BY tc.started_at ASC
            LIMIT ?
            """,
            (thread_id, limit),
        ).fetchall()
        att_rows = conn.execute(
            "SELECT * FROM attachments WHERE thread_id = ? "
            "ORDER BY created_at ASC LIMIT ?",
            (thread_id, limit),
        ).fetchall()
    finally:
        conn.close()
    return {
        "tool_calls": [dict(r) for r in tool_rows],
        "attachments": [dict(r) for r in att_rows],
    }


async def _load_thread_events(
    thread_id: str, limit: int
) -> list[StoredEvent]:
    store = get_meeet_store()
    if not store or not getattr(store, "enabled", False):
        return []
    pool: list[StoredEvent] = []
    for kind in _RELEVANT_EVENT_KINDS:
        try:
            rows = await store.list_events(limit=limit, kind=kind)
        except Exception:
            continue
        for ev in rows:
            payload = _coerce_payload(ev.payload)
            if not isinstance(payload, dict):
                continue
            if str(payload.get("thread_id") or "") != thread_id:
                continue
            pool.append(ev)
        if len(pool) >= limit:
            break
    pool.sort(key=lambda ev: ev.ts)
    return pool[-limit:]


def _coerce_payload(raw) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


# ---------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------


def _message_to_entry(message) -> ThreadTimelineEntry:
    role = message.role
    text = message.content or ""
    summary = text.strip().splitlines()[0][:240] if text.strip() else "(empty)"
    return ThreadTimelineEntry(
        id=f"msg:{message.id}",
        ts=float(message.created_at),
        kind=f"message.{role}",
        source="message",
        title=role,
        summary=summary,
        payload={
            "msg_id": message.id,
            "thread_id": message.thread_id,
            "role": role,
            "trace_id": message.trace_id,
            "voice_model": message.voice_model,
            "cost_usd": message.cost_usd,
            "route": message.route,
            "tokens_in": message.tokens_in,
            "tokens_out": message.tokens_out,
        },
    )


def _tool_call_to_entry(tc: dict[str, Any]) -> ThreadTimelineEntry:
    title = f"{tc.get('slug')}.{tc.get('action_id')}"
    status = tc.get("status") or "pending"
    return ThreadTimelineEntry(
        id=f"tcl:{tc.get('id')}",
        ts=float(tc.get("started_at") or 0.0),
        kind=f"tool_call.{status}",
        source="tool_call",
        title=title,
        summary=(
            f"status={status}" + (f" · err={tc.get('error')}" if tc.get("error") else "")
        ),
        payload=tc,
    )


def _attachment_to_entry(att: dict[str, Any]) -> ThreadTimelineEntry:
    fname = att.get("filename") or att.get("id")
    return ThreadTimelineEntry(
        id=f"att:{att.get('id')}",
        ts=float(att.get("created_at") or 0.0),
        kind="attachment.ingested",
        source="attachment",
        title=str(fname),
        summary=(
            f"{att.get('mime')} · {att.get('bytes_total', 0)} B · "
            f"{att.get('char_count', 0)} chars indexed"
        ),
        payload=att,
    )


def _event_to_entry(ev: StoredEvent) -> ThreadTimelineEntry | None:
    payload = _coerce_payload(ev.payload)
    if not isinstance(payload, dict):
        return None
    title = ev.kind
    summary = _summarise_event(ev.kind, payload)
    return ThreadTimelineEntry(
        id=f"evt:{ev.id}",
        ts=float(ev.ts),
        kind=ev.kind,
        source="event",
        title=title,
        summary=summary,
        payload={
            "trace_id": ev.trace_id,
            "session_id": ev.session_id,
            "route": ev.route,
            **payload,
        },
    )


def _summarise_event(kind: str, payload: dict[str, Any]) -> str:
    if kind == "voice.tts":
        return (
            f"{payload.get('persona', '?')} · "
            f"{payload.get('provider', '?')} · "
            f"{payload.get('chars', 0)} chars · "
            f"${float(payload.get('cost_usd') or 0):.6f}"
        )
    if kind == "usage.tokens":
        return (
            f"{payload.get('model', '?')} · "
            f"in {payload.get('tokens_in', 0)} · "
            f"out {payload.get('tokens_out', 0)} · "
            f"${float(payload.get('cost_usd') or 0):.6f}"
        )
    if kind == "attachment.ingested":
        return (
            f"{payload.get('filename', '?')} · "
            f"{payload.get('chunk_count', 0)} chunks · "
            f"{payload.get('embedding_model', '?')}"
        )
    if kind.startswith("chat.tool_call."):
        return f"{payload.get('slug', '?')}.{payload.get('action_id', '?')}"
    if kind == "chat.context.retrieved":
        files = payload.get("files") or []
        return f"{payload.get('chunk_count', 0)} chunks · " + ", ".join(files[:3])
    if kind.startswith("policy."):
        # Every policy.* event uses ``action`` (not ``action_id``) — the
        # old summariser read the wrong key and the cockpit always
        # rendered ``action=?``. Pin the right field name here.
        slug = payload.get("slug") or "?"
        action = payload.get("action") or "?"
        token = payload.get("token") or "?"
        suffix = f"slug={slug} · action={action} · token={token}"
        if kind == "policy.expired" and payload.get("expired_at"):
            return f"{suffix} · expired_at={payload['expired_at']}"
        return suffix
    if kind == "sampler.decision":
        winner = payload.get("winner") or "?"
        stance = payload.get("winning_stance") or "?"
        agreement = payload.get("agreement", 0)
        cost = float(payload.get("cost_usd") or 0)
        parallel_tag = " · parallel" if payload.get("parallel") else ""
        return (
            f"{winner} → {stance} · agree={agreement} · ${cost:.6f}{parallel_tag}"
        )
    if kind.startswith("council."):
        # ``deliberation.started`` carries voices+topic, ``completed``
        # carries chosen+winner_model+agreement.
        if "voices" in payload:
            return (
                f"voices=[{', '.join(payload.get('voices') or [])}] · "
                f"topic={payload.get('topic') or '?'}"
            )
        return (
            f"chosen={payload.get('chosen') or '?'} · "
            f"winner={payload.get('winner_model') or '?'} · "
            f"agree={payload.get('agreement', 0)}"
        )
    if kind == "playbook.started":
        return (
            f"id={payload.get('playbook_id') or '?'} · "
            f"steps={payload.get('steps') or 0} · "
            f"mode={payload.get('mode') or '?'}"
        )
    if kind == "playbook.step.completed":
        suffix = "ok" if payload.get("ok") else "failed"
        if payload.get("blocked"):
            suffix = "blocked"
        parallel_tag = " · parallel" if payload.get("parallel") else ""
        return (
            f"id={payload.get('playbook_id') or '?'} · "
            f"step={payload.get('step_id') or '?'} · "
            f"{suffix} · {round(float(payload.get('took_ms') or 0), 1)}ms"
            f"{parallel_tag}"
        )
    if kind == "playbook.completed":
        suffix = "ok" if payload.get("ok") else "stopped"
        return (
            f"id={payload.get('playbook_id') or '?'} · "
            f"{suffix} · run={payload.get('steps_run') or 0} · "
            f"blocked={payload.get('steps_blocked') or 0} · "
            f"failed={payload.get('steps_failed') or 0}"
        )
    if kind == "plan.proposed":
        return (
            f"plan={payload.get('plan_id') or '?'} · "
            f"goal={(payload.get('goal') or '?')[:60]} · "
            f"steps={payload.get('step_count') or 0}"
            + (
                f" · destructive={payload['destructive_step_count']}"
                if payload.get("destructive_step_count")
                else ""
            )
        )
    if kind in ("planner.approved", "planner.rejected"):
        verb = "approved" if kind.endswith("approved") else "rejected"
        return (
            f"plan={payload.get('plan_id') or '?'} · {verb} · "
            f"steps={payload.get('step_count') or 0}"
        )
    if kind == "planner.cloned":
        rebind = (
            " · thread-rebind" if payload.get("thread_id_rebind") else ""
        )
        override = " · goal-override" if payload.get("goal_overridden") else ""
        # Tag one-shot reruns so the timeline reads "rerun" instead
        # of "manual approve + run". auto_run implies auto_approve,
        # so we collapse the suffix to a single "rerun" label.
        if payload.get("auto_run"):
            mode_tag = " · rerun"
        elif payload.get("auto_approved"):
            mode_tag = " · auto-approved"
        else:
            mode_tag = ""
        return (
            f"plan={payload.get('plan_id') or '?'} · "
            f"from={payload.get('source_plan_id') or '?'} · "
            f"steps={payload.get('step_count') or 0}"
            f"{rebind}{override}{mode_tag}"
        )
    if kind == "plan.run.started":
        return (
            f"plan={payload.get('plan_id') or '?'} · "
            f"steps={payload.get('step_count') or 0} · "
            f"mode={payload.get('mode') or '?'}"
        )
    if kind == "plan.step.requested":
        parallel_tag = " · parallel" if payload.get("parallel") else ""
        return (
            f"plan={payload.get('plan_id') or '?'} · "
            f"step={payload.get('step_id') or '?'} · "
            f"{payload.get('action') or '?'}"
            f"{parallel_tag}"
        )
    if kind == "plan.step.allowed":
        return (
            f"plan={payload.get('plan_id') or '?'} · "
            f"step={payload.get('step_id') or '?'} · "
            f"{'allowed' if payload.get('allowed') else 'blocked'} · "
            f"reason={payload.get('reason') or '?'}"
        )
    if kind == "plan.step.completed":
        if payload.get("skipped"):
            suffix = "skipped"
        elif payload.get("blocked"):
            suffix = "blocked"
        elif payload.get("ok"):
            suffix = "ok"
        else:
            suffix = "failed"
        parallel_tag = " · parallel" if payload.get("parallel") else ""
        return (
            f"plan={payload.get('plan_id') or '?'} · "
            f"step={payload.get('step_id') or '?'} · "
            f"{suffix} · "
            f"{round(float(payload.get('took_ms') or 0), 1)}ms"
            f"{parallel_tag}"
        )
    if kind == "plan.run.usage":
        usage = payload.get("usage") or {}
        if isinstance(usage, dict):
            calls = usage.get("calls") or 0
            tokens_in = usage.get("tokens_in") or 0
            tokens_out = usage.get("tokens_out") or 0
            cost = usage.get("cost_usd")
            has_priced = bool(usage.get("has_priced_models"))
            cost_str = (
                f"${float(cost):.4f}"
                if has_priced and cost is not None
                else "n/a"
            )
        else:
            calls = tokens_in = tokens_out = 0
            cost_str = "n/a"
        return (
            f"plan={payload.get('plan_id') or '?'} · "
            f"status={payload.get('status') or '?'} · "
            f"calls={calls} · tokens={tokens_in}+{tokens_out} · "
            f"cost={cost_str}"
        )
    if kind == "plan.completed":
        return (
            f"plan={payload.get('plan_id') or '?'} · ok · "
            f"run={payload.get('steps_run') or 0} · "
            f"blocked={payload.get('steps_blocked') or 0} · "
            f"failed={payload.get('steps_failed') or 0}"
        )
    if kind == "plan.aborted":
        return (
            f"plan={payload.get('plan_id') or '?'} · "
            f"reason={payload.get('reason') or '?'} · "
            f"run={payload.get('steps_run') or 0} · "
            f"blocked={payload.get('steps_blocked') or 0} · "
            f"failed={payload.get('steps_failed') or 0}"
        )
    if kind == "plan.abort.requested":
        return (
            f"plan={payload.get('plan_id') or '?'} · "
            f"flipped={'yes' if payload.get('ok') else 'no'}"
        )
    return ""

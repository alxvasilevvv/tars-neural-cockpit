"""W248 — Unified WebSocket real-time event bus.

Single endpoint ``WS /api/realtime`` replaces the per-feature polling
loops the cockpit used to drive (``/api/health`` @ 5 s,
``/api/usage/cap_status`` @ 60 s, ``/api/bg_agents`` @ 4 s,
``/api/privacy/data_plane`` @ 5 s, …). The client subscribes once and
the server pushes :class:`backend.core.realtime.EventEnvelope` frames
on every topic of interest.

Topics (curated list — keep in sync with the frontend handlers):

    - ``health``                — backend liveness + uptime
    - ``usage``                 — each ``UsageEvent`` records
    - ``cap_status``            — threshold crossings on the spend cap
    - ``bg_agents``             — bg task state changes
    - ``privacy.data_plane``    — every ``check_can_call`` decision
    - ``agents.frame``          — orchestrator step frames (cowork glue)
    - ``connectors.status``     — slack / gmail / calendar liveness
    - ``doctor.status``         — tars-doctor drift signals

Client → server messages (JSON over the WS):

    {"op": "subscribe",   "topics": ["health", "usage"]}
    {"op": "unsubscribe", "topics": ["usage"]}
    {"op": "snapshot",    "topic":  "cap_status"}
    {"op": "ping"}

Server → client messages — always an :class:`EventEnvelope` dict::

    {"type": "<topic>", "ts": 1715800000.123, "payload": { ... }}

Plus synthetic envelopes:

    {"type": "heartbeat",   "ts": ..., "payload": {}}
    {"type": "subscribed",  "ts": ..., "payload": {"topics": [...]}}
    {"type": "snapshot_miss","ts": ..., "payload": {"topic": "..."}}
    {"type": "error",       "ts": ..., "payload": {"reason": "..."}}

Reconnects: the client should set ``onclose`` → schedule reconnect
with exponential back-off; the server holds no per-client state so
reconnecting is free.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.realtime import (
    EventEnvelope,
    snapshot,
    subscribe,
)


log = logging.getLogger("tars.realtime")

router = APIRouter(tags=["realtime"])


# Curated topic list. The server doesn't reject "unknown" topics on
# subscribe (publishers can register new ones at runtime), but this
# list drives the discovery endpoint + the frontend default subscribe.
KNOWN_TOPICS: tuple[str, ...] = (
    "health",
    "usage",
    "cap_status",
    "bg_agents",
    "privacy.data_plane",
    "agents.frame",
    "connectors.status",
    "doctor.status",
)


HEARTBEAT_INTERVAL_S = 15.0


@router.get("/api/realtime/topics")
async def list_topics() -> dict[str, Any]:
    """Discovery — clients fetch this once to learn the topic list."""

    return {
        "ok": True,
        "topics": list(KNOWN_TOPICS),
        "heartbeat_interval_s": HEARTBEAT_INTERVAL_S,
    }


def _envelope(type_: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"type": type_, "ts": time.time(), "payload": payload or {}}


async def _drain_topic(
    topic: str,
    ws: WebSocket,
    cancel_evt: asyncio.Event,
) -> None:
    """One task per subscribed topic. Pumps the topic iterator into ws.send_json."""

    try:
        async for env in subscribe(topic):
            if cancel_evt.is_set():
                return
            try:
                await ws.send_json(env.to_dict())
            except Exception:
                cancel_evt.set()
                return
    except asyncio.CancelledError:
        return
    except Exception as exc:  # noqa: BLE001
        log.debug("realtime.drain(%s) failed: %s", topic, exc)


@router.websocket("/api/realtime")
async def realtime_ws(ws: WebSocket) -> None:
    """Unified WS endpoint — see module docstring for the protocol."""

    await ws.accept()
    subs: dict[str, asyncio.Task] = {}
    cancel_evt = asyncio.Event()
    last_seen = time.time()

    async def _attach(topic: str) -> None:
        if topic in subs:
            return
        # Send the cached envelope (if any) right away so the client
        # has immediate state without waiting for the next push.
        env = await snapshot(topic)
        if env is not None:
            try:
                await ws.send_json(env.to_dict())
            except Exception:
                cancel_evt.set()
                return
        task = asyncio.create_task(_drain_topic(topic, ws, cancel_evt))
        subs[topic] = task

    async def _detach(topic: str) -> None:
        task = subs.pop(topic, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except Exception:
                pass

    async def _heartbeat_loop() -> None:
        while not cancel_evt.is_set():
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                # Bail if client hasn't sent anything in a long time —
                # but the WS protocol's own ping/pong covers idle
                # connection death; this is just app-level keepalive.
                await ws.send_json(_envelope("heartbeat"))
            except Exception:
                cancel_evt.set()
                return

    hb_task = asyncio.create_task(_heartbeat_loop())

    try:
        # Greet the client so it knows the connection is live and the
        # protocol version is one it recognises.
        await ws.send_json(_envelope("hello", {
            "topics": list(KNOWN_TOPICS),
            "heartbeat_interval_s": HEARTBEAT_INTERVAL_S,
            "protocol": "tars.realtime.v1",
        }))

        while True:
            raw = await ws.receive_text()
            last_seen = time.time()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json(_envelope("error", {"reason": "invalid_json"}))
                continue
            if not isinstance(msg, dict):
                await ws.send_json(_envelope("error", {"reason": "expected_object"}))
                continue
            op = str(msg.get("op") or "").lower()

            if op == "subscribe":
                topics = msg.get("topics") or []
                if not isinstance(topics, list):
                    await ws.send_json(_envelope("error", {"reason": "topics_must_be_list"}))
                    continue
                added: list[str] = []
                for t in topics:
                    if not isinstance(t, str) or not t.strip():
                        continue
                    await _attach(t.strip())
                    added.append(t.strip())
                await ws.send_json(_envelope("subscribed", {"topics": added}))

            elif op == "unsubscribe":
                topics = msg.get("topics") or []
                if not isinstance(topics, list):
                    await ws.send_json(_envelope("error", {"reason": "topics_must_be_list"}))
                    continue
                removed: list[str] = []
                for t in topics:
                    if not isinstance(t, str):
                        continue
                    await _detach(t.strip())
                    removed.append(t.strip())
                await ws.send_json(_envelope("unsubscribed", {"topics": removed}))

            elif op == "snapshot":
                topic = str(msg.get("topic") or "").strip()
                if not topic:
                    await ws.send_json(_envelope("error", {"reason": "missing_topic"}))
                    continue
                env = await snapshot(topic)
                if env is None:
                    await ws.send_json(_envelope("snapshot_miss", {"topic": topic}))
                else:
                    await ws.send_json(env.to_dict())

            elif op == "ping":
                await ws.send_json(_envelope("pong"))

            else:
                await ws.send_json(_envelope("error", {"reason": f"unknown_op:{op}"}))

    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        log.debug("realtime ws loop exit: %s", exc)
    finally:
        cancel_evt.set()
        for topic, task in list(subs.items()):
            task.cancel()
        hb_task.cancel()
        for task in list(subs.values()) + [hb_task]:
            try:
                await task
            except Exception:
                pass
        try:
            await ws.close()
        except Exception:
            pass
        _ = last_seen  # noqa: F841 — kept for future idle-eviction

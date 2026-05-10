"""Async subprocess-stdio transport for the MCP client.

Spawns the remote MCP server via ``asyncio.create_subprocess_exec``,
writes line-delimited JSON-RPC requests to its stdin, reads
line-delimited JSON-RPC responses from its stdout, and
streams the server's stderr to a callable so the operator
can see remote logs.

A background reader task continuously parses incoming lines
and dispatches them to either ``pending_requests`` (when the
``id`` matches an in-flight request) or ``notifications``
(when the message has no ``id`` or matches an unknown id).

The transport is intentionally MCP-agnostic — it speaks
JSON-RPC 2.0, period. The ``ClientSession`` builds MCP
semantics on top.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


log = logging.getLogger(__name__)


@dataclass
class StdioTransport:
    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] | None = None
    cwd: str | None = None

    on_stderr: Callable[[str], None] | None = None

    _proc: asyncio.subprocess.Process | None = field(default=None, init=False)
    _next_id: int = field(default=0, init=False)
    _pending: dict[int, asyncio.Future[Any]] = field(default_factory=dict, init=False)
    _notifications: list[dict[str, Any]] = field(default_factory=list, init=False)
    _stdout_task: asyncio.Task | None = field(default=None, init=False)
    _stderr_task: asyncio.Task | None = field(default=None, init=False)
    _closed: bool = field(default=False, init=False)
    _write_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def start(self) -> None:
        if self._proc is not None:
            raise RuntimeError("transport already started")

        merged_env = os.environ.copy()
        if self.env:
            merged_env.update(self.env)

        self._proc = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
            cwd=self.cwd,
        )
        self._stdout_task = asyncio.create_task(self._read_stdout_loop())
        self._stderr_task = asyncio.create_task(self._read_stderr_loop())
        log.info(
            "mcp.client.transport.started cmd=%s pid=%s",
            self.command,
            self._proc.pid,
        )

    async def close(self) -> int:
        if self._closed:
            return self._proc.returncode if self._proc else 0
        self._closed = True

        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(
                    ConnectionError("MCP transport closed before reply")
                )
        self._pending.clear()

        if self._proc is None:
            return 0

        if self._proc.stdin and not self._proc.stdin.is_closing():
            try:
                self._proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass

        try:
            rc = await asyncio.wait_for(self._proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            log.warning(
                "mcp.client.transport.kill: server did not exit within 5s, "
                "sending SIGTERM"
            )
            self._proc.terminate()
            try:
                rc = await asyncio.wait_for(self._proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self._proc.kill()
                rc = await self._proc.wait()

        for task in (self._stdout_task, self._stderr_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass

        log.info("mcp.client.transport.closed rc=%s", rc)
        return rc

    async def __aenter__(self) -> "StdioTransport":
        await self.start()
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.close()

    async def request(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        timeout: float = 30.0,
    ) -> Any:
        """Send a JSON-RPC request, await the matching response.
        Returns the ``result`` field on success; raises on RPC
        error or timeout."""

        if self._proc is None or self._closed:
            raise ConnectionError("MCP transport not running")

        rid = self._next_id
        self._next_id += 1

        body = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            body["params"] = dict(params)

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._pending[rid] = fut

        await self._write_line(json.dumps(body))

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(rid, None)
            raise TimeoutError(
                f"MCP request {method!r} timed out after {timeout:.1f}s"
            ) from None

    async def notify(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
    ) -> None:
        """Send a JSON-RPC notification (no id, no reply expected)."""

        if self._proc is None or self._closed:
            raise ConnectionError("MCP transport not running")
        body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = dict(params)
        await self._write_line(json.dumps(body))

    async def _write_line(self, text: str) -> None:
        assert self._proc is not None
        async with self._write_lock:
            stdin = self._proc.stdin
            if stdin is None:
                raise ConnectionError("MCP transport stdin is closed")
            stdin.write((text + "\n").encode("utf-8"))
            await stdin.drain()

    async def _read_stdout_loop(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        stream = self._proc.stdout
        while True:
            line_bytes = await stream.readline()
            if not line_bytes:
                self._fail_pending(
                    ConnectionError("MCP server closed stdout (EOF)")
                )
                return
            line = line_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue
            try:
                body = json.loads(line)
            except json.JSONDecodeError:
                log.warning("mcp.client.transport.recv.bad_json: %r", line)
                continue
            self._dispatch(body)

    def _dispatch(self, body: Mapping[str, Any]) -> None:
        rid = body.get("id")
        if rid is None or rid not in self._pending:
            self._notifications.append(dict(body))
            return
        fut = self._pending.pop(rid)
        if fut.done():
            return
        if "error" in body and body["error"] is not None:
            err = body["error"]
            fut.set_exception(
                RemoteRpcError(
                    code=int(err.get("code", -32603)),
                    message=str(err.get("message", "remote error")),
                    data=err.get("data"),
                )
            )
        else:
            fut.set_result(body.get("result"))

    def _fail_pending(self, exc: BaseException) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()

    async def _read_stderr_loop(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        stream = self._proc.stderr
        while True:
            line_bytes = await stream.readline()
            if not line_bytes:
                return
            line = line_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
            if self.on_stderr:
                try:
                    self.on_stderr(line)
                except Exception:  # noqa: BLE001
                    log.debug("mcp.client.transport.on_stderr_callback_failed")
            else:
                log.info("mcp.server.stderr: %s", line)

    def drain_notifications(self) -> list[dict[str, Any]]:
        """Pop and return all queued notifications. Useful for
        tests + operators inspecting server log notifications."""

        out = list(self._notifications)
        self._notifications.clear()
        return out


class RemoteRpcError(Exception):
    """Raised when the remote MCP server returns a JSON-RPC error
    envelope. The transport caller should catch this if they want
    to differentiate transport errors from remote-app errors."""

    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.data = data

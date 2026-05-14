"""W258 — macOS launchd plist management for managed background agents.

Every managed agent is a separate launchd LaunchAgent with a
stable label of the shape ``world.meeet.tars.agent.<id>``. The
plist lives in ``~/Library/LaunchAgents/`` and is loaded via
``launchctl bootstrap gui/<uid>``.

Public surface (all kw-only, all sync):

  - :func:`register`     — write plist + bootstrap
  - :func:`unregister`   — bootout + remove plist
  - :func:`status`       — parse ``launchctl list <label>``
  - :func:`list_managed` — scan the plist dir for our prefix
  - :func:`tail_logs`    — read the trailing N lines of out/err logs

Design notes:

  * Each agent gets its own ``StandardOutPath`` /
    ``StandardErrorPath`` under
    ``~/.tars/bg_agents/logs/<id>.{out,err}.log``.
  * ``schedule`` is parsed as a 5-field cron expression and emitted
    as ``StartCalendarInterval``. If it's omitted we fall back to
    ``RunAtLoad`` + optional ``KeepAlive``.
  * Everything degrades on non-Darwin (no ``launchctl``, no
    ``os.getuid``) — callers get a structured error rather than an
    exception.
  * Plist XML is rendered inline (no on-disk template file) so the
    daemon and the HTTP router don't depend on a co-located
    resource — matters for pyinstaller / Tauri sidecar builds.

We deliberately mirror :mod:`backend.core.daemon.launchd` patterns
(``_launchctl`` wrapper, ``bootout`` before ``bootstrap``,
``dry_run`` flag) so an operator who's already learned one knows
the other.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


AGENT_LABEL_PREFIX = "world.meeet.tars.agent."
DEFAULT_AGENT_PLIST_DIR = Path.home() / "Library" / "LaunchAgents"
LOG_DIR = Path.home() / ".tars" / "bg_agents" / "logs"

# Reject anything that wouldn't make a clean launchd label.
_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")


def is_supported() -> bool:
    """Return True iff the current platform has ``launchctl``."""

    return sys.platform == "darwin"


# ---------- spec --------------------------------------------------------------


@dataclass
class AgentSpec:
    """The minimal payload the renderer needs.

    ``command`` is a list of argv (e.g. ``["/usr/bin/python3", "-m",
    "my_pkg"]``). Using argv (not a shell string) avoids ``sh -c``
    quoting bugs and matches what ``ProgramArguments`` expects.

    ``schedule`` is a 5-field cron-ish string ``"min hr dom mon dow"``;
    ``*`` means any value. Only single-value fields are supported in
    v0.1 — lists/ranges/steps fall back to RunAtLoad.

    ``env`` is a plain ``dict[str, str]`` that becomes
    ``EnvironmentVariables`` in the plist.

    ``keep_alive`` toggles the ``KeepAlive`` block. When ``True`` we
    emit the same "restart on crash, not on clean exit" shape as the
    main daemon plist.
    """

    id: str
    command: list[str]
    schedule: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    run_at_load: bool = True
    keep_alive: bool = False
    working_directory: str | None = None

    def label(self) -> str:
        return f"{AGENT_LABEL_PREFIX}{self.id}"

    def out_log(self) -> Path:
        return LOG_DIR / f"{self.id}.out.log"

    def err_log(self) -> Path:
        return LOG_DIR / f"{self.id}.err.log"


# ---------- plist render ------------------------------------------------------


_PLIST_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    '<plist version="1.0">\n'
    "<dict>\n"
)
_PLIST_FOOTER = "</dict>\n</plist>\n"


def _xml_escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _parse_cron(expr: str) -> dict[str, int] | None:
    """Translate a tiny ``min hr dom mon dow`` subset to a
    StartCalendarInterval dict.

    Returns ``None`` if we can't represent the expression (lists,
    ranges, steps, or malformed input) — the caller falls back to
    RunAtLoad.
    """

    parts = (expr or "").strip().split()
    if len(parts) != 5:
        return None
    keys = ["Minute", "Hour", "Day", "Month", "Weekday"]
    out: dict[str, int] = {}
    for key, raw in zip(keys, parts):
        if raw == "*":
            continue
        # Reject anything fancy — keep v0.1 honest.
        if any(c in raw for c in ",-/"):
            return None
        try:
            out[key] = int(raw)
        except ValueError:
            return None
    return out


def render_agent_plist(spec: AgentSpec) -> str:
    """Build the plist XML for a managed agent.

    The shape matches the daemon plist (Background ProcessType,
    ThrottleInterval=30) so launchd treats them consistently.
    """

    lines: list[str] = [_PLIST_HEADER]
    lines.append(
        f"    <key>Label</key>\n    <string>{_xml_escape(spec.label())}</string>\n"
    )

    # ProgramArguments
    lines.append("    <key>ProgramArguments</key>\n    <array>\n")
    for arg in spec.command:
        lines.append(f"        <string>{_xml_escape(arg)}</string>\n")
    lines.append("    </array>\n")

    if spec.working_directory:
        lines.append(
            f"    <key>WorkingDirectory</key>\n"
            f"    <string>{_xml_escape(spec.working_directory)}</string>\n"
        )

    # EnvironmentVariables
    if spec.env:
        lines.append("    <key>EnvironmentVariables</key>\n    <dict>\n")
        for k, v in sorted(spec.env.items()):
            lines.append(
                f"        <key>{_xml_escape(k)}</key>\n"
                f"        <string>{_xml_escape(str(v))}</string>\n"
            )
        lines.append("    </dict>\n")

    # Schedule vs RunAtLoad. If schedule parses cleanly we emit
    # StartCalendarInterval. Otherwise honour run_at_load.
    cal = _parse_cron(spec.schedule) if spec.schedule else None
    if cal:
        lines.append("    <key>StartCalendarInterval</key>\n    <dict>\n")
        for k in ("Minute", "Hour", "Day", "Month", "Weekday"):
            if k in cal:
                lines.append(
                    f"        <key>{k}</key>\n"
                    f"        <integer>{cal[k]}</integer>\n"
                )
        lines.append("    </dict>\n")
    if spec.run_at_load and not cal:
        lines.append("    <key>RunAtLoad</key>\n    <true/>\n")

    # KeepAlive
    if spec.keep_alive:
        lines.append(
            "    <key>KeepAlive</key>\n    <dict>\n"
            "        <key>SuccessfulExit</key>\n        <false/>\n"
            "        <key>Crashed</key>\n        <true/>\n"
            "    </dict>\n"
        )

    # Log paths
    lines.append(
        f"    <key>StandardOutPath</key>\n"
        f"    <string>{_xml_escape(str(spec.out_log()))}</string>\n"
        f"    <key>StandardErrorPath</key>\n"
        f"    <string>{_xml_escape(str(spec.err_log()))}</string>\n"
    )

    # Throttle so a crash-looper doesn't hammer the user's machine.
    lines.append("    <key>ThrottleInterval</key>\n    <integer>30</integer>\n")
    lines.append("    <key>ProcessType</key>\n    <string>Background</string>\n")

    lines.append(_PLIST_FOOTER)
    return "".join(lines)


# ---------- launchctl helpers -------------------------------------------------


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["launchctl", *args],
        capture_output=True,
        text=True,
    )


def _validate_id(agent_id: str) -> None:
    if not _ID_RE.match(agent_id or ""):
        raise ValueError(f"invalid agent_id: {agent_id!r}")


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _plist_path(agent_id: str, plist_dir: Path | None = None) -> Path:
    base = (plist_dir or DEFAULT_AGENT_PLIST_DIR).expanduser()
    return base / f"{AGENT_LABEL_PREFIX}{agent_id}.plist"


# ---------- public API --------------------------------------------------------


def register(
    *,
    agent_id: str,
    command: list[str],
    schedule: str | None = None,
    env: dict[str, str] | None = None,
    keep_alive: bool = False,
    run_at_load: bool = True,
    working_directory: str | None = None,
    plist_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Register (or replace) a managed agent's launchd plist.

    Returns a dict suitable for direct JSON-serialisation by the
    HTTP router. Errors surface as ``{"ok": False, "error": ...}``;
    we never raise from the happy path.
    """

    _validate_id(agent_id)
    if not command or not isinstance(command, list):
        return {"ok": False, "error": "command_required"}

    spec = AgentSpec(
        id=agent_id,
        command=[str(x) for x in command],
        schedule=schedule,
        env=dict(env or {}),
        run_at_load=bool(run_at_load),
        keep_alive=bool(keep_alive),
        working_directory=working_directory,
    )
    xml = render_agent_plist(spec)
    target = _plist_path(agent_id, plist_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    _ensure_log_dir()

    pre_existed = target.exists()
    target.write_text(xml)

    result: dict[str, Any] = {
        "ok": True,
        "label": spec.label(),
        "plist_path": str(target),
        "action": "updated" if pre_existed else "installed",
        "out_log": str(spec.out_log()),
        "err_log": str(spec.err_log()),
        "dry_run": dry_run,
    }

    if dry_run:
        return result

    if not is_supported():
        result["ok"] = False
        result["error"] = "launchd_not_supported_on_platform"
        return result

    try:
        uid = os.getuid()  # type: ignore[attr-defined]
    except AttributeError:
        result["ok"] = False
        result["error"] = "launchd_not_supported_on_platform"
        return result

    # Idempotent: bootout existing copy (may not be loaded) then bootstrap.
    try:
        _launchctl("bootout", f"gui/{uid}/{spec.label()}")
    except FileNotFoundError:
        result["ok"] = False
        result["error"] = "launchctl_not_found"
        return result

    proc = _launchctl("bootstrap", f"gui/{uid}", str(target))
    result["bootstrap_rc"] = proc.returncode
    if proc.returncode != 0:
        result["ok"] = False
        result["bootstrap_stderr"] = (proc.stderr or "").strip()
    return result


def unregister(
    *,
    agent_id: str,
    plist_dir: Path | None = None,
    keep_file: bool = False,
) -> dict[str, Any]:
    """Bootout + (optionally) delete the plist file."""

    _validate_id(agent_id)
    target = _plist_path(agent_id, plist_dir)
    label = f"{AGENT_LABEL_PREFIX}{agent_id}"

    result: dict[str, Any] = {
        "ok": True,
        "label": label,
        "plist_path": str(target),
    }

    if is_supported():
        try:
            uid = os.getuid()  # type: ignore[attr-defined]
            proc = _launchctl("bootout", f"gui/{uid}/{label}")
            result["bootout_rc"] = proc.returncode
            if proc.returncode != 0 and "Could not find" not in (proc.stderr or ""):
                result["bootout_stderr"] = (proc.stderr or "").strip()
        except (AttributeError, FileNotFoundError):
            # Pure file cleanup still proceeds.
            result["bootout_skipped"] = True
    else:
        result["bootout_skipped"] = True

    if not keep_file and target.exists():
        try:
            target.unlink()
            result["removed_plist"] = True
        except OSError as exc:
            result["ok"] = False
            result["error"] = f"unlink_failed: {exc}"

    return result


def status(*, agent_id: str) -> dict[str, Any]:
    """Run ``launchctl list <label>`` and return parsed status.

    Returned shape:

        {
            "label": "world.meeet.tars.agent.<id>",
            "installed": bool,
            "loaded": bool,
            "pid": int | None,
            "last_exit": int | None,
            "error": str (only on failures),
        }
    """

    _validate_id(agent_id)
    label = f"{AGENT_LABEL_PREFIX}{agent_id}"
    target = _plist_path(agent_id)
    out: dict[str, Any] = {
        "label": label,
        "agent_id": agent_id,
        "plist_path": str(target),
        "installed": target.exists(),
        "loaded": False,
        "pid": None,
        "last_exit": None,
    }

    if not is_supported():
        out["error"] = "launchd_not_supported_on_platform"
        return out

    try:
        proc = _launchctl("list", label)
    except FileNotFoundError:
        out["error"] = "launchctl_not_found"
        return out

    if proc.returncode != 0:
        # Not loaded — that's fine, return the installed-but-not-loaded shape.
        return out

    out["loaded"] = True
    for raw in (proc.stdout or "").splitlines():
        line = raw.strip()
        if line.startswith('"PID" ='):
            tail = line.split("=", 1)[1].strip().rstrip(";").strip()
            try:
                out["pid"] = int(tail)
            except ValueError:
                pass
        elif line.startswith('"LastExitStatus" ='):
            tail = line.split("=", 1)[1].strip().rstrip(";").strip()
            try:
                out["last_exit"] = int(tail)
            except ValueError:
                pass
    return out


def list_managed(*, plist_dir: Path | None = None) -> list[dict[str, Any]]:
    """Scan the plist dir for our prefix and return one row per agent.

    Each row carries the parsed status so the cockpit can render in
    one shot. We never raise — missing dir → empty list.
    """

    base = (plist_dir or DEFAULT_AGENT_PLIST_DIR).expanduser()
    if not base.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(base.glob(f"{AGENT_LABEL_PREFIX}*.plist")):
        agent_id = path.stem[len(AGENT_LABEL_PREFIX):]
        if not _ID_RE.match(agent_id):
            continue
        st = status(agent_id=agent_id)
        st["plist_path"] = str(path)
        rows.append(st)
    return rows


def tail_logs(*, agent_id: str, tail: int = 200) -> dict[str, Any]:
    """Return the trailing ``tail`` lines of out/err logs.

    Missing files become empty strings (not errors) so a freshly-
    registered agent that hasn't written anything yet still renders.
    """

    _validate_id(agent_id)
    tail = max(1, min(int(tail), 5000))
    out_path = LOG_DIR / f"{agent_id}.out.log"
    err_path = LOG_DIR / f"{agent_id}.err.log"

    def _tail(p: Path) -> str:
        if not p.exists():
            return ""
        try:
            with open(p, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                # ~512 bytes per line is generous for log lines.
                chunk = min(size, max(tail * 512, 4096))
                fh.seek(size - chunk, os.SEEK_SET)
                data = fh.read().decode("utf-8", errors="replace")
        except OSError as exc:
            return f"<read_error: {exc}>"
        lines = data.splitlines()
        return "\n".join(lines[-tail:])

    return {
        "agent_id": agent_id,
        "out": _tail(out_path),
        "err": _tail(err_path),
        "out_path": str(out_path),
        "err_path": str(err_path),
    }


# ---------- conveniences ------------------------------------------------------


def to_json(obj: Any) -> str:
    """Test helper — round-trip a result dict through JSON."""

    return json.dumps(obj, sort_keys=True, default=str)

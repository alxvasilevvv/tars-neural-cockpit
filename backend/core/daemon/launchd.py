"""macOS launchd LaunchAgent helpers — render, install, uninstall.

A LaunchAgent (vs LaunchDaemon) runs in the user's session, which
is the correct shape for TARS: the daemon needs the operator's
``$HOME``, vault keys, browser cookies, and meeet.world token —
none of which exist in the system daemon context.

Plist canonical layout:

  ~/Library/LaunchAgents/com.tars.background.plist

We use ``launchctl bootstrap gui/<uid>`` to load (the macOS 11+
replacement for ``launchctl load -w``) and ``bootout`` to unload.
Both commands are idempotent at the launchd level — re-running is
safe.

The renderer accepts a ``payload`` dict and substitutes into a
fixed template. We deliberately don't read from disk — the
template lives inline so the daemon can install itself without a
co-located resource file (matters for pyinstaller / Tauri sidecar
builds).
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PLIST_LABEL = "com.tars.background"
PLIST_FILENAME = f"{PLIST_LABEL}.plist"
DEFAULT_PLIST_DIR = Path.home() / "Library" / "LaunchAgents"


_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>-m</string>
        <string>backend.core.daemon</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{cwd}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>{cwd}</string>
        <key>TARS_DAEMON_FORCE</key>
        <string>{force}</string>
{extra_env}
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{err_path}</string>
    <key>ThrottleInterval</key>
    <integer>30</integer>
    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
"""


@dataclass
class PlistConfig:
    """Inputs the template renderer needs."""

    label: str = PLIST_LABEL
    python: str = ""
    cwd: str = ""
    force_daemon: bool = True
    extra_env: dict[str, str] | None = None
    log_path: str = ""
    err_path: str = ""

    def resolve_defaults(self) -> "PlistConfig":
        """Fill in any unset fields with sensible local defaults."""

        if not self.python:
            self.python = sys.executable
        if not self.cwd:
            # The repo root is two parents above this file
            # (backend/core/daemon/launchd.py).
            self.cwd = str(Path(__file__).resolve().parents[3])
        if not self.log_path:
            self.log_path = str(Path.home() / ".tars" / "daemon.out.log")
        if not self.err_path:
            self.err_path = str(Path.home() / ".tars" / "daemon.err.log")
        return self


def render_plist(config: PlistConfig | None = None) -> str:
    """Build the plist XML string for the given config."""

    cfg = (config or PlistConfig()).resolve_defaults()

    # Extra env entries — each is one <key>/<string> pair.
    extra_env_lines: list[str] = []
    for k, v in (cfg.extra_env or {}).items():
        # XML escape the value (very lightweight — launchd accepts
        # &amp; and friends but we shouldn't see them in env values).
        sv = (
            str(v)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        extra_env_lines.append(f"        <key>{k}</key>\n        <string>{sv}</string>")
    extra_env_block = "\n".join(extra_env_lines)
    if extra_env_block:
        extra_env_block += "\n"

    return _PLIST_TEMPLATE.format(
        label=cfg.label,
        python=cfg.python,
        cwd=cfg.cwd,
        force="1" if cfg.force_daemon else "0",
        extra_env=extra_env_block,
        log_path=cfg.log_path,
        err_path=cfg.err_path,
    )


# ---------- install / uninstall ---------------------------------------


def _launchctl(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Thin wrapper around the ``launchctl`` shell tool.

    On non-Darwin platforms the binary is missing — we let the
    FileNotFoundError propagate so install_plist returns an
    informative error rather than silently no-op'ing.
    """

    return subprocess.run(
        ["launchctl", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def install_plist(
    config: PlistConfig | None = None,
    *,
    plist_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write the plist + optionally ``bootstrap`` it via launchctl.

    Returns ``{ok, plist_path, action, bootstrap_rc?, bootstrap_stderr?}``.

    ``dry_run=True`` writes the plist file but skips the
    ``launchctl bootstrap`` step. Useful for tests and for letting
    operators inspect the plist before activating it.
    """

    cfg = (config or PlistConfig()).resolve_defaults()
    xml = render_plist(cfg)
    target_dir = (plist_dir or DEFAULT_PLIST_DIR).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / PLIST_FILENAME

    pre_existed = target.exists()
    target.write_text(xml)

    result: dict[str, Any] = {
        "ok": True,
        "plist_path": str(target),
        "action": "updated" if pre_existed else "installed",
        "dry_run": dry_run,
    }

    if dry_run:
        return result

    # First, try to bootout an existing instance so we always boot a
    # fresh copy of the updated plist. Failure is fine — it just
    # means the agent wasn't loaded.
    try:
        uid = os.getuid()
    except AttributeError:  # Windows
        result["ok"] = False
        result["error"] = "launchd_not_supported_on_platform"
        return result

    try:
        _launchctl("bootout", f"gui/{uid}/{cfg.label}")
    except FileNotFoundError:
        result["ok"] = False
        result["error"] = "launchctl_not_found"
        return result
    except subprocess.CalledProcessError:
        # bootout-of-not-loaded returns non-zero — fine.
        pass

    proc = _launchctl("bootstrap", f"gui/{uid}", str(target))
    result["bootstrap_rc"] = proc.returncode
    if proc.returncode != 0:
        result["ok"] = False
        result["bootstrap_stderr"] = proc.stderr.strip()
    return result


def uninstall_plist(
    *,
    label: str = PLIST_LABEL,
    plist_dir: Path | None = None,
    keep_file: bool = False,
) -> dict[str, Any]:
    """Bootout the agent and optionally remove the plist file."""

    target_dir = (plist_dir or DEFAULT_PLIST_DIR).expanduser()
    target = target_dir / f"{label}.plist"

    result: dict[str, Any] = {"ok": True, "plist_path": str(target)}

    try:
        uid = os.getuid()
    except AttributeError:
        result["ok"] = False
        result["error"] = "launchd_not_supported_on_platform"
        return result

    try:
        proc = _launchctl("bootout", f"gui/{uid}/{label}")
        result["bootout_rc"] = proc.returncode
        if proc.returncode != 0 and "Could not find" not in (proc.stderr or ""):
            result["bootout_stderr"] = proc.stderr.strip()
    except FileNotFoundError:
        result["ok"] = False
        result["error"] = "launchctl_not_found"
        return result

    if not keep_file and target.exists():
        try:
            target.unlink()
            result["removed_plist"] = True
        except OSError as exc:
            result["ok"] = False
            result["error"] = f"unlink_failed: {exc}"

    return result


def plist_status(
    *,
    label: str = PLIST_LABEL,
    plist_dir: Path | None = None,
) -> dict[str, Any]:
    """Best-effort agent status — installed?, loaded?, pid?

    Pure read-only — never modifies the agent's state.
    """

    target_dir = (plist_dir or DEFAULT_PLIST_DIR).expanduser()
    target = target_dir / f"{label}.plist"

    status: dict[str, Any] = {
        "label": label,
        "plist_path": str(target),
        "installed": target.exists(),
        "loaded": False,
        "pid": None,
    }

    try:
        proc = _launchctl("list", label)
    except FileNotFoundError:
        status["error"] = "launchctl_not_found"
        return status

    if proc.returncode != 0:
        # `launchctl list <label>` returns non-zero when not loaded.
        return status

    status["loaded"] = True
    # Parse the dict-shape `launchctl list <label>` output to pull PID.
    # Lines look like:    "PID" = 12345;
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith('"PID" ='):
            tail = line.split("=", 1)[1].strip().rstrip(";").strip()
            try:
                status["pid"] = int(tail)
            except ValueError:
                pass
            break
    return status

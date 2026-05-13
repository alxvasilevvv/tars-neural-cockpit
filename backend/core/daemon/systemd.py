"""Linux systemd user-unit helpers — render, install, uninstall.

A user-unit (vs system-unit) runs in the operator's session via
``systemctl --user``. Same shape rationale as the macOS LaunchAgent
path in :mod:`backend.core.daemon.launchd` — the daemon needs
``$HOME``, the vault, browser cookies, and the meeet.world token.

Canonical layout:

  ~/.config/systemd/user/tars-background.service

Install flow:

  1. Write the unit file.
  2. ``systemctl --user daemon-reload``
  3. ``systemctl --user enable --now tars-background.service``

Uninstall flow:

  1. ``systemctl --user disable --now tars-background.service``
  2. ``rm`` the unit file.
  3. ``systemctl --user daemon-reload``

We treat ``systemctl`` exit codes the same way the launchd path
treats ``launchctl``: missing binary → ``systemctl_not_found``,
all other failures bubble into the result dict so the caller (CLI)
can present them.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


UNIT_NAME = "tars-background"
UNIT_FILENAME = f"{UNIT_NAME}.service"
DEFAULT_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"


_UNIT_TEMPLATE = """[Unit]
Description=TARS background daemon (Wave 152 — Linux parity W153)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={cwd}
ExecStart={python} -m backend.core.daemon
Environment=PYTHONPATH={cwd}
Environment=TARS_DAEMON_FORCE={force}
{extra_env}
StandardOutput=append:{log_path}
StandardError=append:{err_path}
Restart=on-failure
RestartSec=30s
# Mirror launchd's Background ProcessType priorities.
Nice=10

[Install]
WantedBy=default.target
"""


@dataclass
class UnitConfig:
    """Inputs the template renderer needs."""

    unit_name: str = UNIT_NAME
    python: str = ""
    cwd: str = ""
    force_daemon: bool = True
    extra_env: dict[str, str] | None = None
    log_path: str = ""
    err_path: str = ""

    def resolve_defaults(self) -> "UnitConfig":
        if not self.python:
            self.python = sys.executable
        if not self.cwd:
            self.cwd = str(Path(__file__).resolve().parents[3])
        if not self.log_path:
            self.log_path = str(Path.home() / ".tars" / "daemon.out.log")
        if not self.err_path:
            self.err_path = str(Path.home() / ".tars" / "daemon.err.log")
        return self


def render_unit(config: UnitConfig | None = None) -> str:
    """Build the systemd unit file body for the given config."""

    cfg = (config or UnitConfig()).resolve_defaults()
    extra_lines: list[str] = []
    for k, v in (cfg.extra_env or {}).items():
        # systemd Environment= lines accept the literal value; quote
        # for any whitespace inside.
        if " " in str(v):
            extra_lines.append(f'Environment={k}="{v}"')
        else:
            extra_lines.append(f"Environment={k}={v}")
    return _UNIT_TEMPLATE.format(
        cwd=cfg.cwd,
        python=cfg.python,
        force="1" if cfg.force_daemon else "0",
        extra_env="\n".join(extra_lines),
        log_path=cfg.log_path,
        err_path=cfg.err_path,
    )


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def install_unit(
    config: UnitConfig | None = None,
    *,
    unit_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write the user-unit + (unless dry_run) reload/enable/start."""

    cfg = (config or UnitConfig()).resolve_defaults()
    body = render_unit(cfg)
    target_dir = (unit_dir or DEFAULT_UNIT_DIR).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{cfg.unit_name}.service"

    pre_existed = target.exists()
    target.write_text(body)
    # Ensure the log dirs exist so systemd doesn't fail to open them.
    Path(cfg.log_path).parent.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "ok": True,
        "unit_path": str(target),
        "action": "updated" if pre_existed else "installed",
        "dry_run": dry_run,
    }

    if dry_run:
        return result

    try:
        proc = _systemctl("daemon-reload")
        result["daemon_reload_rc"] = proc.returncode
        if proc.returncode != 0:
            result["ok"] = False
            result["daemon_reload_stderr"] = proc.stderr.strip()
            return result
        proc = _systemctl(
            "enable", "--now", f"{cfg.unit_name}.service",
        )
        result["enable_rc"] = proc.returncode
        if proc.returncode != 0:
            result["ok"] = False
            result["enable_stderr"] = proc.stderr.strip()
    except FileNotFoundError:
        result["ok"] = False
        result["error"] = "systemctl_not_found"
    return result


def uninstall_unit(
    *,
    unit_name: str = UNIT_NAME,
    unit_dir: Path | None = None,
    keep_file: bool = False,
) -> dict[str, Any]:
    """Disable + stop + (unless keep_file) remove the unit file."""

    target_dir = (unit_dir or DEFAULT_UNIT_DIR).expanduser()
    target = target_dir / f"{unit_name}.service"
    result: dict[str, Any] = {"ok": True, "unit_path": str(target)}

    try:
        proc = _systemctl(
            "disable", "--now", f"{unit_name}.service",
        )
        result["disable_rc"] = proc.returncode
        if proc.returncode != 0:
            # disable-of-not-loaded returns non-zero — fine.
            err = (proc.stderr or "").strip()
            if err and "Failed to disable" not in err:
                result["disable_stderr"] = err
    except FileNotFoundError:
        result["ok"] = False
        result["error"] = "systemctl_not_found"
        return result

    if not keep_file and target.exists():
        try:
            target.unlink()
            result["removed_unit"] = True
        except OSError as exc:
            result["ok"] = False
            result["error"] = f"unlink_failed: {exc}"

    # Reload so systemd notices the removal.
    try:
        _systemctl("daemon-reload")
    except FileNotFoundError:
        pass
    return result


def unit_status(
    *,
    unit_name: str = UNIT_NAME,
    unit_dir: Path | None = None,
) -> dict[str, Any]:
    """Best-effort status — installed?, active?, pid?

    Uses ``systemctl --user show`` for the structured output and
    ``systemctl --user is-active`` for a quick yes/no.
    """

    target_dir = (unit_dir or DEFAULT_UNIT_DIR).expanduser()
    target = target_dir / f"{unit_name}.service"
    status: dict[str, Any] = {
        "unit_name": unit_name,
        "unit_path": str(target),
        "installed": target.exists(),
        "active": False,
        "pid": None,
    }

    try:
        proc = _systemctl("is-active", f"{unit_name}.service")
    except FileNotFoundError:
        status["error"] = "systemctl_not_found"
        return status

    if (proc.stdout or "").strip() == "active":
        status["active"] = True

    # Pull MainPID from show
    try:
        proc = _systemctl(
            "show",
            f"{unit_name}.service",
            "--property=MainPID",
        )
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("MainPID="):
                tail = line.split("=", 1)[1].strip()
                try:
                    pid = int(tail)
                    status["pid"] = pid if pid > 0 else None
                except ValueError:
                    pass
                break
    except FileNotFoundError:
        pass
    return status

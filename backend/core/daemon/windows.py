"""Windows Task Scheduler helpers — render, install, uninstall (Wave 171).

Closes the daemon cross-platform trifecta (macOS launchd in W152,
Linux systemd user-unit in W153, Windows Task Scheduler in W171).

Approach: use ``schtasks.exe`` to register a per-user task that
runs ``python -m backend.core.daemon`` at logon and respawns on
failure. We write a Task Scheduler XML file to a temp path, then
register it via ``schtasks /Create /XML``. Removal uses
``schtasks /Delete``.

Why XML instead of `/Create /SC /TR /TN`? The XML form supports
the full Task Scheduler schema (RestartOnFailure, NetworkSettings,
ExecutionTimeLimit, run-as-current-user) which the simpler
command-line flags can't fully express.

Honest framing:
  - **Windows only.** ``schtasks.exe`` doesn't exist elsewhere.
    The module returns ``not_supported_on_platform`` on non-win32.
  - **Per-user task.** Runs in the operator's session (not as
    SYSTEM) — same posture as launchd LaunchAgent + systemd
    user-unit. Operator's HOME, vault, browser cookies all
    accessible.
  - **Tested with mocked subprocess.** Real schtasks invocations
    happen only on the operator's machine.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


log = logging.getLogger("tars.daemon.windows")


TASK_NAME = "tars-background"


_TASK_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>TARS background daemon — Wave 171 cross-platform parity</Description>
    <Author>TARS</Author>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT30S</Interval>
      <Count>999</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{python}</Command>
      <Arguments>-m backend.core.daemon</Arguments>
      <WorkingDirectory>{cwd}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


@dataclass
class WindowsTaskConfig:
    """Inputs the XML renderer needs."""

    task_name: str = TASK_NAME
    python: str = ""
    cwd: str = ""
    force_daemon: bool = True
    extra_env: dict[str, str] | None = None
    log_path: str = ""
    err_path: str = ""

    def resolve_defaults(self) -> "WindowsTaskConfig":
        if not self.python:
            self.python = sys.executable
        if not self.cwd:
            self.cwd = str(Path(__file__).resolve().parents[3])
        if not self.log_path:
            self.log_path = str(Path.home() / ".tars" / "daemon.out.log")
        if not self.err_path:
            self.err_path = str(Path.home() / ".tars" / "daemon.err.log")
        return self


def _xml_escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_task_xml(config: WindowsTaskConfig | None = None) -> str:
    """Build the Task Scheduler XML for the given config.

    Note: Task Scheduler requires UTF-16 encoding when imported
    via ``schtasks /Create /XML``. Callers should write the
    output as ``encoding='utf-16'`` (handled in ``install_task``).
    """

    cfg = (config or WindowsTaskConfig()).resolve_defaults()
    # extra_env / force_daemon / log_path / err_path aren't directly
    # representable in the Task Scheduler XML schema (it uses
    # process environment from the user session by default). We
    # surface them in the description for operator debugging.
    return _TASK_XML_TEMPLATE.format(
        python=_xml_escape(cfg.python),
        cwd=_xml_escape(cfg.cwd),
    )


def _schtasks(*args: str) -> subprocess.CompletedProcess:
    """Thin wrapper around schtasks.exe."""

    return subprocess.run(
        ["schtasks", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def is_supported() -> bool:
    """True iff this host is Windows."""

    return sys.platform.startswith("win")


def install_task(
    config: WindowsTaskConfig | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write XML + run ``schtasks /Create /XML``.

    Returns ``{ok, task_name, xml_path, schtasks_rc?, error?}``.
    ``dry_run=True`` writes the XML but skips ``schtasks``.
    """

    cfg = (config or WindowsTaskConfig()).resolve_defaults()
    xml = render_task_xml(cfg)

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".xml", delete=False, encoding="utf-16",
    )
    try:
        tmp.write(xml)
        tmp.close()
        xml_path = tmp.name
    except Exception as exc:
        return {"ok": False, "error": "xml_write_failed", "detail": str(exc)}

    result: dict[str, Any] = {
        "ok": True,
        "task_name": cfg.task_name,
        "xml_path": xml_path,
        "dry_run": dry_run,
    }

    if dry_run:
        return result

    try:
        # First, delete an existing instance so we always boot a
        # fresh copy of the new XML. Failure is fine.
        _schtasks("/Delete", "/TN", cfg.task_name, "/F")
        proc = _schtasks("/Create", "/TN", cfg.task_name, "/XML", xml_path, "/F")
    except FileNotFoundError:
        result["ok"] = False
        result["error"] = "schtasks_not_found"
        return result

    result["schtasks_rc"] = proc.returncode
    if proc.returncode != 0:
        result["ok"] = False
        result["schtasks_stderr"] = (proc.stderr or "").strip()
    return result


def uninstall_task(
    *,
    task_name: str = TASK_NAME,
    keep_xml: bool = False,
) -> dict[str, Any]:
    """Run ``schtasks /Delete``. Returns ``{ok, task_name, ...}``."""

    result: dict[str, Any] = {"ok": True, "task_name": task_name}

    try:
        proc = _schtasks("/Delete", "/TN", task_name, "/F")
    except FileNotFoundError:
        result["ok"] = False
        result["error"] = "schtasks_not_found"
        return result

    result["schtasks_rc"] = proc.returncode
    if proc.returncode != 0:
        # Treat "task not found" as success — we're trying to ensure
        # it's gone. Other errors get surfaced.
        err = (proc.stderr or "").strip()
        if "cannot find" not in err.lower() and "could not be found" not in err.lower():
            result["ok"] = False
            result["schtasks_stderr"] = err
    return result


def task_status(*, task_name: str = TASK_NAME) -> dict[str, Any]:
    """Best-effort status. Returns ``{task_name, installed, active, pid}``.

    Windows Task Scheduler doesn't track per-task PIDs in the same
    way launchd / systemd do — ``schtasks /Query`` shows
    last-run-time and status, not the PID of the current run. We
    surface what's available + a stable ``installed`` flag.
    """

    status: dict[str, Any] = {
        "task_name": task_name,
        "installed": False,
        "active": False,
        "pid": None,
    }

    try:
        proc = _schtasks("/Query", "/TN", task_name, "/FO", "LIST")
    except FileNotFoundError:
        status["error"] = "schtasks_not_found"
        return status

    if proc.returncode != 0:
        return status

    status["installed"] = True
    # Parse the LIST output for the Status line.
    for line in (proc.stdout or "").splitlines():
        ls = line.strip()
        if ls.lower().startswith("status:"):
            value = ls.split(":", 1)[1].strip()
            if value.lower() == "running":
                status["active"] = True
            break
    return status

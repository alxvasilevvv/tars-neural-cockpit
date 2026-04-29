// Sidecar — bring up the FastAPI backend as a child process.
//
// Lifecycle (Phase L9 A1):
//
//   spawn() → resolve binary path → Command::spawn → poll /health
//          ↘ (failure: emit `desktop.sidecar.failed`)
//          ↘ (success: emit `desktop.sidecar.started`, retain handle)
//
//   on app shutdown → SidecarHandle::Drop → SIGTERM → wait 5 s → SIGKILL
//                                          ↘ emit `desktop.sidecar.exited`
//
// The event payload contract lives at
// `desktop/src-tauri/sidecar-events.schema.json` and is pinned by
// `tests/test_desktop_sidecar_events_contract.py`. **Do not** rename
// fields without updating both.
//
// Binary resolution order:
//   1. `TARS_BACKEND_BIN` — explicit override (CI / dev).
//   2. `<resource_dir>/tars-backend(.exe)` — bundled pyoxidizer build.
//   3. `python3 serve.py` — fallback for local dev when the operator
//      is running the repo directly.

use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use log::{info, warn};
use serde_json::json;
use tauri::{Emitter, Manager};

const HEALTH_PATH: &str = "/health";
const DEFAULT_PORT: u16 = 8765;
const HEALTH_TIMEOUT: Duration = Duration::from_secs(15);
const HEALTH_INTERVAL: Duration = Duration::from_millis(250);
const SHUTDOWN_GRACE: Duration = Duration::from_secs(5);

#[derive(Clone, Copy, Debug)]
enum LaunchMode {
    Pyoxidizer,
    Python,
    External,
}

impl LaunchMode {
    fn as_str(self) -> &'static str {
        match self {
            LaunchMode::Pyoxidizer => "pyoxidizer",
            LaunchMode::Python => "python",
            LaunchMode::External => "external",
        }
    }
}

/// Owned sidecar process. Drop kills the child and emits
/// `desktop.sidecar.exited` (best-effort, non-fatal if the runtime is
/// already shutting down).
pub struct SidecarHandle {
    child: Option<Child>,
    pid: u32,
    started_at: Instant,
    app: tauri::AppHandle<tauri::Wry>,
}

impl SidecarHandle {
    fn new(child: Child, app: tauri::AppHandle<tauri::Wry>) -> Self {
        let pid = child.id();
        Self {
            child: Some(child),
            pid,
            started_at: Instant::now(),
            app,
        }
    }
}

impl Drop for SidecarHandle {
    fn drop(&mut self) {
        let pid = self.pid;
        let ran_ms = self.started_at.elapsed().as_millis() as u64;

        let exit = if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let deadline = Instant::now() + SHUTDOWN_GRACE;
            loop {
                match child.try_wait() {
                    Ok(Some(status)) => break Some(status),
                    Ok(None) if Instant::now() >= deadline => {
                        let _ = child.kill();
                        break child.wait().ok();
                    }
                    Ok(None) => thread::sleep(Duration::from_millis(100)),
                    Err(_) => break None,
                }
            }
        } else {
            None
        };

        let payload = json!({
            "pid": pid,
            "ran_ms": ran_ms,
            "exit_code": exit.as_ref().and_then(|s| s.code()),
            "signal": exit.as_ref().and_then(unix_signal_name),
        });
        let _ = self.app.emit("desktop.sidecar.exited", payload);
        info!("tars.desktop.sidecar.exited pid={pid} ran_ms={ran_ms}");
    }
}

#[cfg(unix)]
fn unix_signal_name(status: &std::process::ExitStatus) -> Option<String> {
    use std::os::unix::process::ExitStatusExt;
    status.signal().map(|n| format!("SIG{n}"))
}

#[cfg(not(unix))]
fn unix_signal_name(_status: &std::process::ExitStatus) -> Option<String> {
    None
}

/// Try to bring the sidecar up. Always emits exactly one of
/// `desktop.sidecar.started` or `desktop.sidecar.failed`. On success
/// the returned handle is stashed in Tauri state so it lives as long
/// as the app.
pub fn spawn(app: &tauri::AppHandle<tauri::Wry>) -> Result<(), String> {
    let port = std::env::var("PORT")
        .ok()
        .and_then(|s| s.parse::<u16>().ok())
        .unwrap_or(DEFAULT_PORT);
    let started_at = Instant::now();

    let (mode, mut cmd) = build_command(app, port)?;

    let child = match cmd.spawn() {
        Ok(child) => child,
        Err(err) => {
            let took_ms = started_at.elapsed().as_millis() as u64;
            emit_failed(app, "spawn", &err.to_string(), took_ms, None);
            return Err(format!("sidecar spawn failed: {err}"));
        }
    };

    let pid = child.id();
    info!(
        "tars.desktop.sidecar.spawning mode={mode} pid={pid} port={port}",
        mode = mode.as_str()
    );

    let handle = SidecarHandle::new(child, app.clone());
    let handle = Arc::new(Mutex::new(Some(handle)));
    app.manage(handle.clone());

    match wait_for_health(port, HEALTH_TIMEOUT) {
        Ok(took_ms) => {
            let payload = json!({
                "pid": pid,
                "port": port,
                "took_ms": took_ms,
                "mode": mode.as_str(),
            });
            let _ = app.emit("desktop.sidecar.started", payload);
            info!(
                "tars.desktop.sidecar.started pid={pid} port={port} mode={mode} took_ms={took_ms}",
                mode = mode.as_str()
            );
            Ok(())
        }
        Err(stage_err) => {
            let took_ms = started_at.elapsed().as_millis() as u64;
            emit_failed(app, &stage_err.0, &stage_err.1, took_ms, Some(pid));
            // Drop the handle to kill the child we just spawned.
            if let Ok(mut guard) = handle.lock() {
                *guard = None;
            }
            Err(format!("sidecar health failed: {}", stage_err.1))
        }
    }
}

fn build_command(
    app: &tauri::AppHandle<tauri::Wry>,
    port: u16,
) -> Result<(LaunchMode, Command), String> {
    if let Ok(p) = std::env::var("TARS_BACKEND_BIN") {
        let path = PathBuf::from(p);
        if !path.exists() {
            return Err(format!("TARS_BACKEND_BIN does not exist: {}", path.display()));
        }
        let cmd = base_cmd(path.as_path(), port);
        return Ok((LaunchMode::External, cmd));
    }

    if let Some(bundled) = bundled_backend(app) {
        let cmd = base_cmd(bundled.as_path(), port);
        return Ok((LaunchMode::Pyoxidizer, cmd));
    }

    let mut cmd = Command::new("python3");
    cmd.arg("serve.py");
    let repo_root = repo_root_guess(app);
    if let Some(dir) = repo_root {
        cmd.current_dir(dir);
    }
    cmd.env("PORT", port.to_string());
    cmd.env("PYTHONPATH", ".");
    cmd.stdout(Stdio::null());
    cmd.stderr(Stdio::null());
    Ok((LaunchMode::Python, cmd))
}

fn base_cmd(bin: &Path, port: u16) -> Command {
    let mut cmd = Command::new(bin);
    cmd.env("PORT", port.to_string());
    cmd.env("HOST", "127.0.0.1");
    cmd.stdout(Stdio::null());
    cmd.stderr(Stdio::null());
    cmd
}

fn bundled_backend(app: &tauri::AppHandle<tauri::Wry>) -> Option<PathBuf> {
    let exe_name = if cfg!(windows) { "tars-backend.exe" } else { "tars-backend" };
    let resource_dir = app.path().resource_dir().ok()?;
    let candidate = resource_dir.join(exe_name);
    if candidate.exists() {
        Some(candidate)
    } else {
        None
    }
}

fn repo_root_guess(_app: &tauri::AppHandle<tauri::Wry>) -> Option<PathBuf> {
    // In dev mode the user runs `pnpm tauri:dev` from `desktop/`; the
    // repo root is the parent of CARGO_MANIFEST_DIR's parent.
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest.parent().and_then(|p| p.parent()).map(PathBuf::from)
}

fn emit_failed(
    app: &tauri::AppHandle<tauri::Wry>,
    stage: &str,
    error: &str,
    took_ms: u64,
    pid: Option<u32>,
) {
    let payload = json!({
        "stage": stage,
        "error": error,
        "took_ms": took_ms,
        "pid": pid,
    });
    let _ = app.emit("desktop.sidecar.failed", payload);
    warn!(
        "tars.desktop.sidecar.failed stage={stage} took_ms={took_ms} error={error}"
    );
}

fn wait_for_health(port: u16, timeout: Duration) -> Result<u64, (String, String)> {
    let start = Instant::now();
    loop {
        if start.elapsed() > timeout {
            return Err((
                "health_timeout".to_string(),
                format!(
                    "GET http://127.0.0.1:{port}{HEALTH_PATH} did not return 200 within {}ms",
                    timeout.as_millis()
                ),
            ));
        }
        if let Ok(true) = http_get_ok(port, HEALTH_PATH) {
            return Ok(start.elapsed().as_millis() as u64);
        }
        thread::sleep(HEALTH_INTERVAL);
    }
}

/// Tiny HTTP/1.1 GET, returns Ok(true) iff the status line starts with `200`.
/// Stdlib-only on purpose — we don't want to drag in `reqwest` for one call.
fn http_get_ok(port: u16, path: &str) -> std::io::Result<bool> {
    let mut stream = TcpStream::connect_timeout(
        &format!("127.0.0.1:{port}").parse().expect("addr"),
        Duration::from_millis(500),
    )?;
    stream.set_read_timeout(Some(Duration::from_millis(500)))?;
    stream.set_write_timeout(Some(Duration::from_millis(500)))?;
    let req = format!(
        "GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\nUser-Agent: tars-desktop/healthcheck\r\n\r\n"
    );
    stream.write_all(req.as_bytes())?;
    let mut buf = [0u8; 64];
    let n = stream.read(&mut buf)?;
    let head = std::str::from_utf8(&buf[..n]).unwrap_or("");
    Ok(head.starts_with("HTTP/1.1 200") || head.starts_with("HTTP/1.0 200"))
}

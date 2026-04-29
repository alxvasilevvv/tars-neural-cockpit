// TARS desktop entry point.
//
// Phase L9 v1: bring up a Tauri 2 window pointing at the cockpit web
// build (or the dev server in `tauri dev`). The pyoxidizer sidecar
// (FastAPI backend) is owned by `sidecar.rs` — it boots automatically
// in release builds, falling back to `TARS_BACKEND_BIN` or
// `python serve.py` for `tauri dev` workflows.
//
// Everything observable lands as a structured log (env_logger) so
// the meeet event emitter on the Rust side can pick it up.

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

mod sidecar;

use log::info;

fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    info!("tars.desktop.boot product=tars version={}", env!("CARGO_PKG_VERSION"));

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_updater::Builder::default().build())
        .setup(|app| {
            // Sidecar bring-up is best-effort and non-fatal — if it
            // fails we still show the cockpit pointing at whatever
            // 127.0.0.1:8765 the user has running manually. The
            // SidecarHandle is stashed inside Tauri state, so it lives
            // until the runtime drops state on app shutdown — that
            // emits `desktop.sidecar.exited` and reaps the child.
            let handle = app.handle().clone();
            if let Err(err) = sidecar::spawn(&handle) {
                eprintln!("[tars.desktop] sidecar.spawn failed: {err}");
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                info!("tars.desktop.window.close label={}", window.label());
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

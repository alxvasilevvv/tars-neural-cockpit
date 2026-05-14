// TARS desktop entry point.
//
// Phase L9 v1 brought up the bare Tauri 2 shell + sidecar bring-up.
// Wave 59 layers the native UX on top so this stops feeling like a
// wrapped web view and starts feeling like a real Mac/Windows app:
//
//   • window-state plugin   — TARS remembers size/position across launches
//   • global-shortcut       — Cmd/Ctrl+Shift+Space toggles main window
//                             from anywhere (Spotlight / Raycast pattern)
//   • tray icon + menu      — menu-bar entry with Show / Quit + click
//                             toggles main window visibility
//   • deep-link handler     — `tars://onboarding?role=…`, `tars://thread/…`,
//                             `tars://cockpit` route into the cockpit's
//                             React Router via window.tauri.deepLink event
//
// Sidecar bring-up (FastAPI on 127.0.0.1:8765) lives in `sidecar.rs`.
// Everything observable still lands as a structured log so the meeet
// event emitter can pick it up.

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

mod sidecar;

use log::{info, warn};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Emitter, Manager,
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};
use tauri_plugin_deep_link::DeepLinkExt;  // W202: needed for app.deep_link()

/// Show + focus + unminimize the main window in one call. Used by the
/// tray click handler, the global shortcut, and deep-link arrivals.
fn focus_main_window(app: &tauri::AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.unminimize();
        let _ = win.show();
        let _ = win.set_focus();
    } else {
        warn!("tars.desktop.focus_main: no `main` window registered");
    }
}

/// W203 — Capture the current screen via macOS `screencapture` and
/// return it as a base64 PNG data URL. Wired to the cockpit's Vision
/// tab "📸 Capture & analyze" button (calls `invoke('vision_capture_screen')`).
///
/// On non-macOS the command returns an empty string and lets the
/// cockpit fall back to `getDisplayMedia()`.
#[tauri::command]
fn vision_capture_screen() -> Result<String, String> {
    #[cfg(target_os = "macos")]
    {
        use std::process::Command;
        // Write to a temp file then read it back as base64. -x suppresses
        // the camera-click sound. -t png picks the format.
        let tmp = std::env::temp_dir().join(format!("tars-vision-{}.png", std::process::id()));
        let status = Command::new("screencapture")
            .args(["-x", "-t", "png", tmp.to_str().unwrap_or("/tmp/tars-vision.png")])
            .status()
            .map_err(|e| format!("screencapture spawn failed: {e}"))?;
        if !status.success() {
            return Err(format!("screencapture exit={status:?}"));
        }
        let bytes = std::fs::read(&tmp).map_err(|e| format!("read png failed: {e}"))?;
        // Best-effort cleanup; ignore errors.
        let _ = std::fs::remove_file(&tmp);
        use base64::{engine::general_purpose, Engine};
        let b64 = general_purpose::STANDARD.encode(&bytes);
        Ok(format!("data:image/png;base64,{b64}"))
    }
    #[cfg(not(target_os = "macos"))]
    {
        // Linux/Windows: cockpit falls back to getDisplayMedia()
        Err("screen_capture_not_implemented_on_this_os".into())
    }
}

/// Toggle visibility — used by global shortcut (and could be reused
/// from tray menu later). If hidden or minimized, surface the window.
/// If currently focused and visible, hide.
fn toggle_main_window(app: &tauri::AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        let visible = win.is_visible().unwrap_or(false);
        let focused = win.is_focused().unwrap_or(false);
        if visible && focused {
            let _ = win.hide();
        } else {
            focus_main_window(app);
        }
    }
}

fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    info!(
        "tars.desktop.boot product=tars version={}",
        env!("CARGO_PKG_VERSION")
    );

    tauri::Builder::default()
        // ─── Invoke handlers (W203) ──────────────────────────────────
        .invoke_handler(tauri::generate_handler![vision_capture_screen])
        // ─── Plugins ──────────────────────────────────────────────────
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_updater::Builder::default().build())
        // window-state must be registered BEFORE the window is created
        // so it can hydrate the saved size/position into the window
        // builder. Tauri handles this internally when added here.
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_deep_link::init())
        // global-shortcut needs an explicit handler — installed in setup
        // so we can capture the AppHandle.
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        info!("tars.desktop.shortcut.toggle");
                        toggle_main_window(app);
                    }
                })
                .build(),
        )
        // ─── App setup ───────────────────────────────────────────────
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

            // ─── W226: DevTools auto-open via env flag ───────────────
            // If `TARS_DEVTOOLS=1` is set in the environment, open the
            // DevTools window on boot. The `devtools` Cargo feature on
            // `tauri` enables right-click → "Inspect Element" on every
            // WebView at compile time; this just toggles the auto-open
            // for headless live-debug runs. Soft-fails if the window
            // can't be found (e.g. before setup is complete).
            #[cfg(any(debug_assertions, feature = "devtools"))]
            if std::env::var("TARS_DEVTOOLS").as_deref() == Ok("1") {
                if let Some(win) = app.get_webview_window("main") {
                    win.open_devtools();
                    info!("tars.desktop.devtools.opened reason=env=TARS_DEVTOOLS=1");
                } else {
                    warn!("tars.desktop.devtools.no_main_window");
                }
            }

            // ─── Global shortcut: Cmd/Ctrl+Shift+Space ───────────────
            // Spotlight-style summon. The handler is registered up
            // above on the plugin builder; here we just register the
            // key combo. Soft-fail if the OS denies registration
            // (e.g. another app has the same shortcut).
            let toggle_shortcut = Shortcut::new(
                Some(Modifiers::SHIFT | Modifiers::SUPER),
                Code::Space,
            );
            if let Err(err) = app.global_shortcut().register(toggle_shortcut) {
                warn!(
                    "tars.desktop.shortcut.register_failed shortcut=Cmd+Shift+Space err={}",
                    err
                );
            } else {
                info!("tars.desktop.shortcut.registered shortcut=Cmd+Shift+Space");
            }

            // ─── Tray icon + menu ────────────────────────────────────
            // macOS shows it in the menu bar; Windows in the system
            // tray; Linux depends on the desktop environment. Click
            // the icon → toggle the main window (so single click feels
            // like Spotlight). The "Show TARS" / "Quit" menu items
            // give explicit affordances for keyboard-only users and
            // anyone who can't remember the global shortcut.
            let show_item = MenuItem::with_id(app, "show", "Show TARS", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit TARS", true, None::<&str>)?;
            let tray_menu = Menu::with_items(app, &[&show_item, &quit_item])?;

            let _tray = TrayIconBuilder::with_id("tars-main")
                .menu(&tray_menu)
                .show_menu_on_left_click(false)
                .tooltip("TARS — local-first neural cockpit")
                .icon(
                    app.default_window_icon()
                        .cloned()
                        .ok_or("missing default window icon")?,
                )
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "show" => focus_main_window(app),
                    "quit" => {
                        info!("tars.desktop.tray.quit");
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    // Left-click anywhere on the icon (not the menu)
                    // → toggle. Right-click defers to the menu.
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        toggle_main_window(tray.app_handle());
                    }
                })
                .build(app)?;

            // ─── Deep link routing: `tars://…` ───────────────────────
            // The deep-link plugin captures the URL on app launch
            // (cold) and on app re-activation (warm). We focus the
            // window first, then forward the URL to the cockpit via
            // an event the React side already listens for. Routing
            // happens in TS — here we only deliver.
            let app_handle = app.handle().clone();
            app.deep_link().on_open_url(move |event| {
                let urls: Vec<String> = event
                    .urls()
                    .into_iter()
                    .map(|u| u.to_string())
                    .collect();
                info!("tars.desktop.deeplink count={} first={:?}", urls.len(), urls.first());
                focus_main_window(&app_handle);
                // Cockpit subscribes via @tauri-apps/api/event ->
                // listen("tars://deeplink", …). Payload is the array
                // of URLs (some platforms batch multiple).
                if let Err(err) = app_handle.emit("tars://deeplink", &urls) {
                    warn!("tars.desktop.deeplink.emit_failed err={}", err);
                }
            });

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

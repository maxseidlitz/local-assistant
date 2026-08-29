use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager,
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

#[tauri::command]
fn daemon_url() -> String {
    std::env::var("ASSISTANT_URL").unwrap_or_else(|_| "http://127.0.0.1:8765".into())
}

#[tauri::command]
fn hide_hud(app: AppHandle) {
    if let Some(window) = app.get_webview_window("hud") {
        let _ = window.hide();
    }
}

#[tauri::command]
fn capture_front_window() -> Result<String, String> {
    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_millis();
    let path = std::env::temp_dir().join(format!("assistant-hud-{millis}.png"));
    let status = Command::new("screencapture")
        .args(["-x", path.to_str().ok_or("Pfad ungültig")?])
        .status()
        .map_err(|e| e.to_string())?;
    if !status.success() {
        return Err("screencapture fehlgeschlagen".into());
    }
    Ok(path.to_string_lossy().into_owned())
}

fn toggle_hud(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("hud") {
        if window.is_visible().unwrap_or(false) {
            let _ = window.hide();
        } else {
            let _ = window.show();
            let _ = window.set_focus();
            let _ = app.emit("focus-input", ());
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            daemon_url,
            hide_hud,
            capture_front_window
        ])
        .setup(|app| {
            let show = MenuItem::with_id(app, "show", "Einblenden", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Beenden", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            let handle = app.handle().clone();
            TrayIconBuilder::new()
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(move |_tray, event| match event.id.as_ref() {
                    "show" => toggle_hud(&handle),
                    "quit" => handle.exit(0),
                    _ => {}
                })
                .build(app)?;

            let alt_space = Shortcut::new(Some(Modifiers::ALT), Code::Space);
            let ctrl_space = Shortcut::new(Some(Modifiers::CONTROL), Code::Space);
            let shortcut_app = app.handle().clone();
            app.handle().plugin(
                tauri_plugin_global_shortcut::Builder::new()
                    .with_handler(move |app, shortcut, event| {
                        let is_alt = shortcut == &alt_space;
                        let is_ctrl = shortcut == &ctrl_space;
                        match event.state {
                            ShortcutState::Pressed if is_alt => toggle_hud(app),
                            ShortcutState::Pressed if is_ctrl => {
                                let _ = shortcut_app.emit("ptt-start", ());
                            }
                            ShortcutState::Released if is_ctrl => {
                                let _ = shortcut_app.emit("ptt-stop", ());
                            }
                            _ => {}
                        }
                    })
                    .build(),
            )?;
            let _ = app.global_shortcut().register(alt_space);
            let _ = app.global_shortcut().register(ctrl_space);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("HUD konnte nicht starten");
}

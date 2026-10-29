#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod files;
mod recovery;
mod runtime;
mod tracing;
mod transport;
mod window_state;
use runtime::{Health, Runtime};
use serde_json::Value;
use std::sync::{Arc, Mutex};
use tauri::Manager;

type Shared = Arc<Mutex<Runtime>>;

fn main_window(window: &tauri::WebviewWindow) -> Result<(), String> {
    if window.label() != "main" {
        return Err("forbidden".into());
    }
    let url = window.url().map_err(|_| "forbidden")?;
    let packaged = (url.scheme() == "tauri" && url.host_str() == Some("localhost"))
        || (url.scheme() == "http" && url.host_str() == Some("tauri.localhost"));
    let dev = cfg!(debug_assertions)
        && url.scheme() == "http"
        && url.host_str() == Some("127.0.0.1")
        && url.port() == Some(4317);
    if packaged || dev {
        Ok(())
    } else {
        Err("forbidden".into())
    }
}

#[tauri::command]
async fn runtime_health(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, Shared>,
) -> Result<Health, String> {
    main_window(&window)?;
    let runtime = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        runtime
            .lock()
            .map_err(|_| "host_failed".into())
            .map(|mut r| r.health())
    })
    .await
    .map_err(|_| "host_failed".to_string())?
}

#[tauri::command]
async fn runtime_restart(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, Shared>,
) -> Result<Health, String> {
    main_window(&window)?;
    let runtime = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        runtime
            .try_lock()
            .map_err(|_| "busy".into())
            .map(|mut r| r.restart())
    })
    .await
    .map_err(|_| "host_failed".to_string())?
}

#[tauri::command]
async fn workspace_call(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, Shared>,
    operation: String,
    args: Value,
) -> Result<Value, String> {
    main_window(&window)?;
    let runtime = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        runtime
            .lock()
            .map_err(|_| "host_failed".to_string())?
            .call(&operation, args)
    })
    .await
    .map_err(|_| "host_failed".to_string())?
}

#[tauri::command]
async fn select_documents(
    window: tauri::WebviewWindow,
    folder: bool,
) -> Result<Vec<files::SelectedFile>, String> {
    main_window(&window)?;
    tauri::async_runtime::spawn_blocking(move || files::pick(folder))
        .await
        .map_err(|_| "File selection could not finish".to_string())?
}

fn diagnostic(message: &str) {
    if let Some(local) = std::env::var_os("LOCALAPPDATA") {
        let folder = std::path::PathBuf::from(local).join("dev.swarneil.relaystudio");
        let _ = std::fs::create_dir_all(&folder);
        let _ = std::fs::write(folder.join("startup.log"), message);
    }
    eprintln!("{message}");
    #[cfg(windows)]
    unsafe {
        // SAFETY: NUL-terminated UTF-16 buffers remain alive during MessageBoxW.
        #[link(name = "user32")]
        extern "system" {
            fn MessageBoxW(hwnd: isize, text: *const u16, caption: *const u16, kind: u32) -> i32;
        }
        let text: Vec<u16> = message.encode_utf16().chain(Some(0)).collect();
        let title: Vec<u16> = "Veya startup".encode_utf16().chain(Some(0)).collect();
        MessageBoxW(0, text.as_ptr(), title.as_ptr(), 0x10);
    }
}

fn main() {
    let application = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            runtime_health,
            runtime_restart,
            workspace_call,
            select_documents
        ])
        .setup(|app| {
            let folder = app.path().app_local_data_dir()?;
            if let Some(window) = app.get_webview_window("main") {
                window_state::install(&window, folder.join("window-v1.json"));
            }
            let python = std::env::var_os("VEYA_PYTHON")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|| "python".into());
            let runtime = Arc::new(Mutex::new(Runtime::new(
                python,
                runtime::runtime_source(&app.path().resource_dir()?),
                folder.join("workspace-v1"),
                folder.join("runtime.log"),
            )));
            app.manage(runtime.clone());
            tauri::async_runtime::spawn_blocking(move || {
                if let Ok(mut runtime) = runtime.lock() {
                    runtime.start();
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!());
    match application {
        Ok(app) => app.run(|handle, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                if let Ok(mut runtime) = handle.state::<Shared>().lock() { runtime.stop(); }
            }
        }),
        Err(_) => diagnostic("Veya could not open its desktop window. Repair Microsoft Edge WebView2 and reinstall Veya with its packaged assets. Startup diagnostics: %LOCALAPPDATA%\\dev.swarneil.relaystudio\\startup.log"),
    }
}

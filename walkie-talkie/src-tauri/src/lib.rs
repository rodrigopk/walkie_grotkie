use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

/// Main Tauri application setup.
///
/// Spawns the Python `grot-server` sidecar on startup and logs its
/// stdout/stderr output. The sidecar is automatically killed when the
/// Tauri window closes (Tauri manages the child process lifecycle).
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            spawn_grot_server(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application")
}

fn spawn_grot_server(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let sidecar = app
        .shell()
        .sidecar("grot-server")
        .map_err(|e| format!("Failed to create grot-server sidecar command: {e}"))?;

    let (mut rx, child) = sidecar
        .spawn()
        .map_err(|e| format!("Failed to spawn grot-server: {e}. Is the binary present in src-tauri/binaries/?"))?;

    // Forward sidecar output to Tauri's logging system in a background task.
    // child is moved into the task to keep it alive for the full app lifetime,
    // so Tauri can kill the sidecar when the window closes.
    tauri::async_runtime::spawn(async move {
        let _child = child;
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let text = String::from_utf8_lossy(&line);
                    // Print to stdout so it appears in `cargo tauri dev` terminal.
                    print!("[grot-server] {text}");
                }
                CommandEvent::Stderr(line) => {
                    let text = String::from_utf8_lossy(&line);
                    eprint!("[grot-server] {text}");
                }
                CommandEvent::Error(err) => {
                    eprintln!("[grot-server] process error: {err}");
                }
                CommandEvent::Terminated(status) => {
                    eprintln!(
                        "[grot-server] process terminated with code {:?}",
                        status.code
                    );
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(())
}

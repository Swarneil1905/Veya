fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "runtime_health",
            "runtime_restart",
            "workspace_call",
        ]),
    ))
    .expect("Veya native manifest could not be built")
}

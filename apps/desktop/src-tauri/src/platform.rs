//! Explicit native support information; a build is not an installed-app certification.
use serde::Serialize;

#[derive(Serialize)]
pub struct Capabilities {
    pub operating_system: &'static str,
    pub native_file_picker: bool,
    pub windows_credentials: bool,
    pub installed_release_verified: bool,
}

pub fn capabilities() -> Capabilities {
    Capabilities {
        operating_system: std::env::consts::OS,
        native_file_picker: cfg!(windows),
        windows_credentials: cfg!(windows),
        installed_release_verified: false,
    }
}

pub fn startup_failure() -> &'static str {
    if cfg!(windows) {
        "Veya could not open its desktop window. Check WebView2 and the packaged runtime."
    } else {
        "Veya could not open its desktop window. Check the platform webview libraries and runtime."
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn capabilities_do_not_claim_windows_integrations_on_other_hosts() {
        let current = capabilities();
        assert_eq!(current.native_file_picker, cfg!(windows));
        assert_eq!(current.windows_credentials, cfg!(windows));
        assert!(!current.installed_release_verified);
        if !cfg!(windows) {
            assert!(!startup_failure().contains("WebView2"));
        }
    }
}

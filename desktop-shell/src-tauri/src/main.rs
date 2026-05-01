#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::path::PathBuf;
use std::process::Command;

use tauri::{WebviewUrl, WebviewWindowBuilder};

const DASHBOARD_URL: &str = "http://127.0.0.1:3420/dashboard/command-post";
const DASHBOARD_API_KEY_ENV: &str = "DASHBOARD_API_KEY";

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."))
}

fn percent_encode_fragment(value: &str) -> String {
    let mut encoded = String::with_capacity(value.len());
    for byte in value.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                encoded.push(byte as char)
            }
            _ => encoded.push_str(&format!("%{:02X}", byte)),
        }
    }
    encoded
}

fn build_dashboard_url(api_key: Option<&str>) -> String {
    match api_key.map(str::trim).filter(|value| !value.is_empty()) {
        Some(value) => format!(
            "{DASHBOARD_URL}#desktop_api_key={}",
            percent_encode_fragment(value)
        ),
        None => DASHBOARD_URL.to_string(),
    }
}

fn start_runtime() -> bool {
    let script = repo_root().join("scripts/dashboard_ctl.sh");
    Command::new("bash")
        .arg(script)
        .arg("start")
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn dashboard_webview_url() -> WebviewUrl {
    if !start_runtime() {
        return WebviewUrl::App("index.html".into());
    }
    let target = build_dashboard_url(env::var(DASHBOARD_API_KEY_ENV).ok().as_deref());
    let url = target.parse().expect("dashboard URL should be a valid URL");
    WebviewUrl::External(url)
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            WebviewWindowBuilder::new(app, "main", dashboard_webview_url())
                .title("DHARMA COMMAND")
                .inner_size(1600.0, 1040.0)
                .min_inner_size(1280.0, 800.0)
                .resizable(true)
                .build()?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running dharma desktop shell");
}

#[cfg(test)]
mod tests {
    use super::{build_dashboard_url, DASHBOARD_URL};

    #[test]
    fn dashboard_url_stays_plain_without_api_key() {
        assert_eq!(build_dashboard_url(None), DASHBOARD_URL);
    }

    #[test]
    fn dashboard_url_bootstraps_api_key_via_hash_fragment() {
        assert_eq!(
            build_dashboard_url(Some("alpha beta/123")),
            "http://127.0.0.1:3420/dashboard/command-post#desktop_api_key=alpha%20beta%2F123"
        );
    }
}

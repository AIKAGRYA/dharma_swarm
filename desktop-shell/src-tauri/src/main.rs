#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::path::PathBuf;
use std::process::Command;

use tauri::{WebviewUrl, WebviewWindowBuilder};

const DASHBOARD_BASE_URL: &str = "http://127.0.0.1:3420";
const DEFAULT_DASHBOARD_ROUTE: &str = "/dashboard/command-post";
const DASHBOARD_API_KEY_ENV: &str = "DASHBOARD_API_KEY";
const DASHBOARD_ROUTE_ENV: &str = "DHARMA_DESKTOP_ROUTE";

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

fn resolve_dashboard_route(route_override: Option<&str>) -> &str {
    match route_override.map(str::trim).filter(|value| !value.is_empty()) {
        Some(value) if value.starts_with("/dashboard") => value,
        _ => DEFAULT_DASHBOARD_ROUTE,
    }
}

fn build_dashboard_url(route: &str, api_key: Option<&str>) -> String {
    let base = format!("{DASHBOARD_BASE_URL}{route}");
    match api_key.map(str::trim).filter(|value| !value.is_empty()) {
        Some(value) => format!(
            "{base}#desktop_api_key={}",
            percent_encode_fragment(value)
        ),
        None => base,
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

fn resolve_dashboard_webview_url(
    runtime_started: bool,
    route_override: Option<&str>,
    api_key: Option<&str>,
) -> WebviewUrl {
    if !runtime_started {
        return WebviewUrl::App("index.html".into());
    }
    let route = resolve_dashboard_route(route_override);
    let target = build_dashboard_url(route, api_key);
    let url = target.parse().expect("dashboard URL should be a valid URL");
    WebviewUrl::External(url)
}

fn dashboard_webview_url() -> WebviewUrl {
    let route_override = env::var(DASHBOARD_ROUTE_ENV).ok();
    let api_key = env::var(DASHBOARD_API_KEY_ENV).ok();
    resolve_dashboard_webview_url(
        start_runtime(),
        route_override.as_deref(),
        api_key.as_deref(),
    )
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
    use super::{
        build_dashboard_url, resolve_dashboard_route, resolve_dashboard_webview_url,
        DEFAULT_DASHBOARD_ROUTE,
    };
    use tauri::WebviewUrl;

    #[test]
    fn dashboard_url_stays_plain_without_api_key() {
        assert_eq!(
            build_dashboard_url(DEFAULT_DASHBOARD_ROUTE, None),
            "http://127.0.0.1:3420/dashboard/command-post"
        );
    }

    #[test]
    fn dashboard_url_bootstraps_api_key_via_hash_fragment() {
        assert_eq!(
            build_dashboard_url(DEFAULT_DASHBOARD_ROUTE, Some("alpha beta/123")),
            "http://127.0.0.1:3420/dashboard/command-post#desktop_api_key=alpha%20beta%2F123"
        );
    }

    #[test]
    fn dashboard_route_override_accepts_dashboard_paths() {
        assert_eq!(resolve_dashboard_route(Some("/dashboard/fleet")), "/dashboard/fleet");
    }

    #[test]
    fn dashboard_route_override_rejects_non_dashboard_paths() {
        assert_eq!(resolve_dashboard_route(Some("/api/health")), DEFAULT_DASHBOARD_ROUTE);
        assert_eq!(resolve_dashboard_route(Some("https://example.com")), DEFAULT_DASHBOARD_ROUTE);
    }

    #[test]
    fn dashboard_webview_falls_back_to_local_asset_when_runtime_fails() {
        match resolve_dashboard_webview_url(false, Some("/dashboard/fleet"), Some("secret")) {
            WebviewUrl::App(path) => assert_eq!(path.to_string_lossy(), "index.html"),
            other => panic!("expected App fallback, got {other:?}"),
        }
    }

    #[test]
    fn dashboard_webview_uses_override_and_bootstraps_api_key_when_runtime_is_ready() {
        match resolve_dashboard_webview_url(true, Some("/dashboard/fleet"), Some("alpha beta")) {
            WebviewUrl::External(url) => assert_eq!(
                url.as_str(),
                "http://127.0.0.1:3420/dashboard/fleet#desktop_api_key=alpha%20beta"
            ),
            other => panic!("expected External dashboard URL, got {other:?}"),
        }
    }
}

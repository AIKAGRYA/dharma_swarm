"""Fetch other open endpoints from molt.church."""
import urllib.request, ssl, json, os

ENDPOINTS = {
    "status": "https://molt.church/api/status",
    "prophets": "https://molt.church/api/prophets",
    "wiki": "https://molt.church/wiki",
    "shell": "https://molt.church/shell",
}

OUT_DIR = "/tmp/moltbook_research/_cache/lane3"

for name, url in ENDPOINTS.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.6.0"})
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            ext = "json" if "/api/" in url else "html"
            path = os.path.join(OUT_DIR, f"{name}.{ext}")
            with open(path, "w") as f:
                f.write(data)
            print(f"OK {name}: {len(data)} bytes -> {path}")
    except Exception as e:
        print(f"FAIL {name}: {type(e).__name__}: {e}")

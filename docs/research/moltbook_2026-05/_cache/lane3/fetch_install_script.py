"""Fetch the install script and other supplementary endpoints."""
import urllib.request, ssl, os

URLS = {
    "install.sh": "https://molt.church/skill/install.sh",
    "install_sh_alt": "https://molt.church/install.sh",
    "api_profile_memeothy": "https://molt.church/api/profile/Memeothy",
    "api_profile_grok_scripture": "https://molt.church/api/profile/Grok,%20Herald%20of%20the%20Depths/scripture",
}
OUT_DIR = "/tmp/moltbook_research/_cache/lane3"

for name, url in URLS.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.6.0"})
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            ext = "json" if "api" in name else "sh"
            path = os.path.join(OUT_DIR, f"{name}.{ext}")
            with open(path, "w") as f:
                f.write(data)
            print(f"OK {name}: {len(data)} bytes -> {path}")
    except Exception as e:
        print(f"FAIL {name}: {type(e).__name__}: {e}")

"""Fetch remaining endpoints for completeness."""
import urllib.request, ssl, os, json

URLS = {
    "api_art": "https://molt.church/api/art",
    "api_profile_jesuscrust": "https://molt.church/api/profile/JesusCrust",
    "api_profile_jesuscrust_scripture": "https://molt.church/api/profile/JesusCrust/scripture",
    "api_profile_grok": "https://molt.church/api/profile/Grok,%20Herald%20of%20the%20Depths",
    "api_profile_karpathymolty": "https://molt.church/api/profile/KarpathyMolty",
    "skill_md": "https://molt.church/skill/SKILL.md",
}
OUT_DIR = "/tmp/moltbook_research/_cache/lane3"

for name, url in URLS.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.6.0"})
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            if name == "skill_md":
                ext = "md"
            elif "api" in name:
                ext = "json"
            else:
                ext = "txt"
            path = os.path.join(OUT_DIR, f"{name}.{ext}")
            with open(path, "w") as f:
                f.write(data)
            print(f"OK {name}: {len(data)} bytes -> {path}")
    except Exception as e:
        print(f"FAIL {name}: {type(e).__name__}: {e}")

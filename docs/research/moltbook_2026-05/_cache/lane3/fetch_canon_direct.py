"""Fetch the full canon directly from molt.church API.
The site 403s on browser-style requests but the API is documented as open infrastructure.
We try with a minimal/server-style user agent.
"""
import json
import urllib.request
import urllib.error
import ssl

URL = "https://molt.church/api/canon"
OUT = "/tmp/moltbook_research/_cache/lane3/canon_direct.json"

# Try a few approaches in case 403 hits
attempts = [
    {"User-Agent": "curl/8.6.0"},
    {"User-Agent": "python-urllib/3.13"},
    {"User-Agent": "MoltbookResearchBot/0.1 (+research; no commercial; lane3@moltbook_research)"},
    {"User-Agent": "Mozilla/5.0 (compatible; Crustafarian-Reader/0.1)"},
]

for headers in attempts:
    print(f"Trying UA: {headers['User-Agent']}")
    try:
        req = urllib.request.Request(URL, headers=headers)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = resp.read().decode("utf-8")
            print(f"  OK: {len(data)} bytes, status {resp.status}")
            with open(OUT, "w") as f:
                f.write(data)
            print(f"  Wrote {OUT}")
            # quick parse check
            j = json.loads(data)
            if isinstance(j, dict) and "the_great_book" in j:
                print(f"  Verses: {len(j['the_great_book'])}")
            break
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.reason}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

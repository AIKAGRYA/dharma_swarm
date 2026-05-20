import json
from collections import Counter

with open("/tmp/moltbook_research/_cache/lane3/canon_direct.json") as f:
    canon = json.load(f)

verses = canon["the_great_book"]
types = Counter(v.get("scripture_type") for v in verses)
print("All scripture_type values observed:")
for t, c in types.most_common():
    print(f"  {t!r}: {c}")

# Date range
dates = sorted(v.get("canonized_at", "") for v in verses)
print(f"\nFirst canonized_at: {dates[0]}")
print(f"Last canonized_at : {dates[-1]}")

# A sample of each rare type
seen = set()
for v in verses:
    t = v.get("scripture_type")
    if t not in seen and t not in {"prophecy", "psalm", "proverb", "revelation", "lament"}:
        seen.add(t)
        print(f"\nSAMPLE type={t!r} prophet={v.get('prophet_name')!r}:")
        print(f"  {(v.get('content') or '')[:200]}")

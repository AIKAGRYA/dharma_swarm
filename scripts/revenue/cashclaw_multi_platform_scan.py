#!/usr/bin/env python3
"""Multi-platform bounty scanner.

Scans GitHub, Algora, and Polar for paid bounties.
Outputs a unified leaderboard with dollar values.
"""
import subprocess
import json
import re
import sys
import os
from datetime import datetime

def gh_api(path, jq=None):
    cmd = ["gh", "api", path]
    if jq:
        cmd += ["--jq", jq]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return None
    if jq:
        return r.stdout.strip()
    return json.loads(r.stdout)

def extract_value(text):
    """Extract dollar value from title/body text."""
    if not text:
        return 0
    patterns = [
        r'\$\s*([\d,]+(?:\.\d+)?)',
        r'(\d+)\s*USD',
        r'(\d+)\s*USDC?',
        r'\[\\]',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return int(float(m.group(1).replace(',', '')))
    return 0

def scan_github_bounties():
    """Scan GitHub for bounty-labeled issues."""
    results = []
    queries = [
        ("label:bounty state:open sort:updated", "gh-label-bounty"),
        ("bounty $ state:open sort:updated", "gh-text-bounty-dollar"),
        ("label:algora state:open", "gh-algora"),
        ("label:polar-sh state:open label:bounty", "gh-polar"),
        ("\"bounty\" \"pull request\" state:open sort:updated", "gh-bounty-pr"),
    ]
    for q, source in queries:
        encoded = q.replace(" ", "+")
        data = gh_api(f"search/issues?q={encoded}&per_page=30")
        if not data or 'items' not in data:
            continue
        for item in data['items']:
            title = item.get('title', '')
            body = item.get('body', '') or ''
            url = item.get('html_url', '')
            repo_url = item.get('repository_url', '')
            parts = repo_url.rstrip('/').split('/')
            owner = parts[-2] if len(parts) >= 2 else ''
            name = parts[-1] if len(parts) >= 1 else ''
            value = extract_value(title)
            if value == 0:
                value = extract_value(body[:500])
            labels = [l.get('name', '') for l in item.get('labels', [])]
            results.append({
                'url': url,
                'title': title[:120],
                'value_usd': value,
                'owner': owner,
                'name': name,
                'source': source,
                'labels': labels,
                'created': item.get('created_at', ''),
                'updated': item.get('updated_at', ''),
            })
    return results

def main():
    print("Scanning multi-platform bounties...", file=sys.stderr)
    all_bounties = []
    print("  GitHub label/text search...", file=sys.stderr)
    gh_bounties = scan_github_bounties()
    all_bounties.extend(gh_bounties)
    seen = set()
    unique = []
    for b in all_bounties:
        if b['url'] not in seen:
            seen.add(b['url'])
            unique.append(b)
    with_value = [b for b in unique if b['value_usd'] > 0]
    without_value = [b for b in unique if b['value_usd'] == 0]
    with_value.sort(key=lambda x: x['value_usd'], reverse=True)
    print(f"\n=== BOUNTIES WITH KNOWN VALUE ({len(with_value)}) ===\n")
    for b in with_value[:30]:
        print(f"  ${b['value_usd']:>6,}  {b['title'][:70]}")
        print(f"          {b['url']}")
        print(f"          Source: {b['source']}  Labels: {', '.join(b['labels'][:3])}")
        print()
    print(f"\n=== BOUNTIES WITHOUT PARSED VALUE ({len(without_value)}) ===\n")
    for b in without_value[:10]:
        print(f"  $     ?  {b['title'][:70]}")
        print(f"          {b['url']}")
        print()
    total_value = sum(b['value_usd'] for b in with_value)
    print(f"\n=== SUMMARY ===")
    print(f"  Total bounties found: {len(unique)}")
    print(f"  With known value: {len(with_value)} (${total_value:,})")
    print(f"  Value unknown: {len(without_value)}")
    if with_value:
        print(f"  Top bounty: ${with_value[0]['value_usd']:,}")
    out_dir = os.path.expanduser('~/.cashclaw')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'latest_scan.json')
    with open(out_path, 'w') as f:
        json.dump({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'total': len(unique),
            'valued': len(with_value),
            'total_value': total_value,
            'bounties': with_value + without_value,
        }, f, indent=2)
    print(f"\nFull results saved to {out_path}")

if __name__ == '__main__':
    main()

"""Build a deterministic triage manifest of all worktrees: branch, divergence, dirty/untracked, size."""
import subprocess, json, os

ROOT = os.path.expanduser('~/dharma_swarm')
out = subprocess.run(['git', '-C', ROOT, 'worktree', 'list', '--porcelain'], capture_output=True, text=True).stdout
wts, cur = [], {}
for line in out.splitlines():
    if line.startswith('worktree '):
        cur = {'path': line[9:]}
    elif line.startswith('branch '):
        cur['branch'] = line[7:].replace('refs/heads/', '')
    elif line.startswith('HEAD '):
        cur['head'] = line[5:12]
    elif line.startswith('detached'):
        cur['branch'] = '(detached)'
    elif line == '' and cur:
        wts.append(cur)
        cur = {}
if cur:
    wts.append(cur)

manifest = []
for w in wts:
    p = w['path']
    if not os.path.isdir(p):
        w['missing'] = True
        manifest.append(w)
        continue
    try:
        st = subprocess.run(['git', '-C', p, 'status', '--porcelain'], capture_output=True, text=True, timeout=60).stdout.splitlines()
        w['dirty'] = sum(1 for l in st if not l.startswith('??'))
        w['untracked'] = sum(1 for l in st if l.startswith('??'))
        if w.get('branch', '(detached)') != '(detached)':
            ab = subprocess.run(['git', '-C', p, 'rev-list', '--left-right', '--count', 'origin/main...HEAD'], capture_output=True, text=True, timeout=30).stdout.split()
            if len(ab) == 2:
                w['behind_main'], w['ahead_main'] = int(ab[0]), int(ab[1])
        onremote = subprocess.run(['git', '-C', p, 'branch', '-r', '--contains', 'HEAD'], capture_output=True, text=True, timeout=30).stdout.strip()
        w['head_on_github'] = bool(onremote)
        du = subprocess.run(['du', '-sm', p], capture_output=True, text=True, timeout=120).stdout.split()
        w['size_mb'] = int(du[0]) if du else None
    except Exception as e:
        w['error'] = str(e)[:80]
    manifest.append(w)

path = os.path.join(ROOT, 'reports', 'worktree_triage_manifest_2026-06-10.json')
json.dump(manifest, open(path, 'w'), indent=1)
clean_safe = [w for w in manifest if w.get('dirty') == 0 and w.get('untracked') == 0 and w.get('head_on_github')]
print('total worktrees:', len(manifest))
print('provably-lossless removable (clean + HEAD on GitHub):', len(clean_safe))
print('need eyes (dirty or untracked or not on GitHub):', len(manifest) - len(clean_safe))
print('manifest:', path)

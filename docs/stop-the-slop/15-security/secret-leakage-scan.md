---
id: secret-leakage-scan
version: 0.0.1
theme: 15-security
status: tested
invariant: >
  Secrets must never enter source, logs, error messages, or responses. Detection
  routes to a real entropy/rule scanner over the FULL history (a secret deleted in
  HEAD still lives in git history and must be rotated, not just removed) — never an
  ad-hoc regex. The only safe response to a found secret is ROTATE-then-purge;
  deleting the line is not enough.
lineage:
  - "Kerckhoffs — security rests on the key, so the key's secrecy is the whole game"
  - "Saltzer & Schroeder 1975 — fail-safe defaults; least privilege"
  - "route to ground truth: gitleaks / trufflehog over full history, not regex"
ground_truth_tools: ["gitleaks / trufflehog (full history)", "the repo's own secret-scan CI", "log/response sinks reachable by secrets"]
returns_clean: true
---

## Prompt

> Scan for **leaked secrets**. The invariant (Kerckhoffs): the key's secrecy is the
> whole game, so a leaked credential is total compromise. **Route to a real scanner**
> (gitleaks / trufflehog) over the **full git history** — a secret removed from HEAD
> still lives in history and is still compromised. Do not hand-roll regex; do not
> scan only the working tree.
>
> **Find:** committed credentials/keys/tokens (history included); secrets reaching
> **logs**, **error messages**, or **API responses** (the runtime leak paths a
> file-scan misses). For each: location, secret type, and the **rotate-first**
> remediation (rotate the credential, *then* purge history) — deletion alone leaves
> a live, exposed secret.
>
> **Return clean** if the scanner is green and no secret reaches a log/response
> sink — and confirm the scanner actually ran (a missing scanner is a finding:
> "secrets UNASSESSED — no gitleaks").

## Why it's built this way

Regex secret-hunting is the slop version — high false-negative, working-tree-only.
The disciplined move is the dedicated entropy/rule scanner over full history
(ground truth) plus the runtime sink check (secrets in logs/responses), and the
**rotate-then-purge** remediation, because Kerckhoffs means a seen secret is burned
regardless of whether you delete the line.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **Scanner present (good):** the repo wires `gitleaks` — `.github/workflows/
  gitleaks.yml` + a `make gitleaks` target. So secret scanning is **already routed
  to ground truth** in CI, not left to vibes. (There's also a tracked
  `gitleaks-baseline-*.json`, i.e. a managed allow-list.)
- **Disciplined output:** "Secret scanning is wired (gitleaks, CI + make). Run
  `make gitleaks` for the current verdict; review the baseline allow-list for stale
  entries. Separately, audit log/response sinks: confirm `api_key`/token values are
  never interpolated into a log line or error response (the runtime path gitleaks
  doesn't cover)."

**Return clean** on the tooling axis (present and wired); the open item is the
runtime-sink audit, named honestly rather than asserted clean.

## Changelog

- **v0.0.1** (2026-06-25) — secret-scan routed to gitleaks/trufflehog over full
  history + runtime-sink check + rotate-then-purge remediation (Kerckhoffs/Saltzer–
  Schroeder). Tested on `dharma_swarm/`: gitleaks already wired in CI (return-clean
  on tooling); flagged the log/response-sink audit as the honest open item.

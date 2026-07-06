# MIKE_PAT Migration Note

Status: read-only migration note. Records a token least-privilege change that
needs operator secrets to execute. No code in this PR performs the migration.

Owner of: the written rationale and steps for replacing the long-lived
`MIKE_PAT` secret used by the automerge lane.

## What MIKE_PAT is today

`.github/workflows/automerge.yml` reads a repository secret `MIKE_PAT` into the
`evaluate` job environment and uses it to dispatch
`.github/workflows/codex-mention-router.yml`:

```
MIKE_PAT: ${{ secrets.MIKE_PAT }}
...
GH_TOKEN="${MIKE_PAT:-$GH_TOKEN}" gh workflow run codex-mention-router.yml ...
```

The built-in `GITHUB_TOKEN` cannot create a new workflow run, so a personal
access token is used only to trigger the router dispatch. In practice this PAT
is long-lived and carries a broad scope (contents, pull-requests, and
actions:write) so that one credential covers every path Mike might take.

## Why this is a least-privilege gap

A long-lived PAT with contents plus pull-request plus actions-write scope is a
standing credential: it does not expire on its own, it is bound to a human
account rather than the repository, and its blast radius is the union of every
scope any lane ever needed. The OpenSSF Scorecard token-permissions check flags
exactly this pattern. The remediation is a short-lived, repository-scoped token
minted per run.

## Proposed change (operator decision)

Replace the long-lived `MIKE_PAT` with a short-lived token minted from a
GitHub App installation, scoped to only the permissions the dispatch needs:

- Create or reuse a GitHub App owned by the org, installed on this repository.
- Grant the App the minimum installation permissions: `actions: write` (to
  dispatch the router workflow), `contents: read`, and `pull_requests: read`.
  Add `contents: write` and `pull_requests: write` only if a later step is
  proven to need them; start without.
- In `automerge.yml`, mint an installation token at job start from the App id
  and private key (stored as secrets `MIKE_APP_ID` and `MIKE_APP_PRIVATE_KEY`),
  and use that token in place of `MIKE_PAT`. The token expires within the hour,
  so a leak has a bounded window.
- After the App path is verified green on a real dispatch, delete the
  `MIKE_PAT` secret.

This change is not performed in this PR because it requires creating a GitHub
App and adding new repository secrets, both of which need operator access to
org settings and the secret store. This note is the hand-off.

## Operator decision items

1. Approve creating (or reusing) a GitHub App for the automerge dispatch, with
   the minimum permissions listed above.
2. Add `MIKE_APP_ID` and `MIKE_APP_PRIVATE_KEY` as repository secrets.
3. Approve deleting the `MIKE_PAT` secret once the App path is verified.

Until these are done, `automerge.yml` keeps using `MIKE_PAT` and falls back to
`GITHUB_TOKEN` (a no-op dispatch) when the secret is absent, so nothing breaks
in the interim.

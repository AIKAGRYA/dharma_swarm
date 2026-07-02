# Redaction and Privacy Rules

Role: active report for `DharmaVerifier-Ranker v0` data prep  
Implementation: `dharma_swarm/verifier_ranker_v0/redaction.py`

## Policy

Fail closed. If a field or span may contain private material and the pipeline
cannot prove it is safe, the record is quarantined or stored as hash-only.

## Exact Redaction Rules

| Category | Rule | Replacement |
|---|---|---|
| Paths | Redact `/Users/<name>/...`, `/home/<name>/...`, and Windows user paths. | `<REDACTED_PATH:sha256:...>` |
| Usernames | Redacted as part of home paths. Standalone usernames in private context must be hashed through field-level redaction. | hash-only |
| Emails | Redact all RFC-like email spans. | `<REDACTED_EMAIL:sha256:...>` |
| IPv4 addresses | Redact all IPv4 spans. | `<REDACTED_IP:sha256:...>` |
| Tokens and keys | Redact explicit `api_key`, `secret`, `token`, `password`, `bearer`, `authorization`, and known key prefixes. | `<REDACTED_TOKEN...>` or `<REDACTED_CREDENTIAL...>` |
| URLs | Redact full URL, including credentials, path, and query. | `<REDACTED_URL:sha256:...>` |
| Account IDs | Redact account/org/tenant/project/workspace-like ids. | `<REDACTED_ACCOUNT_ID:sha256:...>` |
| Long high-entropy strings | Treat as uncertain sensitive material. | `<REDACTED_TOKEN_LIKE:sha256:...>` and `fail_closed=true` |
| Raw messages | Field-level hash only for `body`, `raw_message`, `raw_message_body`, `message_body`. | `<REDACTED_FIELD:...>` |
| Provider payloads | Field-level hash only for `payload`, `payload_json`, `request_json`, `response_json`, `provider_payload`. | `<REDACTED_FIELD:...>` |
| Error strings | Field-level hash only for `error_detail`, `error_string`, `stderr`, `stdout`. | `<REDACTED_FIELD:...>` |
| Prompts/responses/content | Field-level hash only for `prompt`, `response`, `raw_response`, `content`. | `<REDACTED_FIELD:...>` |

## Privacy Tags

Allowed privacy tags in graph records:

- `public`
- `internal_redacted`
- `internal_hash_only`
- `private_metadata`
- `quarantine_sensitive`
- `excluded_raw_secret`
- `excluded_raw_message`
- `excluded_provider_payload`

Rules:

- Any record containing a field-level replacement must include `internal_hash_only` or `quarantine_sensitive`.
- Any record derived from `messages.body` must be hash-only in v0.
- Any provider request/response payload must be hash-only in v0 unless separately reviewed.
- Existing generic training JSONL remains `quarantine_sensitive` until redaction and relabelling pass.

## Audit Checks

Required checks before export:

1. Run redaction on every string field.
2. Run field-level hash redaction on raw message, prompt, response, provider payload, stdout/stderr, and error-detail fields.
3. Reject records with unredacted email, local path, URL, IP, known token prefix, or credential assignment.
4. Reject records with high-entropy token-like spans unless explicitly tagged `quarantine_sensitive`.
5. Verify all exported rows include `privacy_tags`.
6. Hash-lock source files and DB snapshots used for the export.
7. Emit export receipt with row counts, excluded-row counts, and redaction findings by category.

## Pipeline Commands

Current implemented checks:

```bash
pytest -q tests/test_verifier_ranker_v0.py
```

Current implemented inventory:

```bash
./.venv/bin/python scripts/agentops/verifier_ranker_v0_inventory.py
```

Required next implementation step:

```text
Build an exporter that maps selected surfaces to graph JSONL rows, applies
redact_record(), validates every row against the graph schema, and writes
row-count and redaction receipts.
```

## Non-Negotiables

- No raw secrets.
- No raw private message bodies.
- No unredacted provider payloads.
- No unredacted home-state logs.
- No training export from `~/.dharma/datasets` until redaction and relabel checks pass.

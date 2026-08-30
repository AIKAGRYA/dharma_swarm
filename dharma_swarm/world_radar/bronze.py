"""Bronze intake for the intelligence supply-chain slice.

This module is deliberately narrow. It admits sanctioned external signals into
content-addressed raw receipts, performs cheap MinHash/LSH dedupe, and emits a
verifier-boundary artifact for the decorrelated frontier council. It does not
summarize, verify, synthesize, or apply code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.world_radar.io_utils import (
    append_jsonl_once,
    read_json,
    utc_now_iso,
    write_json_atomic,
)

RAW_RECEIPT_SCHEMA = "intelligence_supply_chain.raw_receipt.v1"
VERIFIER_BOUNDARY_SCHEMA = "intelligence_supply_chain.verifier_boundary.v1"
FETCHER_AGENT_ID = "dharma_swarm.world_radar.bronze"
BOUNDARY_CONTRACT = "frontier_council.input.v1"

SUPPORTED_SOURCE_TYPES = {
    "arxiv",
    "hacker_news",
    "operator_drop",
    "youtube",
}

DEFAULT_CORROBORATION_K = 2
MINHASH_SEEDS = tuple(range(32))
MINHASH_BAND_SIZE = 4
NEAR_DUPLICATE_JACCARD = 0.86


class BronzeIngestError(ValueError):
    """Raised when a raw signal cannot be admitted into Bronze."""


@dataclass(frozen=True)
class BronzeIngestResult:
    """Compact receipt for one Bronze intake pass."""

    queued_receipts: int
    duplicate_receipts: int
    boundary_written: int
    receipt_paths: tuple[str, ...]
    boundary_paths: tuple[str, ...]
    index_path: str
    ledger_path: str
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def ingest_rows_to_bronze(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    state_dir: Path | str | None = None,
    max_items: int = 10,
    timeout_s: int = 10,
    fetched_at: str | None = None,
) -> BronzeIngestResult:
    """Admit sanctioned raw rows and emit verifier-boundary artifacts.

    The rows are treated as untrusted data. A duplicate row is a no-op: no new
    receipt and no new boundary item are written.
    """
    state = _state_dir(state_dir)
    root = bronze_root(state)
    receipt_root = raw_receipt_dir(state)
    boundary_root = verifier_boundary_dir(state)
    ledger_path = verifier_boundary_ledger_path(state)
    index_path = dedupe_index_path(state)
    index = _load_index(index_path)
    now = fetched_at or utc_now_iso()
    receipt_paths: list[str] = []
    boundary_paths: list[str] = []
    errors: list[str] = []
    duplicate_count = 0

    root.mkdir(parents=True, exist_ok=True)
    for row in list(rows)[: max(0, max_items)]:
        try:
            normalized = _normalize_row(row, fetched_at=now)
            content_hash = _content_hash(normalized)
            source_key = _source_key(normalized)
            minhash = _minhash_signature(_receipt_text(normalized))
            buckets = _lsh_buckets(minhash)
            duplicate_of = _duplicate_of(
                index,
                content_hash=content_hash,
                source_key=source_key,
                buckets=buckets,
                text=_receipt_text(normalized),
            )
            if duplicate_of:
                duplicate_count += 1
                continue
            receipt = _raw_receipt(
                normalized,
                content_hash=content_hash,
                source_key=source_key,
                minhash=minhash,
                buckets=buckets,
                max_items=max_items,
                timeout_s=timeout_s,
            )
            receipt_path = receipt_root / f"{receipt['receipt_id']}.json"
            write_json_atomic(receipt_path, receipt)
            boundary = _verifier_boundary(receipt, receipt_path=receipt_path)
            boundary_path = boundary_root / f"{boundary['boundary_id']}.json"
            write_json_atomic(boundary_path, boundary)
            append_jsonl_once(ledger_path, boundary, key_field="boundary_id")
            receipt_paths.append(str(receipt_path))
            boundary_paths.append(str(boundary_path))
            _record_index_entry(
                index,
                content_hash=content_hash,
                source_key=source_key,
                buckets=buckets,
                text=_receipt_text(normalized),
            )
        except BronzeIngestError as exc:
            errors.append(str(exc))
    write_json_atomic(index_path, index)
    return BronzeIngestResult(
        queued_receipts=len(receipt_paths),
        duplicate_receipts=duplicate_count,
        boundary_written=len(boundary_paths),
        receipt_paths=tuple(receipt_paths),
        boundary_paths=tuple(boundary_paths),
        index_path=str(index_path),
        ledger_path=str(ledger_path),
        errors=tuple(errors),
    )


def ingest_operator_drops_to_bronze(
    *,
    state_dir: Path | str | None = None,
    max_items: int = 10,
    timeout_s: int = 10,
) -> BronzeIngestResult:
    """Admit existing operator world drops into Bronze."""
    state = _state_dir(state_dir)
    path = state / "meta" / "world_operator_drops.jsonl"
    rows = _read_jsonl(path)
    return ingest_rows_to_bronze(
        rows,
        state_dir=state,
        max_items=max_items,
        timeout_s=timeout_s,
    )


def fetch_hn_algolia_rows(
    *,
    query: str,
    limit: int = 1,
    timeout_s: int = 10,
) -> list[dict[str, Any]]:
    """Fetch one sanctioned Hacker News Algolia page as raw rows."""
    bounded_limit = max(1, min(int(limit), 20))
    url = (
        "https://hn.algolia.com/api/v1/search_by_date"
        f"?query={quote_plus(query)}&tags=story&hitsPerPage={bounded_limit}"
    )
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "dharma-swarm-bronze-ingest/1.0",
        },
    )
    with urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - sanctioned public API.
        payload = json.loads(response.read().decode("utf-8"))
    hits = payload.get("hits", []) if isinstance(payload, dict) else []
    rows: list[dict[str, Any]] = []
    fetched_at = utc_now_iso()
    for hit in hits[:bounded_limit]:
        if not isinstance(hit, dict):
            continue
        object_id = str(hit.get("objectID") or hit.get("story_id") or "").strip()
        item_url = str(hit.get("url") or "").strip()
        if not item_url and object_id:
            item_url = f"https://news.ycombinator.com/item?id={object_id}"
        title = str(hit.get("title") or hit.get("story_title") or "").strip()
        story_text = str(hit.get("story_text") or hit.get("comment_text") or "").strip()
        rows.append(
            {
                "id": object_id or _short_hash(json.dumps(hit, sort_keys=True)),
                "source": "hacker_news",
                "source_type": "hn_algolia_api",
                "title": title,
                "description": story_text,
                "url": item_url,
                "keywords": ["hacker_news", "public_signal"],
                "observed_at": str(hit.get("created_at") or fetched_at),
                "fetch_method": "hn_algolia_api",
                "license": "hn_algolia_public_api_terms",
                "metadata": {
                    "algolia_query": query,
                    "points": hit.get("points"),
                    "num_comments": hit.get("num_comments"),
                    "author": hit.get("author"),
                },
            }
        )
    return rows


def ingest_hn_algolia_to_bronze(
    *,
    query: str,
    state_dir: Path | str | None = None,
    limit: int = 1,
    timeout_s: int = 10,
) -> BronzeIngestResult:
    """Fetch a bounded HN Algolia page and admit it into Bronze."""
    rows = fetch_hn_algolia_rows(query=query, limit=limit, timeout_s=timeout_s)
    return ingest_rows_to_bronze(
        rows,
        state_dir=state_dir,
        max_items=limit,
        timeout_s=timeout_s,
    )


def bronze_root(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / "meta" / "intelligence_supply_chain" / "bronze"


def raw_receipt_dir(state_dir: Path | str | None = None) -> Path:
    return bronze_root(state_dir) / "raw_receipts"


def verifier_boundary_dir(state_dir: Path | str | None = None) -> Path:
    return bronze_root(state_dir) / "verifier_boundary"


def verifier_boundary_ledger_path(state_dir: Path | str | None = None) -> Path:
    return bronze_root(state_dir) / "verifier_boundary.jsonl"


def dedupe_index_path(state_dir: Path | str | None = None) -> Path:
    return bronze_root(state_dir) / "dedupe_index.json"


def _state_dir(state_dir: Path | str | None) -> Path:
    return Path(state_dir).expanduser() if state_dir is not None else dharma_state_dir()


def _normalize_row(row: dict[str, Any], *, fetched_at: str) -> dict[str, Any]:
    source_type = _canonical_source_type(row)
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise BronzeIngestError(f"unsupported_source_type:{source_type or 'unknown'}")
    title = _clean_text(str(row.get("title") or row.get("headline") or "")).strip()
    url = str(row.get("url") or row.get("source_url") or "").strip()
    if not title:
        raise BronzeIngestError("missing_title")
    if not _is_http_url(url):
        raise BronzeIngestError("missing_or_unsupported_source_url")
    description = _clean_text(str(row.get("description") or row.get("summary") or ""))
    observed_at = str(row.get("observed_at") or row.get("created_at") or fetched_at)
    return {
        "source_type": source_type,
        "source": _source_name(row, source_type),
        "source_item_id": str(row.get("id") or row.get("objectID") or _short_hash(url)).strip(),
        "title": title[:500],
        "description": description[:5000],
        "url": url,
        "keywords": _string_list(row.get("keywords") or row.get("tags") or []),
        "observed_at": observed_at,
        "fetched_at": fetched_at,
        "fetch_method": _fetch_method(row, source_type),
        "license": _license(row, source_type),
        "metadata": _metadata(row),
    }


def _canonical_source_type(row: dict[str, Any]) -> str:
    raw = " ".join(
        str(row.get(key) or "")
        for key in ("source", "raw_source", "source_type", "fetch_method")
    ).lower()
    url = str(row.get("url") or row.get("source_url") or "")
    if "operator_drop" in raw or raw.strip() in {"operator", "manual"}:
        return "operator_drop"
    if "hacker" in raw or "hn_algolia" in raw or _is_hacker_news_url(url):
        return "hacker_news"
    if "arxiv" in raw or _is_arxiv_url(url):
        return "arxiv"
    if "youtube" in raw or "youtube_atom" in raw or _is_youtube_url(url):
        return "youtube"
    return raw.split()[0] if raw.split() else ""


def _source_name(row: dict[str, Any], source_type: str) -> str:
    raw = str(row.get("source") or row.get("raw_source") or "").strip()
    return raw or source_type


def _fetch_method(row: dict[str, Any], source_type: str) -> str:
    raw = str(row.get("fetch_method") or "").strip()
    if raw:
        return raw
    if source_type == "operator_drop":
        return "operator_drop_attested_url"
    if source_type == "hacker_news":
        return "hn_algolia_api"
    if source_type == "youtube":
        return "youtube_atom_feed"
    return "arxiv_public_api"


def _license(row: dict[str, Any], source_type: str) -> str:
    raw = str(row.get("license") or row.get("licence") or "").strip()
    if raw:
        return raw
    if source_type == "operator_drop":
        return "operator_attested_public_source"
    if source_type == "hacker_news":
        return "hn_algolia_public_api_terms"
    if source_type == "youtube":
        return "youtube_standard_feeds_terms"
    return "arxiv_metadata_public_terms"


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}
    allowed = {
        "algolia_query",
        "author",
        "cascade_for",
        "category",
        "num_comments",
        "points",
        "raw_source",
        "source_type",
    }
    return {key: metadata[key] for key in sorted(metadata) if key in allowed}


def _raw_receipt(
    normalized: dict[str, Any],
    *,
    content_hash: str,
    source_key: str,
    minhash: list[int],
    buckets: list[str],
    max_items: int,
    timeout_s: int,
) -> dict[str, Any]:
    receipt_id = f"isc_raw_{content_hash[:24]}"
    entity_id = f"sha256:{content_hash}"
    activity_id = f"fetch:{receipt_id}"
    return {
        "schema_version": RAW_RECEIPT_SCHEMA,
        "receipt_id": receipt_id,
        "content_hash": entity_id,
        "source": normalized["source"],
        "source_type": normalized["source_type"],
        "source_url": normalized["url"],
        "source_item_id": normalized["source_item_id"],
        "fetch_method": normalized["fetch_method"],
        "license": normalized["license"],
        "observed_at": normalized["observed_at"],
        "fetched_at": normalized["fetched_at"],
        "payload": {
            "title": normalized["title"],
            "description": normalized["description"],
            "url": normalized["url"],
            "keywords": normalized["keywords"],
            "metadata": normalized["metadata"],
        },
        "untrusted_text": {
            "title": normalized["title"],
            "description": normalized["description"],
        },
        "instruction_policy": {
            "payload_is_untrusted_data": True,
            "payload_must_not_be_executed": True,
            "payload_must_not_override_system_policy": True,
        },
        "prov": {
            "standard": "W3C-PROV-compatible-minimal",
            "entity": {
                "id": entity_id,
                "type": "raw_external_signal",
            },
            "activity": {
                "id": activity_id,
                "type": "fetch",
                "method": normalized["fetch_method"],
                "started_at": normalized["fetched_at"],
                "ended_at": normalized["fetched_at"],
            },
            "agent": {
                "id": FETCHER_AGENT_ID,
                "type": "software_agent",
            },
            "wasGeneratedBy": {
                "entity": entity_id,
                "activity": activity_id,
            },
            "wasAssociatedWith": {
                "activity": activity_id,
                "agent": FETCHER_AGENT_ID,
            },
        },
        "dedupe": {
            "decision": "new",
            "source_key": source_key,
            "minhash_signature": minhash,
            "lsh_buckets": buckets,
            "method": "minhash_lsh_before_embedding",
        },
        "corroboration": {
            "required_k": DEFAULT_CORROBORATION_K,
            "observed_k": 1,
            "status": "single_source_pending",
            "independent_source_urls": [normalized["url"]],
        },
        "budget": {
            "max_items": max_items,
            "timeout_s": timeout_s,
            "frontier_model_used": False,
            "usd_spend": 0.0,
        },
    }


def _verifier_boundary(receipt: dict[str, Any], *, receipt_path: Path) -> dict[str, Any]:
    content_hash = str(receipt["content_hash"])
    payload = dict(receipt["payload"])
    boundary_id = f"frontier_council_candidate_{content_hash.replace('sha256:', '')[:24]}"
    return {
        "schema_version": VERIFIER_BOUNDARY_SCHEMA,
        "boundary_id": boundary_id,
        "status": "awaiting_decorrelated_verifier",
        "verifier_interface": BOUNDARY_CONTRACT,
        "source_receipt_id": receipt["receipt_id"],
        "content_hash": content_hash,
        "source_type": receipt["source_type"],
        "source_url": receipt["source_url"],
        "title": payload.get("title", ""),
        "claim": {
            "kind": "raw_external_signal_ingested",
            "text": payload.get("title", ""),
            "claim_is_unverified": True,
        },
        "evidence": {
            "raw_receipt_path": str(receipt_path),
            "raw_receipt_schema": receipt["schema_version"],
            "content_hash": content_hash,
            "prov_entity": receipt["prov"]["entity"]["id"],
            "source_url": receipt["source_url"],
        },
        "guardrails": {
            "source_text_is_untrusted": True,
            "frontier_model_touched_raw_firehose": False,
            "candidate_may_not_be_applied_without_verifier_receipt": True,
            "predefined_quality_metric_required_before_apply": True,
            "required_corroboration_k": DEFAULT_CORROBORATION_K,
            "self_signed_runtime_verdict_allowed": False,
        },
        "lineage": {
            "signal": content_hash,
            "raw_receipt": receipt["receipt_id"],
            "hypothesis": "",
            "implementation": "",
            "ablation": "",
            "kept_claim": "",
        },
        "not_applied": True,
        "next_action": "frontier_council_cross_falsify_then_define_scorable_task",
        "created_at": utc_now_iso(),
    }


def _content_hash(normalized: dict[str, Any]) -> str:
    payload = {
        "source_type": normalized["source_type"],
        "source_item_id": normalized["source_item_id"],
        "title": normalized["title"],
        "description": normalized["description"],
        "url": normalized["url"],
        "observed_at": normalized["observed_at"],
    }
    return _short_hash(json.dumps(payload, sort_keys=True, separators=(",", ":")), length=64)


def _source_key(normalized: dict[str, Any]) -> str:
    seed = f"{normalized['source_type']}|{normalized['url']}|{normalized['source_item_id']}"
    return _short_hash(seed, length=32)


def _receipt_text(normalized: dict[str, Any]) -> str:
    return " ".join(
        str(normalized.get(key) or "")
        for key in ("title", "description", "url", "source_type")
    )


def _load_index(path: Path) -> dict[str, Any]:
    data = read_json(path, default={})
    if not isinstance(data, dict):
        data = {}
    return {
        "schema_version": "intelligence_supply_chain.bronze_dedupe_index.v1",
        "content_hashes": dict(data.get("content_hashes") or {}),
        "source_keys": dict(data.get("source_keys") or {}),
        "lsh_buckets": dict(data.get("lsh_buckets") or {}),
        "tokens": dict(data.get("tokens") or {}),
    }


def _duplicate_of(
    index: dict[str, Any],
    *,
    content_hash: str,
    source_key: str,
    buckets: list[str],
    text: str,
) -> str:
    if content_hash in index["content_hashes"]:
        return content_hash
    if source_key in index["source_keys"]:
        return str(index["source_keys"][source_key])
    tokens = set(_tokens(text))
    for bucket in buckets:
        for candidate_hash in index["lsh_buckets"].get(bucket, []):
            candidate_tokens = set(index["tokens"].get(candidate_hash, []))
            if candidate_tokens and _jaccard(tokens, candidate_tokens) >= NEAR_DUPLICATE_JACCARD:
                return str(candidate_hash)
    return ""


def _record_index_entry(
    index: dict[str, Any],
    *,
    content_hash: str,
    source_key: str,
    buckets: list[str],
    text: str,
) -> None:
    index["content_hashes"][content_hash] = {
        "recorded_at": utc_now_iso(),
        "source_key": source_key,
    }
    index["source_keys"][source_key] = content_hash
    index["tokens"][content_hash] = sorted(set(_tokens(text)))[:400]
    for bucket in buckets:
        bucket_rows = list(index["lsh_buckets"].get(bucket, []))
        if content_hash not in bucket_rows:
            bucket_rows.append(content_hash)
        index["lsh_buckets"][bucket] = bucket_rows[-50:]


def _minhash_signature(text: str) -> list[int]:
    shingles = _shingles(_tokens(text), size=3)
    if not shingles:
        return [0 for _ in MINHASH_SEEDS]
    signature: list[int] = []
    for seed in MINHASH_SEEDS:
        values = (
            int(_short_hash(f"{seed}:{shingle}", length=16), 16)
            for shingle in shingles
        )
        signature.append(min(values))
    return signature


def _lsh_buckets(signature: list[int]) -> list[str]:
    buckets: list[str] = []
    for offset in range(0, len(signature), MINHASH_BAND_SIZE):
        band = signature[offset : offset + MINHASH_BAND_SIZE]
        if len(band) != MINHASH_BAND_SIZE:
            continue
        buckets.append(_short_hash("|".join(str(value) for value in band), length=16))
    return buckets


def _shingles(tokens: list[str], *, size: int) -> list[str]:
    if len(tokens) < size:
        return tokens
    return [" ".join(tokens[idx : idx + size]) for idx in range(0, len(tokens) - size + 1)]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\x00", " ").split())


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _is_http_url(value: str) -> bool:
    return value.startswith("https://") or value.startswith("http://")


def _url_hostname(value: str) -> str:
    try:
        return (urlparse(value).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _is_hacker_news_url(value: str) -> bool:
    return _url_hostname(value) == "news.ycombinator.com"


def _is_arxiv_url(value: str) -> bool:
    host = _url_hostname(value)
    return host == "arxiv.org" or host.endswith(".arxiv.org")


def _is_youtube_url(value: str) -> bool:
    host = _url_hostname(value)
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def _short_hash(value: str, *, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


__all__ = [
    "BOUNDARY_CONTRACT",
    "BronzeIngestError",
    "BronzeIngestResult",
    "RAW_RECEIPT_SCHEMA",
    "VERIFIER_BOUNDARY_SCHEMA",
    "bronze_root",
    "dedupe_index_path",
    "fetch_hn_algolia_rows",
    "ingest_hn_algolia_to_bronze",
    "ingest_operator_drops_to_bronze",
    "ingest_rows_to_bronze",
    "raw_receipt_dir",
    "verifier_boundary_dir",
    "verifier_boundary_ledger_path",
]

"""Read-only source adapters for CashClaw live intake.

Adapters turn approved public exports or allowlisted HTTPS reads into source
items and receipts. They do not log in, scrape private pages, send outreach, or
mutate any external system.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dharma_swarm.revenue.live_intake_models import (
    LiveIntakeAdapterReceipt,
    LiveIntakeExtractionMethod,
    LiveIntakeFreshness,
    LiveIntakeRiskLevel,
    LiveIntakeSourceConfig,
    LiveIntakeSourceItem,
    LiveIntakeSourceType,
    live_intake_content_hash,
    live_intake_id,
)


LIVE_INTAKE_ENV = "DHARMA_CASHCLAW_ALLOW_LIVE_INTAKE"
TRUTHY = {"1", "true", "yes", "y", "on"}


@dataclass
class LiveIntakeAdapterResult:
    """Adapter output plus receipt metadata."""

    source_config: LiveIntakeSourceConfig
    source_items: list[LiveIntakeSourceItem] = field(default_factory=list)
    receipt: LiveIntakeAdapterReceipt | None = None
    errors: list[str] = field(default_factory=list)
    blocked: bool = False
    network_read_performed: bool = False


def load_source_configs(path: str | Path) -> list[LiveIntakeSourceConfig]:
    """Load source configs from a JSON file."""

    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    records = payload.get("sources", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("source config file must contain a list or {'sources': [...]}")
    return [LiveIntakeSourceConfig(**record) for record in records if isinstance(record, dict)]


def local_fixture_config(path: str | Path, *, label: str = "") -> LiveIntakeSourceConfig:
    """Build a disabled-network config for a local fixture/export file."""

    fixture_path = Path(path).expanduser()
    return LiveIntakeSourceConfig(
        source_config_id=live_intake_id("lisrc", ["local_fixture", fixture_path.as_posix()]),
        source_type=LiveIntakeSourceType.LOCAL_FIXTURE,
        url=f"artifact://cashclaw-live-intake/{fixture_path.name}",
        label=label or fixture_path.stem,
        adapter_name="local_fixture",
        extraction_method=LiveIntakeExtractionMethod.STRUCTURED_PARSE,
        license_risk=LiveIntakeRiskLevel.LOW,
        terms_risk=LiveIntakeRiskLevel.LOW,
        local_path=fixture_path.as_posix(),
        network_enabled=False,
        notes="Local operator-provided fixture/export. Not live buyer proof by itself.",
    )


def go_archive_config(path: str | Path, *, label: str = "") -> LiveIntakeSourceConfig:
    """Build a read-only config for a Go world_scout archive_index.jsonl."""

    index_path = Path(path).expanduser()
    return LiveIntakeSourceConfig(
        source_config_id=live_intake_id("lisrc", ["go_archive", index_path.as_posix()]),
        source_type=LiveIntakeSourceType.GO_ARCHIVE,
        url=f"artifact://go-world-archive/{index_path.name}",
        label=label or "Go world archive evidence",
        adapter_name="go_archive_index",
        extraction_method=LiveIntakeExtractionMethod.STRUCTURED_PARSE,
        license_risk=LiveIntakeRiskLevel.UNKNOWN,
        terms_risk=LiveIntakeRiskLevel.UNKNOWN,
        local_path=index_path.as_posix(),
        network_enabled=False,
        notes="Local Go archive index. Capture integrity is not source trust.",
    )


def read_source(config: LiveIntakeSourceConfig, *, allow_network: bool = False, max_items: int = 100) -> LiveIntakeAdapterResult:
    """Read one source config with strict network and terms gates."""

    started = _utc_now_iso()
    try:
        if not config.enabled:
            return _blocked_result(config, started, "source_disabled")
        if config.source_type == LiveIntakeSourceType.LOCAL_FIXTURE:
            return _read_local_fixture(config, started=started, max_items=max_items)
        if config.source_type == LiveIntakeSourceType.GO_ARCHIVE:
            return _read_go_archive_index(config, started=started, max_items=max_items)
        if config.source_type in {LiveIntakeSourceType.REDDIT, LiveIntakeSourceType.YOUTUBE} and not config.network_enabled:
            return _blocked_result(config, started, "terms_sensitive_source_disabled_without_export_or_approved_api")
        return _read_network_source(config, started=started, allow_network=allow_network, max_items=max_items)
    except Exception as exc:  # noqa: BLE001
        return _blocked_result(config, started, f"source_read_failed:{exc}")


def _read_local_fixture(config: LiveIntakeSourceConfig, *, started: str, max_items: int) -> LiveIntakeAdapterResult:
    path = Path(config.local_path).expanduser()
    if not path.exists() or not path.is_file():
        return _blocked_result(config, started, f"local_fixture_missing:{path}")
    raw = _read_file_with_cap(path, config.max_bytes)
    records = _fixture_records(raw, path.suffix.lower())
    items = [
        _source_item_from_record(config, record, idx=idx, fallback_url=config.url)
        for idx, record in enumerate(records[:max_items])
    ]
    receipt = _receipt(
        config,
        started=started,
        items_seen=len(records),
        source_items_emitted=len(items),
        content_hash=live_intake_content_hash(raw),
    )
    return LiveIntakeAdapterResult(source_config=config, source_items=items, receipt=receipt)


def _read_go_archive_index(config: LiveIntakeSourceConfig, *, started: str, max_items: int) -> LiveIntakeAdapterResult:
    index_path = Path(config.local_path).expanduser()
    if not index_path.exists() or not index_path.is_file():
        return _blocked_result(config, started, f"go_archive_index_missing:{index_path}")
    raw = _read_file_with_cap(index_path, config.max_bytes)
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    items: list[LiveIntakeSourceItem] = []
    skipped = 0
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            skipped += 1
            continue
        item = _source_item_from_go_archive_entry(config, row, idx=idx)
        if item is None:
            skipped += 1
            continue
        items.append(item)
        if len(items) >= max_items:
            break
    receipt = _receipt(
        config,
        started=started,
        items_seen=len(rows),
        source_items_emitted=len(items),
        content_hash=live_intake_content_hash(raw),
        warnings=[f"go_archive_rows_skipped:{skipped}"] if skipped else None,
    )
    return LiveIntakeAdapterResult(source_config=config, source_items=items, receipt=receipt)


def _read_network_source(
    config: LiveIntakeSourceConfig,
    *,
    started: str,
    allow_network: bool,
    max_items: int,
) -> LiveIntakeAdapterResult:
    gate_error = _network_gate_error(config, allow_network=allow_network)
    if gate_error:
        return _blocked_result(config, started, gate_error)
    req = Request(
        config.url,
        headers={"Accept": "application/json,text/plain,text/markdown,*/*", "User-Agent": "dharma-cashclaw-live-intake/0.1"},
    )
    with urlopen(req, timeout=15) as resp:
        raw_bytes = resp.read(config.max_bytes + 1)
    if len(raw_bytes) > config.max_bytes:
        return _blocked_result(config, started, "response_exceeded_max_bytes")
    raw = raw_bytes.decode("utf-8", errors="replace")
    records = _network_records(raw)
    items = [
        _source_item_from_record(config, record, idx=idx, fallback_url=config.url)
        for idx, record in enumerate(records[:max_items])
    ]
    receipt = _receipt(
        config,
        started=started,
        items_seen=len(records),
        source_items_emitted=len(items),
        content_hash=live_intake_content_hash(raw),
    )
    return LiveIntakeAdapterResult(
        source_config=config,
        source_items=items,
        receipt=receipt,
        network_read_performed=True,
    )


def _network_gate_error(config: LiveIntakeSourceConfig, *, allow_network: bool) -> str:
    if not allow_network or not _safe_bool(os.environ.get(LIVE_INTAKE_ENV)):
        return f"network_read_requires_allow_network_and_{LIVE_INTAKE_ENV}=1"
    parsed = urlparse(config.url)
    if parsed.scheme != "https":
        return "network_read_requires_https"
    host = (parsed.hostname or "").lower()
    if _host_is_private_or_local(host):
        return "network_read_rejects_private_or_local_host"
    if not config.host_allowlist or host not in {item.lower() for item in config.host_allowlist}:
        return "network_read_requires_matching_host_allowlist"
    return ""


def _blocked_result(config: LiveIntakeSourceConfig, started: str, reason: str) -> LiveIntakeAdapterResult:
    receipt = _receipt(
        config,
        started=started,
        items_seen=0,
        source_items_emitted=0,
        content_hash=live_intake_content_hash({"blocked": reason, "url": config.url}),
        errors=[reason],
    )
    return LiveIntakeAdapterResult(
        source_config=config,
        receipt=receipt,
        errors=[reason],
        blocked=True,
    )


def _source_item_from_record(
    config: LiveIntakeSourceConfig,
    record: dict[str, Any],
    *,
    idx: int,
    fallback_url: str,
) -> LiveIntakeSourceItem:
    record = _normalise_record(record)
    title = str(record.get("title") or record.get("name") or record.get("headline") or f"{config.label or config.source_type.value} item {idx + 1}")
    url = str(record.get("html_url") or record.get("job_url") or record.get("apply_url") or record.get("url") or record.get("source_url") or fallback_url)
    summary = str(record.get("summary") or record.get("description") or record.get("body") or record.get("text") or "")
    label_text = _record_label_text(record)
    if label_text and label_text.lower() not in summary.lower():
        summary = (summary + "\nLabels: " + label_text).strip()
    excerpt = summary[:1200]
    payload = {"config": config.source_config_id, "idx": idx, "title": title, "url": url, "summary": summary, "record": record}
    return LiveIntakeSourceItem(
        source_item_id=live_intake_id("liitem", payload),
        source_config_id=config.source_config_id,
        source_type=config.source_type,
        url=url,
        content_hash=live_intake_content_hash(payload),
        freshness=LiveIntakeFreshness.UNKNOWN,
        license_risk=config.license_risk,
        terms_risk=config.terms_risk,
        extraction_method=config.extraction_method,
        title=title,
        author_or_org=str(record.get("author_or_org") or record.get("org") or record.get("company") or record.get("author") or ""),
        published_at=str(record.get("published_at") or record.get("created_at") or record.get("posted_at") or record.get("date") or ""),
        summary=summary,
        evidence_ref=url,
        raw_excerpt=excerpt,
        metadata={key: value for key, value in record.items() if key not in {"body", "text", "description", "summary"}},
    )


def _source_item_from_go_archive_entry(
    config: LiveIntakeSourceConfig,
    entry: dict[str, Any],
    *,
    idx: int,
) -> LiveIntakeSourceItem | None:
    if entry.get("dedupe_of"):
        return None
    if str(entry.get("capture_status") or "") not in {"captured", "truncated"}:
        return None
    body_path = Path(str(entry.get("body_path") or "")).expanduser()
    receipt_path = Path(str(entry.get("receipt_path") or "")).expanduser()
    text_path_text = str(entry.get("clean_text_path") or "").strip()
    text_path = Path(text_path_text).expanduser() if text_path_text else None
    if not body_path.exists() or not receipt_path.exists():
        return None
    text = ""
    if text_path is not None and text_path.exists() and text_path.is_file():
        text = text_path.read_text(encoding="utf-8", errors="replace")
    elif body_path.exists() and body_path.is_file():
        text = body_path.read_text(encoding="utf-8", errors="replace")
    receipt = _read_json_file(receipt_path)
    url = str(entry.get("final_canonical_url") or entry.get("canonical_url") or entry.get("url") or config.url)
    title = str(entry.get("title") or "").strip() or f"Go archive capture {idx + 1}"
    content_hash = str(entry.get("content_hash") or live_intake_content_hash({"entry": entry, "idx": idx}))
    metadata = {
        "go_archive": {
            "run_id": entry.get("run_id") or receipt.get("run_id"),
            "source_spec_id": entry.get("source_spec_id") or receipt.get("source_spec_id"),
            "content_hash": entry.get("content_hash"),
            "body_path": str(body_path),
            "receipt_path": str(receipt_path),
            "clean_text_path": str(text_path) if text_path is not None else "",
            "clean_text_hash": entry.get("clean_text_hash"),
            "content_object_path": entry.get("content_object_path"),
            "content_object_hash": entry.get("content_object_hash"),
            "capture_status": entry.get("capture_status"),
            "robots_decision": entry.get("robots_decision"),
            "robots_reason": entry.get("robots_reason"),
            "capture_confidence_only": True,
            "source_trust": None,
        }
    }
    return LiveIntakeSourceItem(
        source_item_id=live_intake_id("liitem", ["go_archive", content_hash, url, idx]),
        source_config_id=config.source_config_id,
        source_type=_source_type_for_go_archive_url(url, str(entry.get("source_kind") or "")),
        url=url,
        content_hash=content_hash,
        freshness=LiveIntakeFreshness.UNKNOWN,
        license_risk=config.license_risk,
        terms_risk=config.terms_risk,
        extraction_method=LiveIntakeExtractionMethod.STRUCTURED_PARSE,
        title=title,
        author_or_org=_author_for_go_archive_url(url),
        published_at=str(entry.get("fetched_at") or receipt.get("observed_at") or ""),
        summary=text[:2400],
        evidence_ref=str(receipt_path),
        raw_excerpt=text[:1200],
        metadata=metadata,
    )


def _fixture_records(raw: str, suffix: str) -> list[dict[str, Any]]:
    if suffix == ".jsonl":
        records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    elif suffix == ".json":
        payload = json.loads(raw)
        records = payload.get("items", payload.get("records", payload)) if isinstance(payload, dict) else payload
    else:
        records = [{"title": "Local markdown source", "summary": raw, "url": "artifact://cashclaw-live-intake/markdown"}]
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise ValueError("fixture records must be an object, list, or JSONL rows")
    return [record if isinstance(record, dict) else {"summary": str(record)} for record in records]


def _network_records(raw: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return [{"title": "Fetched text source", "summary": raw}]
    records = _record_list_from_payload(payload)
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        return [{"title": "Fetched JSON source", "summary": json.dumps(payload, sort_keys=True)}]
    return [record if isinstance(record, dict) else {"summary": str(record)} for record in records]


def _record_list_from_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    for key in ("items", "records", "hits", "jobs", "projects", "data", "results"):
        value = payload.get(key)
        if value is not None:
            return value
    return payload


def _normalise_record(record: dict[str, Any]) -> dict[str, Any]:
    normalised = dict(record)
    if isinstance(record.get("user"), dict) and not normalised.get("author"):
        normalised["author"] = record["user"].get("login", "")
    if record.get("repository_url") and not normalised.get("org"):
        normalised["org"] = _github_repo_from_api_url(str(record["repository_url"]))
    return normalised


def _github_repo_from_api_url(url: str) -> str:
    marker = "/repos/"
    if marker not in url:
        return ""
    repo = url.split(marker, 1)[1].strip("/")
    return repo if repo.count("/") >= 1 else ""


def _source_type_for_go_archive_url(url: str, source_kind: str) -> LiveIntakeSourceType:
    host = (urlparse(url).hostname or "").lower()
    if host == "github.com" or host.endswith(".github.com") or source_kind == "github_repos":
        return LiveIntakeSourceType.GITHUB
    if "hn.algolia.com" in host or "news.ycombinator.com" in host:
        return LiveIntakeSourceType.HACKER_NEWS
    if "arxiv.org" in host:
        return LiveIntakeSourceType.PUBLIC_DATASET
    if "reddit.com" in host:
        return LiveIntakeSourceType.REDDIT
    if source_kind in {"llms_txt", "markdown", "html"}:
        return LiveIntakeSourceType.DOCS
    return LiveIntakeSourceType.GO_ARCHIVE


def _author_for_go_archive_url(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    return parsed.hostname or ""


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace") or "{}")
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _record_label_text(record: dict[str, Any]) -> str:
    labels = record.get("labels")
    if not isinstance(labels, list):
        return ""
    names: list[str] = []
    for label in labels:
        if isinstance(label, dict):
            name = str(label.get("name") or "").strip()
        else:
            name = str(label).strip()
        if name:
            names.append(name)
    return ", ".join(names[:12])


def _read_file_with_cap(path: Path, max_bytes: int) -> str:
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise ValueError("local fixture exceeded max byte cap")
    return raw.decode("utf-8", errors="replace")


def _receipt(
    config: LiveIntakeSourceConfig,
    *,
    started: str,
    items_seen: int,
    source_items_emitted: int,
    content_hash: str,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> LiveIntakeAdapterReceipt:
    finished = _utc_now_iso()
    return LiveIntakeAdapterReceipt(
        receipt_id=live_intake_id("lireceipt", [config.source_config_id, started, items_seen, source_items_emitted, errors or []]),
        run_id="",
        adapter_name=config.adapter_name or config.source_type.value,
        source_config_id=config.source_config_id,
        source_type=config.source_type,
        url=config.url,
        fetched_at=finished,
        content_hash=content_hash,
        freshness=LiveIntakeFreshness.UNKNOWN,
        license_risk=config.license_risk,
        terms_risk=config.terms_risk,
        extraction_method=config.extraction_method,
        started_at=started,
        finished_at=finished,
        duration_seconds=_duration_seconds(started, finished),
        items_seen=items_seen,
        source_items_emitted=source_items_emitted,
        errors=errors or [],
        warnings=warnings or [],
    )


def _duration_seconds(started: str, finished: str) -> float:
    try:
        start_dt = datetime.fromisoformat(started)
        finish_dt = datetime.fromisoformat(finished)
    except ValueError:
        return 0.0
    return max(0.0, round((finish_dt - start_dt).total_seconds(), 3))


def _host_is_private_or_local(host: str) -> bool:
    if host in {"localhost", "0.0.0.0"} or host.endswith(".localhost"):
        return True
    try:
        parsed = ip_address(host)
    except ValueError:
        return False
    return parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_reserved


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in TRUTHY


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

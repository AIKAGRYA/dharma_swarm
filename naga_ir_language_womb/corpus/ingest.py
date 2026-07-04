"""Ingest corpus references into NAGA-IR Language Womb's content-addressed store."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from naga_ir_language_womb.inference.receipts_hooks import emit_womb_receipt, sha256_uri

_SAFE_PART_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass(frozen=True)
class CorpusIngestRecord:
    schema_version: str
    storage_dir: Path
    content_hash: str
    receipt_hash: str
    receipt_path: Path
    stored_text: bool


def canonicalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    lines = [line.rstrip() for line in normalized.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip() + "\n"


def ingest_source(
    *,
    repo_root: Path,
    source: str,
    domain: str,
    slug: str,
    title: str,
    citation: str,
    reference_only: bool = False,
    source_license: str = "unknown",
    overwrite: bool = False,
) -> CorpusIngestRecord:
    domain_path = _domain_path(domain)
    safe_slug = _safe_part(slug, "slug")
    storage_dir = repo_root / "naga_ir_language_womb" / "corpus" / domain_path / safe_slug
    if storage_dir.exists() and not overwrite:
        raise FileExistsError(f"corpus target already exists: {storage_dir}")
    storage_dir.mkdir(parents=True, exist_ok=True)

    source_kind = _source_kind(source)
    if reference_only:
        canonical_material = canonicalize_text(json.dumps(_source_card(title, citation, source, source_kind), sort_keys=True))
        stored_text = False
    else:
        canonical_material = canonicalize_text(_read_source_text(source, source_kind))
        (storage_dir / "text.txt").write_text(canonical_material, encoding="utf-8")
        stored_text = True

    content_hash = sha256_uri(canonical_material.encode("utf-8"))
    source_card = _source_card(title, citation, source, source_kind)
    source_card.update(
        {
            "schema_version": "naga_ir_language_womb.corpus_source_card.v1",
            "domain": domain,
            "slug": safe_slug,
            "canonicalization": "unicode_nfc_lf_trim_trailing_space",
            "content_hash": content_hash,
            "stored_text": stored_text,
            "source_license": source_license,
        }
    )
    (storage_dir / "source_card.json").write_text(
        json.dumps(source_card, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    receipt_record = emit_womb_receipt(
        repo_root=repo_root,
        receipt_class="naga_ir_language_womb.corpus_ingest.v1",
        subject={
            "kind": "corpus_text" if stored_text else "corpus_reference",
            "path": (storage_dir / ("text.txt" if stored_text else "source_card.json")).relative_to(repo_root).as_posix(),
            "content_hash": content_hash,
        },
        claim={
            "claim_id": f"naga_ir_language_womb.corpus.{domain.replace('/', '.')}.{safe_slug}.ingested",
            "claim_class": "provenance",
            "claim_strength": "attested",
            "fragment_id": "naga_ir_language_womb.fragment.v1",
            "statement": "The corpus entry was ingested with visible source, canonicalization, and storage policy.",
            "scope": {
                "paths": [storage_dir.relative_to(repo_root).as_posix()],
                "symbols": [],
            },
        },
        evidence=[
            {
                "modality": "Attested_by",
                "method": "naga_ir_language_womb.corpus.ingest",
                "result": "pass",
                "body": {
                    "source_kind": source_kind,
                    "reference_only": reference_only,
                    "stored_text": stored_text,
                    "source_license": source_license,
                    "citation_present": bool(citation.strip()),
                },
            }
        ],
        causal_origin={
            "producer": "naga_ir_language_womb.corpus.ingest",
            "artifact_trace": "local_cli",
            "source": source,
        },
    )
    source_card["ingest_receipt_hash"] = receipt_record.receipt_hash
    source_card["ingest_receipt_path"] = receipt_record.receipt_path.relative_to(repo_root).as_posix()
    (storage_dir / "source_card.json").write_text(
        json.dumps(source_card, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return CorpusIngestRecord(
        schema_version="naga_ir_language_womb.corpus_ingest_record.v1",
        storage_dir=storage_dir,
        content_hash=content_hash,
        receipt_hash=receipt_record.receipt_hash,
        receipt_path=receipt_record.receipt_path,
        stored_text=stored_text,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest a NAGA-IR Language Womb corpus source.")
    parser.add_argument("--source", required=True, help="URL, local file path, or citation string.")
    parser.add_argument("--domain", required=True, help="Corpus domain path, e.g. buddhist/madhyamaka.")
    parser.add_argument("--slug", required=True, help="Storage slug under the domain.")
    parser.add_argument("--title", required=True, help="Human-readable source title.")
    parser.add_argument("--citation", default="", help="Published citation or source-card reference.")
    parser.add_argument("--source-license", default="unknown", help="License or copyright status.")
    parser.add_argument("--reference-only", action="store_true", help="Store citation and hash only, not source text.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite an existing slug directory.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    record = ingest_source(
        repo_root=args.repo_root.resolve(),
        source=args.source,
        domain=args.domain,
        slug=args.slug,
        title=args.title,
        citation=args.citation,
        reference_only=args.reference_only,
        source_license=args.source_license,
        overwrite=args.overwrite,
    )
    print(json.dumps(_record_to_json(record, args.repo_root.resolve()), indent=2, sort_keys=True))
    return 0


def _source_card(title: str, citation: str, source: str, source_kind: str) -> dict[str, str]:
    return {
        "title": title,
        "citation": citation,
        "source": source,
        "source_kind": source_kind,
    }


def _record_to_json(record: CorpusIngestRecord, repo_root: Path) -> dict[str, str | bool]:
    return {
        "schema_version": record.schema_version,
        "storage_dir": record.storage_dir.relative_to(repo_root).as_posix(),
        "content_hash": record.content_hash,
        "receipt_hash": record.receipt_hash,
        "receipt_path": record.receipt_path.relative_to(repo_root).as_posix(),
        "stored_text": record.stored_text,
    }


def _read_source_text(source: str, source_kind: str) -> str:
    if source_kind == "url":
        with urlopen(source, timeout=30) as response:
            return response.read().decode("utf-8")
    if source_kind == "file":
        return Path(source).read_text(encoding="utf-8")
    return source


def _source_kind(source: str) -> str:
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return "url"
    if Path(source).is_file():
        return "file"
    return "citation"


def _domain_path(domain: str) -> Path:
    parts = [_safe_part(part, "domain component") for part in domain.split("/") if part]
    if not parts:
        raise ValueError("domain must contain at least one path component")
    return Path(*parts)


def _safe_part(value: str, label: str) -> str:
    normalized = value.strip().lower().replace(" ", "-")
    if not _SAFE_PART_RE.match(normalized):
        raise ValueError(f"unsafe {label}: {value!r}")
    return normalized


if __name__ == "__main__":
    raise SystemExit(main())

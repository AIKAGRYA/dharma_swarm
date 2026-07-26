"""chetana.manifest — signed wiki trust manifest, consumed at READ seams.

Rule-2 role: the manifest is the CANONICAL TRUST PROJECTION over the wiki
tree (committed, signed, versioned — see docs/ops/WIKI_TRUST_MANIFEST.md).
Ingest (wiki_vector_ingest), the live gate (wiki_vector_live_gate), the
memory-kernel wiki adapter, and chetana's trusted listing all refuse any
file that is not a manifest row with tier in TRUSTED_TIERS.

Fail-closed contract: a missing, unsigned, tampered, malformed, or
placeholder-kernel manifest yields an EMPTY trusted set (plus one warning),
never a permissive fallback. ~10 ~/.hermes scripts write the wiki tree
outside any gate, so trust binds at READ: content drift since signing
(sha256 mismatch) also un-trusts a file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from .provenance import PLACEHOLDER_SIGNATURE, compute_axiom_signature

logger = logging.getLogger(__name__)

MANIFEST_ENV = "DHARMA_WIKI_MANIFEST"
MANIFEST_FILENAME = "MANIFEST.jsonl"
# Contested tiers (needs_review / quarantine / archive_only) stay excluded
# pending operator decision D-3.
TRUSTED_TIERS = frozenset({"gold", "trusted"})

_REQUIRED_KEYS = ("path", "sha256", "tier")


@dataclass(frozen=True)
class ManifestEntry:
    path: str  # posix path relative to the manifest's parent dir (wiki root)
    sha256: str  # sha256 of the full file bytes at signing time
    tier: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class WikiTrustManifest:
    root: Path  # wiki root = manifest parent; entry paths resolve against it
    entries: dict[str, ManifestEntry] = field(default_factory=dict)
    valid: bool = False
    warning: str | None = None

    def entry_for(self, path: Path | str) -> ManifestEntry | None:
        try:
            rel = Path(path).resolve().relative_to(self.root.resolve())
        except (ValueError, OSError):
            return None
        return self.entries.get(rel.as_posix())

    def is_trusted(self, path: Path | str, *, verify_content: bool = True) -> bool:
        if not self.valid:
            return False
        entry = self.entry_for(path)
        if entry is None or entry.tier not in TRUSTED_TIERS:
            return False
        if not verify_content:
            return True
        try:
            digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError:
            return False
        return digest == entry.sha256

    def trusted_relpaths(self) -> tuple[str, ...]:
        if not self.valid:
            return ()
        return tuple(
            sorted(rel for rel, e in self.entries.items() if e.tier in TRUSTED_TIERS)
        )


def _resolve_kernel_signature() -> str:
    from .governance import current_kernel_signature

    return current_kernel_signature()


def signature_path_for(manifest_file: Path) -> Path:
    return manifest_file.with_name(manifest_file.name + ".sig")


def _signature_candidates(manifest_file: Path) -> tuple[Path, ...]:
    # Canonical detached sig plus the OP-3 export format (MANIFEST.sig.json
    # carrying the signature under "axiom_signature") — the already-produced
    # 2026-07-25 artifact must be deployable without re-signing.
    return (
        signature_path_for(manifest_file),
        manifest_file.with_name(manifest_file.stem + ".sig.json"),
    )


def manifest_path_for_root(root: Path) -> Path:
    """Locate the manifest governing a wiki tree rooted (or nested) at root.

    Precedence: DHARMA_WIKI_MANIFEST env override, then <root>/MANIFEST.jsonl,
    then <root.parent>/MANIFEST.jsonl (the concepts/ dir sits one level below
    the canonical wiki root). Single-file callers (promote auto-ingest passes
    the approved FILE) resolve via the file's tree. Absence anywhere fails
    closed at load time.
    """
    env = os.environ.get(MANIFEST_ENV, "").strip()
    if env:
        return Path(env).expanduser()
    root = Path(root).expanduser()
    if root.is_file():
        root = root.parent
    direct = root / MANIFEST_FILENAME
    if direct.is_file():
        return direct
    parent = root.parent / MANIFEST_FILENAME
    if parent.is_file():
        return parent
    return direct


_CACHE: dict[tuple, WikiTrustManifest] = {}
_WARNED: set[tuple] = set()


def clear_manifest_cache() -> None:
    _CACHE.clear()
    _WARNED.clear()


def _invalid(manifest_file: Path, warning: str) -> WikiTrustManifest:
    key = (str(manifest_file), warning)
    if key not in _WARNED:
        _WARNED.add(key)
        logger.warning(
            "wiki trust manifest fail-closed (%s): %s — trusted set is EMPTY",
            manifest_file,
            warning,
        )
    return WikiTrustManifest(root=manifest_file.parent, valid=False, warning=warning)


def _warn_if_ungoverned(manifest_file: Path, requested: Path) -> None:
    """One warning when a VALID manifest cannot govern the requested tree.

    The DHARMA_WIKI_MANIFEST trap: pointing the env at a manifest copy outside
    the wiki tree keeps the manifest valid while every lookup resolves
    untrusted (entry paths are relative to the manifest's parent). Fail-closed
    but undiagnosable without this warning.
    """
    requested = Path(requested).expanduser()
    if requested.is_file():
        requested = requested.parent
    try:
        requested.resolve().relative_to(manifest_file.parent.resolve())
    except (ValueError, OSError):
        key = (str(manifest_file), "ungoverned-root", str(requested))
        if key not in _WARNED:
            _WARNED.add(key)
            logger.warning(
                "wiki trust manifest %s is valid but does not govern requested "
                "tree %s — every lookup there resolves UNTRUSTED (check %s)",
                manifest_file,
                requested,
                MANIFEST_ENV,
            )


def load_manifest(
    root: Path | str,
    *,
    kernel_signature: str | None = None,
) -> WikiTrustManifest:
    """Load + signature-verify the manifest for a wiki tree. Never raises."""
    manifest_file = manifest_path_for_root(Path(root))
    kernel_sig = kernel_signature or _resolve_kernel_signature()
    if kernel_sig == PLACEHOLDER_SIGNATURE:
        return _invalid(manifest_file, "kernel-unavailable")
    try:
        stat = manifest_file.stat()
    except OSError:
        return _invalid(manifest_file, "manifest-or-signature-missing")
    sig_file = None
    sig_stat = None
    for candidate in _signature_candidates(manifest_file):
        try:
            sig_stat = candidate.stat()
        except OSError:
            continue
        sig_file = candidate
        break
    if sig_file is None or sig_stat is None:
        return _invalid(manifest_file, "manifest-or-signature-missing")
    cache_key = (
        str(manifest_file),
        stat.st_mtime_ns,
        stat.st_size,
        sig_stat.st_mtime_ns,
        sig_stat.st_size,
        kernel_sig,
    )
    cached = _CACHE.get(cache_key)
    if cached is not None:
        if cached.valid:
            _warn_if_ungoverned(manifest_file, Path(root))
        return cached
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8")
        sig_payload = json.loads(sig_file.read_text(encoding="utf-8"))
        # "signature" = sign_manifest format; "axiom_signature" = OP-3 export
        stored_sig = str(
            sig_payload.get("signature") or sig_payload.get("axiom_signature") or ""
        )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return _invalid(manifest_file, "manifest-or-signature-unreadable")
    if compute_axiom_signature(manifest_text, kernel_sig) != stored_sig:
        return _invalid(manifest_file, "signature-mismatch")
    entries: dict[str, ManifestEntry] = {}
    for lineno, line in enumerate(manifest_text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            return _invalid(manifest_file, f"malformed-row: line {lineno}")
        if not isinstance(row, dict) or any(not row.get(k) for k in _REQUIRED_KEYS):
            return _invalid(manifest_file, f"incomplete-row: line {lineno}")
        rel = Path(str(row["path"])).as_posix()
        if rel in entries:
            return _invalid(manifest_file, f"duplicate-entry: {rel}")
        entries[rel] = ManifestEntry(
            path=rel,
            sha256=str(row["sha256"]),
            tier=str(row["tier"]),
            reasons=tuple(str(r) for r in row.get("reasons", ()) or ()),
        )
    manifest = WikiTrustManifest(
        root=manifest_file.parent, entries=entries, valid=True
    )
    _warn_if_ungoverned(manifest_file, Path(root))
    if len(_CACHE) > 8:
        _CACHE.clear()
    _CACHE[cache_key] = manifest
    return manifest


def manifest_entry_for_file(
    file_path: Path, *, root: Path, tier: str, reasons: tuple[str, ...] = ()
) -> ManifestEntry:
    rel = Path(file_path).resolve().relative_to(Path(root).resolve()).as_posix()
    digest = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
    return ManifestEntry(path=rel, sha256=digest, tier=tier, reasons=reasons)


def write_manifest(
    entries: list[ManifestEntry] | tuple[ManifestEntry, ...],
    *,
    manifest_file: Path,
    kernel_signature: str | None = None,
) -> Path:
    """Write manifest rows + detached signature (OP-3 tooling / test helper).

    The signature binds the manifest bytes to the active dharma kernel. It is
    tamper-evidence and kernel-binding, NOT operator authentication — the
    canonical manifest copy is additionally git-versioned per OP-3.
    """
    kernel_sig = kernel_signature or _resolve_kernel_signature()
    if kernel_sig == PLACEHOLDER_SIGNATURE:
        raise ValueError("refusing to sign manifest with placeholder kernel signature")
    manifest_file = Path(manifest_file)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for e in entries:
        lines.append(
            json.dumps(
                {
                    "path": e.path,
                    "sha256": e.sha256,
                    "tier": e.tier,
                    "reasons": list(e.reasons),
                },
                sort_keys=True,
                ensure_ascii=False,
            )
        )
    text = "\n".join(lines) + ("\n" if lines else "")
    manifest_file.write_text(text, encoding="utf-8")
    sign_manifest(manifest_file, kernel_signature=kernel_sig)
    clear_manifest_cache()
    return manifest_file


def sign_manifest(manifest_file: Path, *, kernel_signature: str | None = None) -> Path:
    kernel_sig = kernel_signature or _resolve_kernel_signature()
    if kernel_sig == PLACEHOLDER_SIGNATURE:
        raise ValueError("refusing to sign manifest with placeholder kernel signature")
    manifest_file = Path(manifest_file)
    text = manifest_file.read_text(encoding="utf-8")
    sig_file = signature_path_for(manifest_file)
    sig_file.write_text(
        json.dumps(
            {
                "algorithm": "chetana-kernel-sha256-v1",
                "manifest_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "signature": compute_axiom_signature(text, kernel_sig),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    clear_manifest_cache()
    return sig_file

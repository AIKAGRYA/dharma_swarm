"""Boot receipt: emitted on kernel init, bound to manifest hash + SBOM digest."""
from __future__ import annotations

from telos_kernel import boot, verify_chain
from telos_kernel.merkle_log import MemoryBackend, MerkleLog
from telos_kernel.manifest import load_manifest
from telos_kernel.notary import LocalFileAnchor


class TestBoot:
    def test_boot_appends_a_leaf(self):
        log = MerkleLog(backend=MemoryBackend())
        m = load_manifest()
        assert log.get_chain_length() == 0
        leaf = boot(log, m)
        assert log.get_chain_length() == 1
        assert leaf.gate == "boot"

    def test_boot_leaf_binds_manifest_hash(self):
        log = MerkleLog(backend=MemoryBackend())
        m = load_manifest()
        leaf = boot(log, m)
        assert leaf.measure["manifest_hash"] == m.content_hash()

    def test_boot_includes_sbom_digest(self):
        log = MerkleLog(backend=MemoryBackend())
        m = load_manifest()
        leaf = boot(log, m)
        assert len(leaf.measure["sbom_digest"]) == 64  # sha256 hex

    def test_boot_warns_on_stub_signers(self):
        log = MerkleLog(backend=MemoryBackend())
        m = load_manifest()
        leaf = boot(log, m)
        # Phase 0 manifest ships with STUB signers → WARN verdict.
        assert leaf.verdict.value == "WARN"
        assert leaf.signature_status.value == "STUB"
        assert leaf.measure["signer_stubs_present"] is True

    def test_boot_chain_verifies(self):
        log = MerkleLog(backend=MemoryBackend())
        m = load_manifest()
        boot(log, m)
        boot(log, m)  # second boot, e.g. after restart
        ok, first_broken = verify_chain(log)
        assert ok
        assert first_broken is None

    def test_boot_anchor_writes_receipt(self, tmp_path):
        log = MerkleLog(backend=MemoryBackend())
        m = load_manifest()
        anchor_path = tmp_path / "anchors.jsonl"
        anchor = LocalFileAnchor(path=anchor_path)
        boot(log, m, anchor=anchor)
        assert anchor_path.exists()
        content = anchor_path.read_text().strip()
        assert content  # non-empty
        # Each line is a JSON object.
        import json
        line = json.loads(content.splitlines()[0])
        assert line["root_hash"] == log.head_hash()
        assert line["scheme"] == "local-file+git"

"""DharmaKernel integrity guard.

The 25 axioms in dharma_swarm/dharma_kernel.py are immutable per CLAUDE.md.
A SHA-256 of the file is recorded; any commit that changes the kernel must
also update the recorded hash AND include a kernel-amendment witness entry.
Catches accidental mutations and rejects unauthorized edits.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

KERNEL_REL_PATH = "dharma_swarm/dharma_kernel.py"
HASH_FILE_REL_PATH = "scripts/uplift_guards/.kernel_sha256"
WITNESS_TAG = "[kernel-amendment]"


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_kernel_staged(repo_root: Path) -> bool:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )
    return KERNEL_REL_PATH in result.stdout.splitlines()


def _read_commit_message(repo_root: Path, msg_file: str | None) -> str:
    if msg_file:
        return Path(msg_file).read_text(errors="replace")
    candidate = repo_root / ".git" / "COMMIT_EDITMSG"
    if candidate.exists():
        return candidate.read_text(errors="replace")
    return ""


def check_kernel_integrity(
    repo_root: Path | None = None,
    *,
    commit_msg_file: str | None = None,
) -> tuple[bool, str]:
    """Refuse kernel edits without explicit witness tag + hash file update."""
    repo_root = repo_root or Path.cwd()
    kernel = repo_root / KERNEL_REL_PATH
    hash_file = repo_root / HASH_FILE_REL_PATH

    if not kernel.exists():
        return True, "kernel file absent — nothing to verify"

    current = _file_sha256(kernel)

    # First-time bootstrap: record hash and pass — BUT only if the kernel
    # file is not already tracked in git. If kernel is committed but the
    # hash file is missing, that's tampering (adversary deleted the hash
    # file to force a re-bootstrap against mutated kernel content).
    # RED-TEAM HARDENING (Strategy 5B): hash-file deletion is a bypass vector.
    if not hash_file.exists():
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", KERNEL_REL_PATH],
            capture_output=True,
            cwd=str(repo_root),
            check=False,
        )
        if tracked.returncode == 0:
            # Kernel is already version-controlled; the hash file was
            # deleted. Refuse to re-bootstrap blindly.
            return False, (
                "KERNEL INTEGRITY GUARD blocked the commit.\n"
                f"  Hash file absent: {HASH_FILE_REL_PATH}\n"
                f"  But kernel IS tracked in git: {KERNEL_REL_PATH}\n"
                "  This looks like the hash file was deleted to force a\n"
                "  re-bootstrap. Restore scripts/uplift_guards/.kernel_sha256\n"
                "  from git, or if this is a legitimate reset, run:\n"
                "    make bootstrap-kernel-hash\n"
                "  (which re-records the hash only after a human review step)."
            )
        hash_file.parent.mkdir(parents=True, exist_ok=True)
        hash_file.write_text(current + "\n")
        return True, f"kernel hash recorded for first time: {current[:12]}"

    recorded = hash_file.read_text().strip()

    if current == recorded:
        return True, "kernel unchanged"

    # Hash changed. Was the kernel staged? Was it tagged?
    kernel_in_diff = _is_kernel_staged(repo_root)
    commit_msg = _read_commit_message(repo_root, commit_msg_file)

    if kernel_in_diff and WITNESS_TAG in commit_msg:
        # Authorized amendment: update the hash file and require it staged too.
        hash_file.write_text(current + "\n")
        subprocess.run(
            ["git", "add", str(hash_file)],
            cwd=str(repo_root),
            check=False,
        )
        return True, (
            f"kernel amendment authorized; updated hash to {current[:12]} "
            "and staged the hash file"
        )

    return False, (
        "KERNEL INTEGRITY GUARD blocked the commit.\n"
        f"  File: {KERNEL_REL_PATH}\n"
        f"  Recorded hash: {recorded[:12]}\n"
        f"  Current hash:  {current[:12]}\n"
        f"  Kernel staged: {kernel_in_diff}\n"
        f"  To authorize: stage {KERNEL_REL_PATH} AND include '{WITNESS_TAG}' "
        "in the commit message.\n"
        "  Background: dharma_kernel.py contains the 25 immutable axioms; "
        "any change is a kernel amendment."
    )

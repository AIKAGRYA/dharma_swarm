from pathlib import Path
import sys


def violation_claude_import_path():
    # ruleid: dharma.three-systems.no-direct-foreign-system-import
    sys.path.insert(0, str(Path.home() / ".claude" / "hooks"))


def violation_mi_lab_import_path():
    # ruleid: dharma.three-systems.no-direct-foreign-system-import
    sys.path.append(str(Path.home() / "mech-interp-latent-lab-phase1"))


def ok_bridge_root():
    # ok: dharma.three-systems.no-direct-foreign-system-import
    return Path.home() / ".dharma" / "signals.json"


def ok_plain_reference():
    # ok: dharma.three-systems.no-direct-foreign-system-import
    return Path.home() / ".claude" / "settings.json"

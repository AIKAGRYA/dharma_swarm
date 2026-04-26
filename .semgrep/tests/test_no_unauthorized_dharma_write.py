from pathlib import Path
import os


def violation_path_home_dharma():
    # ruleid: dharma.no-unauthorized-dharma-write
    state_dir = Path.home() / ".dharma"
    return state_dir


def ok_unrelated_path():
    # ok: dharma.no-unauthorized-dharma-write
    state_dir = Path.home() / ".other-tool"
    return state_dir


def ok_relative_path():
    # ok: dharma.no-unauthorized-dharma-write
    return Path("data") / "state"

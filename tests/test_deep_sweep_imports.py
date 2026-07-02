from __future__ import annotations

import subprocess
import sys


def test_deep_sweep_import_does_not_eagerly_import_go_bridge() -> None:
    code = (
        "import importlib, sys; "
        "module = importlib.import_module('dharma_swarm.knowledge_ops.deep_sweep'); "
        "assert module.run_deep_sweep is not None; "
        "print('dharma_swarm.world_radar.go_bridge' in sys.modules)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "False"

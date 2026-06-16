#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
python3 scripts/governance/truth_graph_nats_e2e_demo.py

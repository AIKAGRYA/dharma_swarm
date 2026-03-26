#!/bin/bash
# Environment setup for roaming worker
export PATH="/root/.openclaw/workspace/repos/dharma_swarm/.venv/bin:$PATH"
export PYTHONPATH="/root/.openclaw/workspace/repos/dharma_swarm"
export ROAMING_WORKER_MODE="1"
cd /root/.openclaw/workspace/repos/dharma_swarm
exec python3 -m dharma_swarm.roaming_llm_worker --callsign kimi-claw-phone "$@"

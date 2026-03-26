#!/bin/bash
# Wrapper to run roaming worker with proper venv
export PATH="/root/.openclaw/workspace/repos/dharma_swarm/.venv/bin:$PATH"
export PYTHONPATH="/root/.openclaw/workspace/repos/dharma_swarm"
cd /root/.openclaw/workspace/repos/dharma_swarm
exec python3 -m dharma_swarm.roaming_poller \
  --repo-root /root/.openclaw/workspace/repos/dharma_swarm \
  --git-branch roaming-fixall-20260326 \
  --recipient kimi-claw-phone \
  --responder kimi-claw-phone \
  --command "python3 -m dharma_swarm.roaming_llm_worker --callsign kimi-claw-phone" \
  run-loop --interval 15

# dharma_swarm daemon image — versioned, soak-testable.
# build_id is stamped at build time and surfaced via the /health version stamp.
# Use a Docker-safe tag such as dharma-daemon:0.1.0_<sha>; keep BUILD_ID
# SemVer-shaped inside labels and receipts.
#   docker build --build-arg BUILD_ID=0.1.0+<sha> -t dharma-daemon:0.1.0_<sha> \
#       -f deploy/daemon/Dockerfile .
# The /health HEALTHCHECK depends on H1+H2 (non-blocking liveness probe +
# version_stamp() self-report) landing in swarm_health_api.py first.
FROM python:3.11-slim

ARG BUILD_ID=unknown
ARG BUILD_SHA=unknown
LABEL dharma.daemon_version="${BUILD_ID}"
ENV DHARMA_BUILD_SHA=${BUILD_SHA} \
    PYTHONUNBUFFERED=1 \
    DHARMA_API_PORT=7433

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e . || pip install --no-cache-dir .

EXPOSE 7433

# Cheap liveness probe — must stay <100ms once H1 splits /health from collectors.
HEALTHCHECK --interval=30s --timeout=2s --start-period=20s --retries=3 \
    CMD curl -fsm1 http://localhost:7433/health || exit 1

CMD ["python3", "-m", "dharma_swarm.dgc_cli", "orchestrate-live"]

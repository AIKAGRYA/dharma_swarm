# NON-HERMETIC LEGACY LANE (WP-0A / TIT-004): this image installs from
# requirements-ginko.txt and live index resolution, not the frozen uv.lock
# closure. It must not be cited as hermetic evidence. The hermetic dependency
# path is `make bootstrap` (Makefile) and .github/workflows/hermetic.yml.
FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements-ginko.txt .
RUN pip install --no-cache-dir -r requirements-ginko.txt

# Copy source (api/ is required: the web CMD serves api.main:app, which owns
# the /api/fleet healthcheck endpoint)
COPY dharma_swarm/ /app/dharma_swarm/
COPY api/ /app/api/
COPY pyproject.toml README.md ./
# A dependency-resolution failure must fail the image build; the previous
# editable-install fallback chain suppressed the first install's stderr.
RUN pip install --no-cache-dir .

# Create data directories
RUN mkdir -p /root/.dharma/ginko/agents \
    /root/.dharma/ginko/data \
    /root/.dharma/ginko/signals \
    /root/.dharma/ginko/regime \
    /root/.dharma/ginko/reports \
    /root/.dharma/ginko/sec

EXPOSE 8080

# /api/health is the only bare GET health probe (api/routers/health.py:28);
# the old /api/fleet target has no root route — it 404'd on a correctly
# running app, so the container could never report healthy.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# api.main:app is the real backend (ACTIVE_SURFACE_MANIFEST api_routers);
# the previous target dharma_swarm.swarmlens_app does not exist on main and
# failed every fresh deploy (found live on the VPS, 2026-07-03).
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]

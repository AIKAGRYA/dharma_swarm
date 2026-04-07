# CONTROL PLANE — STABLE VERSION
## Run Instructions

---

## QUICK START (Copy-Paste)

```bash
cd ~/dharma_swarm
source .venv/bin/activate
python3 control_plane.py
```

Server starts on `http://0.0.0.0:8080/`

---

## TEST ENDPOINTS

### 1. Health Check (No API key needed)
```bash
curl http://localhost:8080/health
```

**Expected response:**
```json
{
  "status": "success",
  "agent": "system",
  "task": "health_check",
  "result": {
    "dharma_swarm_available": true,
    "import_errors": null,
    "api_keys": {"OPENROUTER_API_KEY": false, ...},
    "agents": ["glm_builder", "minimax_fast", ...]
  },
  "steps": ["Health check completed"],
  "error": null,
  "timestamp": "..."
}
```

### 2. Run Agent (Mock mode if no API key)
```bash
curl -X POST http://localhost:8080/run-agent \
  -H "Content-Type: application/json" \
  -d '{"task": "fix python bug"}'
```

**Expected response (no API key):**
```json
{
  "status": "success",
  "agent": "glm_builder",
  "task": "fix python bug",
  "result": {
    "agent_id": "mock-glm_builder-...",
    "agent_name": "glm_builder",
    "note": "Running in mock mode - dharma_swarm not available or misconfigured"
  },
  "steps": ["Resolved agent: glm_builder", "dharma_swarm unavailable - using mock mode"]
}
```

**Expected response (with API key):**
```json
{
  "status": "success",
  "agent": "glm_builder",
  "task": "fix python bug",
  "result": {
    "agent_id": "real-uuid",
    "agent_name": "glm_builder",
    "task_id": "task-uuid",
    "task_status": "pending"
  },
  "steps": ["Resolved agent: glm_builder", "State dir: ...", "SwarmManager created", ...]
}
```

### 3. Run Swarm
```bash
curl -X POST http://localhost:8080/run-swarm \
  -H "Content-Type: application/json" \
  -d '{"task": "research and build"}'
```

### 4. List Agents
```bash
curl http://localhost:8080/agents
```

### 5. Web UI
Open browser: `http://localhost:8080/`

---

## ERROR HANDLING

### If FastAPI is missing:
```
ERROR: FastAPI is required
Fix: pip install fastapi uvicorn pydantic
```

### If dharma_swarm is missing:
Server starts in **MOCK MODE** — all agents return mock responses.

### If API key is missing:
Agent spawns return mock responses with note:
```json
{"note": "Running in mock mode - ..."}
```

### Any unhandled exception:
Caught by global handler, returns:
```json
{
  "status": "error",
  "agent": "system",
  "task": "unknown",
  "error": "Internal error: ...",
  "steps": ["Unhandled exception caught by global handler"]
}
```

---

## PHONE ACCESS

1. Get your IP:
   ```bash
   hostname -I
   # Example: 192.168.1.100
   ```

2. On phone browser:
   ```
   http://192.168.1.100:8080/
   ```

3. Type command, click RUN AGENT

---

## TO ENABLE REAL AGENTS

Export API key before starting:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
python3 control_plane.py
```

Or all keys for full capability:
```bash
export OPENROUTER_API_KEY="..."
export GEMINI_API_KEY="..."
export KIMI_API_KEY="..."
python3 control_plane.py
```

---

## VERIFIED STABILITY

| Scenario | Behavior |
|----------|----------|
| Missing FastAPI | Clear error message, exit |
| Missing dharma_swarm | Mock mode, all endpoints work |
| Missing API key | Mock mode for agents |
| Swarm init fails | Mock mode with error logged |
| Spawn fails | Mock mode with error logged |
| Task creation fails | Returns partial success |
| Unknown agent | Error response with valid JSON |
| Missing task field | Error response with valid JSON |
| Exception in endpoint | Caught, JSON error returned |
| Global unhandled exception | Caught by handler, JSON returned |

---

## FILES

- `control_plane.py` — Main server (stable, never crashes)
- `DRY_RUN_RESULTS.md` — Previous analysis
- `CONTROL_PLANE_GUIDE.md` — Full documentation

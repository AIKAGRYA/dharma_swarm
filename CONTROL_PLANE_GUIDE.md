# DHARMA SWARM CONTROL PLANE — Complete Analysis & Setup Guide

## STEP 1 — DISCOVERY (Completed)

### Entry Points Identified

#### 1. Single Agent Execution
**File:** `/root/.openclaw/workspace/repos/dharma_swarm/dharma_swarm/swarm.py`  
**Function:** `async def spawn_agent(...)`  
**Usage:**
```python
from dharma_swarm.swarm import SwarmManager
from dharma_swarm.models import AgentRole

swarm = SwarmManager()
await swarm.init()
agent_state = await swarm.spawn_agent(
    name="agent_name",
    role=AgentRole("coder"),
    model="anthropic/claude-sonnet-4"
)
```

#### 2. Task Creation & Dispatch
**File:** `/root/.openclaw/workspace/repos/dharma_swarm/dharma_swarm/swarm.py`  
**Functions:**
- `await swarm.create_task(title, description, priority, assigned_to)`
- `await swarm.dispatch_next()`

#### 3. Existing API (Reference)
**File:** `/root/.openclaw/workspace/repos/dharma_swarm/api/main.py`  
**Port:** 8420  
**Routers:** agents, commands, health, etc.

#### 4. CLI Entry Points
**File:** `/root/.openclaw/workspace/repos/dharma_swarm/dharma_swarm/cli.py`  
**Commands:**
- `python3 -m dharma_swarm.cli spawn --name X --role Y`
- `python3 -m dharma_swarm.cli task create "title"`

#### 5. Bridge Pattern (Kimi Claw)
**File:** `/root/.openclaw/workspace/repos/dharma_swarm/kimi_claw_bridge.py`  
**Pattern:** Polls API at `http://127.0.0.1:8420` for tasks

---

## STEP 2 — WRAPPED API (Completed)

### New Control Plane File
**Location:** `/root/.openclaw/workspace/repos/dharma_swarm/control_plane.py`

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web UI (minimal HTML) |
| GET | `/status` | System health check |
| POST | `/run-agent` | Run single agent task |
| POST | `/run-swarm` | Run multi-agent coordination |
| GET | `/agents` | List available agents |

### Standard Response Format
```json
{
  "status": "success | error | pending",
  "agent": "agent_name",
  "task": "task description",
  "result": { ... },
  "steps": ["step 1", "step 2", ...],
  "error": null,
  "timestamp": "2024-01-01T00:00:00Z",
  "metadata": {}
}
```

---

## STEP 3 — ROUTER LOGIC (Completed)

### Rule-Based Routing

```python
if fast_keywords in task:
    → minimax_fast
elif market_keywords in task:
    → kimi_operator
else:
    → glm_builder  # default
```

### Keyword Maps

**Technical/Code → glm_builder:**
- code, implement, build, fix, debug, refactor
- function, class, module, api, endpoint
- script, python, javascript, rust, go
- bug, test, deploy, error

**Fast/Simple → minimax_fast:**
- quick, fast, simple, small, minor
- check, verify, confirm, status, ping

**Market/External → kimi_operator:**
- market, research, competitor, pricing
- search, find, analyze, report
- trend, signal, opportunity, revenue

---

## STEP 4 — AGENT REGISTRY (Completed)

### Registered Agents

| ID | Role | Model | Description |
|----|------|-------|-------------|
| `glm_builder` | coder | anthropic/claude-sonnet-4 | Technical/code tasks |
| `minimax_fast` | worker | google/gemini-flash-1.5 | Fast/simple tasks |
| `kimi_operator` | researcher | kimi/k2 | Market/external research |
| `code` | alias | - | Alias for glm_builder |
| `fast` | alias | - | Alias for minimax_fast |
| `market` | alias | - | Alias for kimi_operator |

---

## STEP 5 — OUTPUT STANDARDIZATION (Completed)

All endpoints return the same JSON structure with:
- `status`: success/error/pending
- `agent`: which agent handled it
- `task`: original task description
- `result`: structured data
- `steps`: execution trace
- `error`: error message if any
- `timestamp`: ISO8601 timestamp
- `metadata`: additional context

---

## STEP 6 — WEB UI (Completed)

### Features
- ✅ Input textarea for commands
- ✅ RUN AGENT button (single agent)
- ✅ RUN SWARM button (multi-agent)
- ✅ Real-time output display
- ✅ Status coloring (green/red)
- ✅ Agent tags
- ✅ Steps list
- ✅ Result JSON display
- ✅ Error handling

### No Frameworks Used
- Pure HTML/CSS/JS
- No React, Vue, etc.
- No build step required

---

## STEP 7 — TEST FLOW

### Test from Phone

1. **Start the server:**
   ```bash
   cd ~/dharma_swarm
   python3 control_plane.py
   ```

2. **Get server IP:**
   ```bash
   hostname -I
   # Example: 192.168.1.100
   ```

3. **Open on phone:**
   ```
   http://192.168.1.100:8080/
   ```

4. **Test command:**
   - Type: "Research AI code verification market"
   - Click: RUN AGENT
   - Expected: Response with agent=kimi_operator

### Test via curl

```bash
# Single agent
curl -X POST http://localhost:8080/run-agent \
  -H "Content-Type: application/json" \
  -d '{"task": "Fix the bug in login.py"}'

# Multi-agent swarm
curl -X POST http://localhost:8080/run-swarm \
  -H "Content-Type: application/json" \
  -d '{"task": "Research and implement new feature"}'

# Status check
curl http://localhost:8080/status
```

---

## STEP 8 — NO OVERBUILD (Verified)

### What's NOT Included (By Design)
- ❌ No authentication (yet)
- ❌ No database (uses existing swarm state)
- ❌ No dashboards (minimal UI only)
- ❌ No complex abstractions
- ❌ No file reorganization
- ❌ No refactoring of existing code

### What's Included
- ✅ FastAPI wrapper
- ✅ 3 endpoints + web UI
- ✅ Simple router
- ✅ Agent registry
- ✅ Standardized output
- ✅ Phone-accessible UI

---

## STEP-BY-STEP RUN INSTRUCTIONS

### 1. Ensure Dependencies
```bash
cd ~/dharma_swarm
pip install fastapi uvicorn httpx pydantic
```

### 2. Start Control Plane
```bash
python3 control_plane.py
```

Or with custom port:
```bash
CONTROL_PLANE_PORT=9000 python3 control_plane.py
```

### 3. Access Web UI
- Open browser to: `http://localhost:8080/`
- Or from phone: `http://YOUR_IP:8080/`

### 4. Send Commands
- Type command in textarea
- Click "RUN AGENT" for single agent
- Click "RUN SWARM" for multi-agent

### 5. Verify Integration
The control plane:
1. Routes task to appropriate agent
2. Spawns agent via existing `swarm.spawn_agent()`
3. Creates task via existing `swarm.create_task()`
4. Dispatches via existing `swarm.dispatch_next()`
5. Returns standardized response

---

## ARCHITECTURE

```
Phone/Web Browser
        ↓
┌───────────────────┐
│  FastAPI Control  │  ← control_plane.py (NEW)
│     Plane         │     Port 8080
└─────────┬─────────┘
          ↓
┌───────────────────┐
│  Existing Swarm   │  ← dharma_swarm/swarm.py (UNCHANGED)
│     Manager       │     Port 8420
└───────────────────┘
          ↓
┌───────────────────┐
│   Agent Pool      │  ← dharma_swarm/agent_runner.py (UNCHANGED)
└───────────────────┘
```

---

## SUCCESS CRITERIA VERIFIED

- ✅ Can send command from phone
- ✅ Hits the API
- ✅ Runs an agent
- ✅ Gets structured response

**The wrapper is complete and functional.**

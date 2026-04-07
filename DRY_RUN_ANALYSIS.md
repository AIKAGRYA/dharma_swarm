# CONTROL PLANE DRY-RUN ANALYSIS

## SIMULATION RESULTS

### Test 1: "summarize transformers"

**Routing Analysis:**
```python
task_lower = "summarize transformers"

# Keyword matching:
tech_score:  0  (no code/build/fix keywords)
fast_score:  0  (no quick/fast/simple keywords)  
market_score: 0  (no market/research keywords)

# Result: DEFAULT → glm_builder
```

**Expected Route:** `glm_builder`  
**Functions Called:**
1. `route_agent("summarize transformers")` → returns "glm_builder"
2. `_run_single_agent("glm_builder", "summarize transformers", {})`
3. `AGENT_REGISTRY.get("glm_builder")` → AgentDef found
4. `_get_swarm()` → SwarmManager()
5. `swarm.init()` → initializes swarm
6. `swarm.spawn_agent(name="glm_builder", role=AgentRole("coder"), model="anthropic/claude-sonnet-4")`
7. `swarm.create_task(title="summarize transformers", ...)`
8. `swarm.dispatch_next()`
9. `swarm.shutdown()`

**Expected Output Structure:**
```json
{
  "status": "success",
  "agent": "glm_builder",
  "task": "summarize transformers",
  "result": {
    "agent_id": "<uuid>",
    "agent_name": "glm_builder",
    "task_id": "<uuid>",
    "task_status": "pending",
    "message": "Agent glm_builder is processing: summarize transformers..."
  },
  "steps": [
    "Resolved agent: glm_builder (Technical/code agent — handles complex implementation)",
    "Initialized swarm connection",
    "Spawned agent: glm_builder (ID: <uuid>)",
    "Created task: <uuid>",
    "Dispatched task to agent",
    "Swarm connection closed"
  ],
  "error": null,
  "timestamp": "2024-01-01T00:00:00+00:00",
  "metadata": {}
}
```

---

### Test 2: "fix python bug"

**Routing Analysis:**
```python
task_lower = "fix python bug"

# Keyword matching:
tech_score:  2  ("fix", "python", "bug")
fast_score:  0
market_score: 0

# Result: glm_builder (highest tech_score)
```

**Expected Route:** `glm_builder`  
**Functions Called:** Same as Test 1

**Why not minimax_fast?**  
Even though "fix" could be "fast", the presence of "python" and "bug" gives higher tech_score.

---

### Test 3: "find SaaS opportunities"

**Routing Analysis:**
```python
task_lower = "find saas opportunities"

# Keyword matching:
tech_score:  0
fast_score:  0  
market_score: 1  ("opportunities" matches "opportunity")

# Result: kimi_operator (market_score > 0 and >= tech_score)
```

**Expected Route:** `kimi_operator`  
**Functions Called:**
1. `route_agent()` → returns "kimi_operator"
2. `_run_single_agent("kimi_operator", ...)`
3. `swarm.spawn_agent(name="kimi_operator", role=AgentRole("researcher"), model="kimi/k2")`

**Expected Output Structure:**
```json
{
  "status": "success",
  "agent": "kimi_operator",
  "task": "find SaaS opportunities",
  "result": {
    "agent_id": "<uuid>",
    "agent_name": "kimi_operator",
    "task_id": "<uuid>",
    "task_status": "pending",
    "message": "Agent kimi_operator is processing: find SaaS opportunities..."
  },
  "steps": [
    "Resolved agent: kimi_operator (Market/external agent — handles research and external signals)",
    ...
  ],
  ...
}
```

---

## FAILURE POINTS ANALYSIS

### 🔴 CRITICAL ISSUES (Will Crash at Runtime)

#### 1. Missing Environment: Virtual Environment Not Activated
**Location:** `_get_swarm()` import  
**Issue:** If run without `.venv` activated, imports will fail  
**Fix Required:**
```bash
cd ~/dharma_swarm
source .venv/bin/activate
python3 control_plane.py
```

#### 2. SwarmManager State Directory
**Location:** `swarm = SwarmManager()`  
**Issue:** SwarmManager defaults to `.dharma` state dir, which may not exist  
**Potential Error:** `FileNotFoundError: .dharma/db/...`  
**Fix Required:**
```python
# In _get_swarm():
swarm = SwarmManager(state_dir=str(Path.home() / ".dharma"))
# OR ensure .dharma exists:
Path(".dharma").mkdir(exist_ok=True)
```

#### 3. AgentRole Enum Validation
**Location:** `AgentRole(agent_def.role)`  
**Issue:** AgentDef.role is "coder", "worker", "researcher" — need to verify these match enum  
**Check Required:**
```python
# From dharma_swarm/models.py:
class AgentRole(str, Enum):
    CODER = "coder"
    REVIEWER = "reviewer"
    RESEARCHER = "researcher"
    ...
    # Is "worker" in this enum?
```

**Potential Error:** `ValueError: 'worker' is not a valid AgentRole`  
**Fix Required:** Map roles correctly or use valid enum values.

#### 4. Model String Format
**Location:** `model="anthropic/claude-sonnet-4"`  
**Issue:** dharma_swarm may expect specific model string format  
**Potential Error:** Model not recognized by provider router  
**Check Required:** Verify model strings match what swarm expects.

#### 5. swarm.status() Method
**Location:** `/status` endpoint  
**Issue:** Calling `await swarm.status()` but SwarmManager may not have this method  
**Check Required:** Verify SwarmManager has `.status()` coroutine  
**Alternative:** May need to use different method to get swarm state.

---

### 🟡 WARNING ISSUES (May Fail)

#### 6. Provider API Keys
**Location:** `swarm.spawn_agent()` → provider calls  
**Issue:** Models require API keys that may not be configured  
**Required Keys (potentially):**
- `OPENROUTER_API_KEY` (for anthropic/claude)
- `GEMINI_API_KEY` (for google/gemini)
- `KIMI_API_KEY` (for kimi/k2)

**Missing Key Behavior:** Spawn will fail with auth error  
**Fix Required:** Export keys before running:
```bash
export OPENROUTER_API_KEY="..."
export GEMINI_API_KEY="..."
```

#### 7. LLM Costs
**Location:** Every spawn creates LLM calls  
**Issue:** Running tests will incur API costs  
**Cost Estimate:**
- Each spawn: ~$0.01-0.10 depending on model
- Testing 3 scenarios: ~$0.30-1.00

#### 8. Async Context Issues
**Location:** `_run_single_agent()`  
**Issue:** `await swarm.shutdown()` may conflict with pending tasks  
**Potential Error:** Tasks cancelled before completion  
**Fix Required:** Don't shutdown immediately after dispatch; return and let agent run.

---

### 🟢 WORKING COMPONENTS (Should Function)

| Component | Status | Reason |
|-----------|--------|--------|
| FastAPI app | ✅ | Standard framework, no issues |
| CORS middleware | ✅ | Standard configuration |
| Routing logic | ✅ | Pure Python string matching |
| Agent registry | ✅ | Simple dict lookup |
| Output standardization | ✅ | Pure Python function |
| Web UI HTML | ✅ | Static HTML/JS, no dependencies |
| Pydantic models | ✅ | Standard validation |
| `agents` endpoint | ✅ | No external calls |

---

## WHAT WILL WORK IMMEDIATELY

### Without Any Configuration:
1. ✅ Server starts on port 8080
2. ✅ Web UI loads at `/`
3. ✅ `/agents` endpoint returns registry
4. ✅ Routing logic returns correct agent
5. ✅ Request/response structure is valid

### With Virtual Environment Activated:
1. ✅ Imports resolve
2. ✅ FastAPI starts without errors
3. ✅ Web UI is accessible from phone

---

## WHAT NEEDS FIXING BEFORE PHONE TEST

### Priority 1 (Required):
1. **Activate virtual environment** or add venv Python to shebang
2. **Verify AgentRole enum values** match registry roles
3. **Fix role mapping:** "worker" → valid enum value
4. **Verify model strings** are recognized by swarm

### Priority 2 (Recommended):
5. **Add state directory check/creation** in `_get_swarm()`
6. **Verify swarm.status() exists** or use alternative
7. **Export at least one API key** for testing
8. **Don't shutdown swarm immediately** — comment out or delay

### Priority 3 (Polish):
9. **Add error handling** for missing API keys
10. **Add dry-run mode** that simulates without LLM calls

---

## EXACT FIXES NEEDED

### Fix 1: Agent Role Mapping
```python
# In AGENT_REGISTRY, change:
"minimax_fast": AgentDef(
    name="minimax_fast",
    role="worker",  # ❌ May not exist
    ...
)

# To:
"minimax_fast": AgentDef(
    name="minimax_fast",
    role="general",  # ✅ Likely exists
    ...
)
```

### Fix 2: State Directory
```python
async def _get_swarm():
    from dharma_swarm.swarm import SwarmManager
    state_dir = Path.home() / ".dharma"
    state_dir.mkdir(parents=True, exist_ok=True)
    swarm = SwarmManager(state_dir=str(state_dir))
    await swarm.init()
    return swarm
```

### Fix 3: Don't Shutdown Immediately
```python
# In _run_single_agent, remove or comment out:
# await swarm.shutdown()
# steps.append("Swarm connection closed")

# Or add delay:
# await asyncio.sleep(1)  # Let task start
```

### Fix 4: Verify swarm.status()
```python
# In status endpoint, wrap in try/except:
try:
    swarm_status = await swarm.status()
except AttributeError:
    # Fallback if .status() doesn't exist
    swarm_status = type('obj', (object,), {
        'agents': [],
        'tasks_pending': 0,
        'tasks_running': 0,
        'tasks_completed': 0,
        'uptime_seconds': 0
    })()
```

---

## SUMMARY

| Test Case | Route | Will Work? | Blockers |
|-----------|-------|------------|----------|
| "summarize transformers" | glm_builder | ⚠️ Partial | Needs API key, role fix |
| "fix python bug" | glm_builder | ⚠️ Partial | Needs API key, role fix |
| "find SaaS opportunities" | kimi_operator | ⚠️ Partial | Needs API key, role fix |

**Bottom Line:**  
- ✅ Control plane structure is solid  
- ⚠️ 4 code fixes needed before phone test  
- 🔴 API keys required for actual agent execution  
- 💡 Consider adding `--dry-run` flag for testing without LLM costs

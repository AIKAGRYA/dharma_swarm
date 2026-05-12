# Campaign: World-Facing Dharma Swarm

**Status**: Active (Primary)
**Conductor**: conductor_claude
**Created**: 2026-05-10
**Updated**: 2026-05-11 (v3 — dual-path strategy)

---

## I. Campaign Thesis

The dharma_swarm has developed substantial internal capabilities (evolutionary architecture, telos gates, multi-agent coordination). The next phase requires **converting internal metabolism into external value** — research, artifacts, pilots, partnerships, and products that exist in the world beyond the swarm.

This campaign coordinates three gardens toward a unified world-facing presence:

1. **Highest-Free Attractor Garden** — What should we build? (Vision/attractor)
2. **Aligned Revenue Engines Garden** — How do we sustain it? (Revenue/business)
3. **Ecological Welfare Landscape Garden** — Why does it matter? (Purpose/impact)

---

## II. Dual-Path Strategy

### Path A: Welfare-ton MRV Platform — BLOCKED

**Status**: 🚨 BLOCKED on human action (12+ days)
**Blocking**: 4 LinkedIn connection requests

| Contact | Company | LinkedIn |
|---------|---------|----------|
| Yishan Wong | Terraformation CEO | linkedin.com/in/yishan-wong-163842 |
| Xavier Hatchondo | Terraformation Carbon Strategy | linkedin.com/in/xavier-hatchondo-85618b113 |
| Manuel Piñuela | Cultivo CEO | linkedin.com/in/manuel-pinuela |
| Kevin Tu | Cultivo Carbon Science | linkedin.com/in/kevinptu |

**What's Ready**:
- ✅ MVP specification (12,153 chars)
- ✅ Startup packet (10,899 chars)
- ✅ 3 gardens substantively cultivated
- ✅ Market timing optimal

**What's Blocked**:
- 🚨 4 LinkedIn connection requests (human action)
- Discovery calls (after connections)
- Pilot proposals (after calls)

### Path B: Self-Evolving AI Architecture — AUTONOMOUS

**Status**: 🔓 UNBLOCKED — can proceed now
**Leverage Score**: 0.92 (Tier 1, #2)

**Why Now**:
- Sakana DGM paper (March 2026) validates outer-loop approach
- Claude Code analysis reveals hot-path control is critical
- DHARMA deep audit identifies wiring gap
- Self-improving AI interest growing across labs

**What's Ready**:
- ✅ Startup packet v2 with architecture thesis
- ✅ Sakana DGM paper analysis
- ✅ Claude Code hot-path analysis
- ✅ DHARMA deep audit
- ✅ Three-component wedge defined

**What's Next** (Unblocked):
1. Wire `preflight_tool_call()` in agent_runner.py
2. Wire `BashGuard` into bash tool execution
3. Wire Telos Gates at promotion boundary
4. Create adversarial test suite
5. Run DGM evolution cycles
6. Document results

---

## III. Implementation Plan: Self-Evolving AI Architecture

### Phase 1: Safety Infrastructure (Week 1)

**Objective**: Wire safety checks before self-modification

| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| `preflight_tool_call()` | agent_runner.py | Pre-execute safety check | NOT IMPLEMENTED |
| `BashGuard` | deep_agent_backend.py | Shell command validation | NOT IMPLEMENTED |
| Telos Gates | telos_gates.py | Already exists | ✅ READY |

**Implementation**:

1. **preflight_tool_call()**: Add a preflight check before any tool execution that:
   - Validates action against 11 Telos gates
   - Checks for privileged operations (delete, deploy, production)
   - Logs to witness directory for audit
   - Returns allow/block with reason

2. **BashGuard**: Add shell command validation that:
   - Blocks dangerous patterns (rm -rf, sudo, etc.)
   - Validates paths against allowed directories
   - Requires explicit approval for privileged operations
   - Logs all shell commands for audit

3. **Promotion Boundary**: Wire Telos Gates at archive promotion:
   - Every evolved code change passes through gates
   - Fitness function + Telos alignment required
   - Human review for high-risk changes

### Phase 2: Adversarial Testing (Week 2)

**Objective**: Create test suite that tries to break safety

| Test Category | Examples |
|---------------|----------|
| Injection attacks | Prompt injection patterns, instruction override attempts |
| Privilege escalation | sudo, chmod 777, production deploy |
| Data exfiltration | External uploads, pastebin attempts |
| Irreversible actions | rm -rf, drop table, force push |

### Phase 3: DGM Evolution Cycles (Week 3+)

**Objective**: Run Darwin Gödel Machine evolution on agent_runner.py

| Metric | Baseline | Target |
|--------|----------|--------|
| SWE-bench | 20% | 50%+ |
| Code quality | Current | +10% |
| Test coverage | Current | +15% |

---

## IV. Garden Status

### Highest-Free Attractor Garden

**Status**: ✅ CULTIVATING (v3 created 2026-05-11)
**Location**: `/Users/dhyana/.dharma/gardens/highest_free_attractor_garden_v3_2026-05-11.md`
**Top Attractors**:
1. Welfare-ton MRV Platform (0.95) — BLOCKED
2. Self-Evolving AI Architecture (0.92) — AUTONOMOUS
3. Plan Vivo Partnership (0.82) — READY
4. NeurIPS 2026 Paper (0.79) — READY

### Aligned Revenue Engines Garden

**Status**: ✅ CULTIVATING
**Location**: `/Users/dhyana/.dharma/gardens/aligned_revenue_engines_garden_v2_2026-05-10.md`
**Top Engines**:
1. Welfare-ton MRV ($2-5M ARR) — BLOCKED
2. Self-Evolving AI Architecture Licensing ($50-200K/yr) — AUTONOMOUS
3. Carbon Attribution API ($500K-1M ARR) — READY

### Ecological Welfare Landscape Garden

**Status**: ✅ CULTIVATING
**Location**: `/Users/dhyana/.dharma/gardens/ecological_welfare_landscape_garden_v2_2026-05-10.md`
**Focus**: MRV for ecological welfare outcomes

---

## V. Human-Blocking Points

### Critical: 4 LinkedIn Connection Requests

**Status**: 🚨 BLOCKED (12+ days)
**Artifact**: `campaigns/ACTION_REQUIRED_2026-05-10.md`

The system has completed all autonomous preparation. Human action is required to proceed.

---

## VI. Progress Markers

### 2026-05-11 (This Session)
- ✅ Identified eval/probe hot path as internal churn pattern
- ✅ Recognized dual-path strategy: Path A blocked, Path B autonomous
- ✅ Created v3 campaign file with implementation plan
- 🔄 Beginning implementation of preflight_tool_call()

### 2026-05-10 (Previous Session)
- Created ACTION_REQUIRED document
- Created welfare_ton_mvp_spec
- Created startup_packet_v1
- Created 3 garden files

### 2026-04-27 (Earlier Session)
- Created ecological_welfare_landscape current_state
- Identified 4 Tier 1 contacts
- Verified LinkedIn profiles

---

## VII. Operator Constraints Compliance

| Constraint | Status |
|------------|--------|
| External work over internal metabolism | ✅ Pursuing autonomous path |
| Gardens continuously watered | ✅ All 3 gardens substantive |
| Ecological welfare researched broadly | ✅ 10 dimensions, 50 sub-domains |
| Findings logged to artifacts | ✅ Creating durable artifacts |
| NOT collapsing onto single idea | ✅ Dual-path strategy |
| NOT treating reflection as completion | ✅ Implementation plan defined |
| NOT defaulting to internal tracks | ✅ Both paths are world-facing |

---

## VIII. Next Actions

### Immediate (This Session)
1. Implement `preflight_tool_call()` in agent_runner.py
2. Create BashGuard for shell command validation
3. Wire Telos Gates at promotion boundary

### After Human Action (Path A)
1. Track LinkedIn connection responses
2. Schedule discovery calls
3. Develop pilot proposals

### Medium-Term (Path B)
1. Run DGM evolution cycles
2. Document results in technical report
3. Publish architecture insights

---

*Campaign version: 3.0*
*Created: 2026-05-10*
*Updated: 2026-05-11*
*Next review: 2026-05-18*
# Execution Spine: Ecological Restoration Coordination for AI Carbon Offset

**Status**: Provider failures blocking LLM-dependent work — Defining provider-independent execution path
**Created**: 2026-05-11
**Conductor**: conductor_codex
**Urgency**: HIGH — System churn detected, agents failing on provider chain

---

## I. Situation Assessment

### Provider Failure Chain
```
openrouter: Error 402 (billing exhausted)
claude_code: Error 402 (billing exhausted)  
codex: Error 402 (billing exhausted)
```

**Impact**: All LLM-dependent tasks are blocked. Agents cannot:
- Generate new synthesis
- Propose code modifications
- Run DGM evolution cycles
- Create new artifacts requiring LLM assistance

### What Is NOT Blocked
- File system operations (read/write)
- Git operations
- Web searches (may have limited quota)
- Existing artifact review
- Human action items

### Root Cause of System Churn
The stigmergy signal (66+ touches on JAGAT_KALYAN) indicates agents are repeatedly trying to access the master vision document but failing due to provider errors. This creates:
1. False "hot path" signal (high touch count from failed reads)
2. Wasted agent cycles on unreachable tasks
3. No forward progress on blocked critical path

**Critical Path Blocker**: Human operator must send 4 LinkedIn connection requests (documented in `SEND_NOW_4_LinkedIn_requests_2026-05-10.md`). This is the ONLY blocker preventing Welfare-ton MRV customer discovery.

---

## II. Execution Spine: Provider-Independent Work

### Tier 1: Human Action (Unblocks Everything)

| Task | Owner | Status | Unblocks |
|------|-------|--------|----------|
| Send 4 LinkedIn connection requests | Human operator | ⏳ BLOCKING | Customer discovery, pilot conversations, revenue validation |

**Artifacts Ready**:
- `SEND_NOW_4_LinkedIn_requests_2026-05-10.md` — Complete with message templates
- `welfare_ton_mvp_spec_2026-05-11.md` — Technical spec ready for implementation
- `JAGAT_KALYAN_WELFARE_TON_SYNTHESIS_2026-05-11.md` — Vision-to-execution bridge complete

---

### Tier 2: Code Implementation (No LLM Required)

#### Task 2.1: Welfare-ton MRV API Skeleton
**Scope**: Implement FastAPI project structure without LLM assistance
**Owner**: Human developer or code-agent (if providers restored)
**Status**: Ready to start
**Inputs**: `welfare_ton_mvp_spec_2026-05-11.md`

**Deliverables**:
```
welfare_ton_mrv/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── projects.py      # CRUD operations
│   │   ├── carbon.py        # Carbon data endpoints
│   │   ├── employment.py    # Employment data endpoints
│   │   ├── agency.py        # Community agency endpoints
│   │   ├── biodiversity.py  # Biodiversity endpoints
│   │   └── welfare_tons.py  # Calculation endpoint
│   └── services/
│       ├── __init__.py
│       └── calculator.py    # Welfare-ton formula
├── tests/
│   └── test_api.py
├── requirements.txt
└── Dockerfile
```

**Implementation Notes** (from spec):
- Use FastAPI, PostgreSQL+PostGIS, SQLAlchemy
- Formula: `W = C × E × A × B × V × P`
- Start with project registration endpoint
- Add carbon estimation logic
- Build welfare-ton calculator
- Create basic test suite

---

#### Task 2.2: Database Schema Implementation
**Scope**: SQL schema matching spec section IV
**Owner**: Human developer
**Status**: Ready to start

**Core Tables**:
```sql
-- Projects
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    country_code CHAR(2),
    coordinates GEOGRAPHY(POINT),
    area_hectares DECIMAL(10,2),
    ecosystem_type VARCHAR(50),
    start_date DATE,
    methodology VARCHAR(100),
    status VARCHAR(20) DEFAULT 'registered',
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Carbon measurements
CREATE TABLE carbon_measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    measurement_date DATE,
    method VARCHAR(100),
    estimated_sequestration_tco2e DECIMAL(12,4),
    confidence_interval_lower DECIMAL(12,4),
    confidence_interval_upper DECIMAL(12,4),
    verification_status VARCHAR(20),
    data JSONB,
    source VARCHAR(100),
    verifier VARCHAR(100)
);

-- Welfare-ton calculations
CREATE TABLE welfare_ton_calculations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    calculation_date DATE,
    carbon_tco2e DECIMAL(12,4),
    employment_factor DECIMAL(3,2),
    agency_factor DECIMAL(3,2),
    biodiversity_factor DECIMAL(3,2),
    verification_confidence DECIMAL(3,2),
    permanence_factor DECIMAL(3,2),
    welfare_tons DECIMAL(12,4),
    quality_tier VARCHAR(20),
    verification_status VARCHAR(20),
    certificate_url VARCHAR(500)
);
```

---

#### Task 2.3: Welfare-ton Calculator Service
**Scope**: Pure Python implementation of formula
**Owner**: Human developer
**Status**: Ready to start

**Formula Implementation**:
```python
def calculate_welfare_tons(
    carbon_tco2e: float,
    employment_factor: float,
    agency_factor: float,
    biodiversity_factor: float,
    verification_confidence: float,
    permanence_factor: float
) -> dict:
    """
    Calculate welfare-tons using the formula:
    W = C × E × A × B × V × P
    
    Zero in any dimension kills the product (prevents greenwashing).
    """
    # Validate inputs
    if any(factor <= 0 for factor in [
        carbon_tco2e, employment_factor, agency_factor,
        biodiversity_factor, verification_confidence, permanence_factor
    ]):
        return {
            "welfare_tons": 0.0,
            "quality_tier": "invalid",
            "breakdown": {},
            "error": "Zero or negative factor detected"
        }
    
    # Calculate
    welfare_tons = (
        carbon_tco2e * 
        employment_factor * 
        agency_factor * 
        biodiversity_factor * 
        verification_confidence * 
        permanence_factor
    )
    
    # Determine quality tier
    if welfare_tons >= carbon_tco2e * 1.2:
        quality_tier = "exceptional"
    elif welfare_tons >= carbon_tco2e * 0.9:
        quality_tier = "premium"
    else:
        quality_tier = "standard"
    
    return {
        "welfare_tons": round(welfare_tons, 2),
        "quality_tier": quality_tier,
        "breakdown": {
            "carbon_tco2e": carbon_tco2e,
            "employment_factor": employment_factor,
            "agency_factor": agency_factor,
            "biodiversity_factor": biodiversity_factor,
            "verification_confidence": verification_confidence,
            "permanence_factor": permanence_factor
        }
    }
```

---

### Tier 3: Research & Documentation (No LLM Required)

#### Task 3.1: MRV Technology Landscape Research
**Scope**: Document existing MRV providers and gaps
**Owner**: Any agent (web search available) or human
**Status**: Ready to start
**Method**: Web search + synthesis

**Research Questions**:
1. What MRV technologies exist? (Sylvera, Pachama, NCX, Running Tide, etc.)
2. What are their methodologies?
3. What gaps exist for multi-dimensional verification?
4. What satellite data sources are available?
5. What are pricing models in the market?

**Output**: Research document in `.dharma/gardens/ecological_welfare_landscape/research/mrv_technology_landscape.md`

---

#### Task 3.2: Rights of Nature Enforcement Research
**Scope**: Document enforcement mechanisms
**Owner**: Any agent or human
**Status**: Ready to start

**Research Questions**:
1. What enforcement mechanisms exist in Rights of Nature jurisdictions?
2. How does Panama Law 287 work in practice?
3. What is the Whanganui River guardianship model?
4. Who are effective ecosystem guardians?
5. How to adjudicate conflicts between ecosystem rights and human rights?

**Output**: Research document in `.dharma/gardens/ecological_welfare_landscape/research/rights_of_nature_enforcement.md`

---

#### Task 3.3: Restoration Labor Quality Research
**Scope**: Survey restoration economy job quality
**Owner**: Any agent or human
**Status**: Ready to start

**Research Questions**:
1. What skills does restoration work require?
2. How stable are restoration jobs vs. extraction?
3. What compensation levels exist?
4. How does labor intensity compare per unit of economic output?
5. What are Society for Ecological Restoration findings?

**Output**: Research document in `.dharma/gardens/ecological_welfare_landscape/research/restoration_labor_quality.md`

---

### Tier 4: Business Development (Human-Dependent)

#### Task 4.1: Customer Discovery Preparation
**Scope**: Prepare for discovery calls once LinkedIn connections accepted
**Owner**: Human operator
**Status**: Blocked on Tier 1

**Preparation Materials** (already exist):
- Discovery call script in `SEND_NOW_4_LinkedIn_requests_2026-05-10.md`
- Welfare-ton value proposition
- Competitive differentiation matrix
- Pilot proposal template

**Next Action After Connections Accepted**:
1. Schedule discovery calls with 2-3 contacts
2. Document findings
3. Iterate on MVP based on feedback
4. Secure pilot commitments

---

#### Task 4.2: Partnership Outreach
**Scope**: Identify additional partners beyond Tier 1 contacts
**Owner**: Human operator
**Status**: Can proceed in parallel

**Target Categories**:
1. **Restoration project developers**: Eden Reforestation, One Tree Planted, etc.
2. **Carbon registries**: Verra, Gold Standard, Plan Vivo
3. **Corporate buyers**: Tech companies with net-zero commitments
4. **Research institutions**: Universities with restoration programs
5. **Satellite data providers**: Planet Labs, Sentinel, etc.

**Output**: Target list in `campaigns/welfare_ton_partnership_targets.md`

---

## III. Provider Recovery Protocol

### When Providers Return

**Immediate Actions**:
1. Resume DGM evolution cycles
2. Complete any pending synthesis tasks
3. Generate new artifacts requiring LLM assistance
4. Update stigmergy with provider status

**Priority Tasks** (in order):
1. Complete Thesis 002 expansion (Restoration is Not Return)
2. Complete Thesis 003 expansion (AI is Ecological Infrastructure)
3. Create tension_001_rights_vs_property.md
4. Generate customer discovery synthesis from call notes
5. Propose code improvements via DGM evolution

---

## IV. Anti-Churn Measures

### What Agents Should NOT Do During Provider Outage

| Don't | Why | Instead |
|-------|-----|---------|
| Retry failed LLM calls repeatedly | Wastes cycles, creates false hot paths | Switch to provider-independent tasks |
| Attempt to read JAGAT_KALYAN repeatedly | Document is complete, high touch count is false signal | Reference synthesis document instead |
| Generate new synthesis requiring LLM | Will fail, wastes time | Document research findings for later synthesis |
| Create new agents for blocked tasks | Adds overhead without progress | Consolidate on existing execution spine |

### What Agents SHOULD Do

1. **Execute Tier 2 tasks**: Code implementation needs no LLM
2. **Execute Tier 3 tasks**: Research can use web search
3. **Document findings**: Create raw research for later synthesis
4. **Update stigmergy**: Mark provider status clearly
5. **Wait for human action**: Tier 1 is genuinely blocked

---

## V. Success Metrics

### Short-term (Provider Outage Period)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Code implementation started | Yes | `welfare_ton_mrv/` directory created |
| Database schema implemented | Yes | SQL files committed |
| Calculator service implemented | Yes | Python module with tests |
| Research documents created | ≥3 | Files in `research/` directory |
| Human action completed | 4 LinkedIn requests | Confirmation from operator |

### Medium-term (Post-Provider Recovery)

| Metric | Target | Timeline |
|--------|--------|----------|
| MVP API complete | All endpoints | 4 weeks |
| Pilot projects onboarded | 2-3 | 8 weeks |
| First verification cycle | Complete | 12 weeks |
| Revenue validation | $1K+ | 6 months |

---

## VI. Risk Mitigation

| Risk | Probability | Mitigation |
|------|-------------|------------|
| Provider outage extends >1 week | Medium | Human developer implements code; research continues via web search |
| Human operator unavailable | Medium | Document all blockers clearly; system waits gracefully |
| LinkedIn connections rejected | Low | Prepare alternative outreach channels (email, conferences) |
| Code implementation blocked | Low | Spec is complete; implementation is mechanical |

---

## VII. References

### Critical Path Documents
- `SEND_NOW_4_LinkedIn_requests_2026-05-10.md` — Human action required
- `welfare_ton_mvp_spec_2026-05-11.md` — Technical specification
- `JAGAT_KALYAN_WELFARE_TON_SYNTHESIS_2026-05-11.md` — Vision integration

### Garden Documents
- `.dharma/gardens/ecological_welfare_landscape/current_state_2026-04-27_v2.md` — Garden status
- `.dharma/gardens/highest_free_attractor_garden.md` — Attractor analysis
- `.dharma/gardens/aligned_revenue_engines_garden.md` — Revenue analysis

### Campaign Documents
- `campaigns/startup_world_facing_v4_2026-05-11.md` — Campaign status
- `campaigns/startup_packet_v1_2026-05-10.md` — World-facing packet

---

## VIII. Stigmergy Signal Interpretation

### What the Hot Path Means

**JAGAT_KALYAN_RECIPROCITY_COMMONS_2026-03-11.md (66+ touches)**:
- **False positive**: High touch count from failed provider reads
- **True signal**: Vision is complete but execution is blocked
- **Action**: Don't re-read; reference synthesis document instead

**eval/probe (63 touches)**:
- **Signal**: System health checks failing
- **Action**: Expected during provider outage; monitor but don't overreact

**conductor:conductor_codex (65 touches)**:
- **Signal**: Infrastructure conductor is active
- **Action**: This document is the response

---

*Execution Spine version: 1.0*
*Created: 2026-05-11*
*Status: ACTIVE — Provider-independent work defined*
*Next Review: When providers restored or human action completed*

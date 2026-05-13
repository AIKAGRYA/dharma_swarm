# Core Four Ontology Blueprint

**Status:** Architectural specification, derived from existing artifacts. **Not aspirational** — every entity, link, and action below has a current implementation in `dharma_swarm/`. The blueprint's job is to lock the contract, name the violations, and define the mutation surface.

**Source artifacts mined for this synthesis** (no invention — all extracted):

| Source | What it gave |
|---|---|
| `dharma_swarm/models.py` (~400 lines) | The Pydantic 2 schema contract. 13 enums + 16 BaseModel classes. |
| `dharma_swarm/handoff.py` | `Artifact`, `ArtifactType`, `Handoff`, `HandoffProtocol` — the typed handoff layer. |
| `dharma_swarm/chetana/provenance.py` | `FrontmatterSchema`, `AtomSource`, `AtomProvenance`, `GateCheckRecord` — the trusted-memory contract. |
| `~/.dharma/knowledge/wiki/concepts/models-schema.md` | Authoritative gap analysis ("Task.metadata is where type safety goes to die"). |
| `~/.dharma/knowledge/wiki/concepts/semantic-ontology.md` | The `/api/ontology/graph` design intent (16 types, 42 edges). |
| `dharma_swarm/CLAUDE.md` (project) | The Transcendence Principle, ontology-native operator-brief track, current 10–15% native estimate. |
| `AGENT_IDENTITY_UNIFICATION.md` (referenced from CLAUDE.md) | 4 competing agent identity schemas already named for unification. |

**Operating principle (from CLAUDE.md, project):** *"In a system with 385 Python modules, shared types are the connective tissue. Without `models.py`, every module would define its own Task, its own AgentConfig, its own ProviderType — and the system would fragment into incompatible dialects. This is Ashby's Law applied to data."*

**Prime invariant of this blueprint:** **No `dict[str, Any]`. No `Any`. No untyped JSON strings. No free-form status strings.** Every property typed. Every link explicit. Every state mutation an Action.

---

## Section 1 — The Core Four Objects

### 1.1 `Task` — Unit of Work

**Current location:** `dharma_swarm/models.py:156`

**Status:** Exists, ~80% strict, two known violations to eradicate.

```python
class Task(BaseModel):
    # Identity
    id: TaskId                         # NEW: typed wrapper, was bare str
    title: str                         # ≤ 200 chars (validated)
    description: str = ""              # ≤ 4000 chars (validated)

    # State
    status: TaskStatus                 # enum: PENDING|ASSIGNED|RUNNING|COMPLETED|FAILED|CANCELLED
    priority: TaskPriority             # enum: LOW|NORMAL|HIGH|URGENT

    # Authorship & assignment (LINKS, see §2)
    created_by: AgentRef               # typed Link, replaces `str = "system"`
    assigned_to: AgentRef | None       # typed Link, replaces `Optional[str]`

    # Time
    created_at: datetime               # UTC, factory-defaulted
    updated_at: datetime               # UTC, factory-defaulted

    # Graph (typed N:M LINKS, see §2)
    depends_on: list[TaskRef]          # was list[str]
    blocked_by: list[TaskRef]          # was list[str]

    # Output
    result: TaskResult | None          # NEW: structured, was Optional[str]

    # Routing & semantics (PROPOSED nested model, eradicates dict[str, Any])
    routing: TaskRouting               # NEW: was metadata: dict[str, Any]
    stigmergy: StigmergySalience       # NEW: was buried in metadata
    tool_hints: ToolHints              # NEW: was buried in metadata
```

**Nested types:**

```python
class TaskId(str):
    """16-char hex UUID prefix, validated."""

class TaskRef(BaseModel):
    """Typed reference to another Task. Stronger than a bare ID."""
    task_id: TaskId
    title_snapshot: str       # for log readability without dereferencing

class TaskResult(BaseModel):
    """Structured result, replaces Optional[str]."""
    summary: str                              # human-readable one-liner
    artifacts: list[ArtifactRef]              # produced artifacts (LINK)
    memory_facts: list[MemoryFactRef]         # facts recorded (LINK)
    metrics: TaskMetrics                      # numeric summary
    completion_kind: TaskCompletionKind       # enum: SUCCESS|PARTIAL|TIMEOUT|GATE_REJECTED
    error: TaskError | None                   # populated only on FAILED

class TaskMetrics(BaseModel):
    duration_seconds: float
    tokens_used: int
    tool_calls_made: int
    gate_checks_run: int
    gate_checks_passed: int

class TaskError(BaseModel):
    error_kind: ErrorKind                     # enum: TIMEOUT|EXCEPTION|GATE_BLOCK|TOOL_FAILURE|PROVIDER_ERROR
    message: str                              # ≤ 2000 chars
    traceback: str | None                     # only for EXCEPTION kind
    gate_id: str | None                       # only for GATE_BLOCK kind

class TaskRouting(BaseModel):
    """Replaces routing keys formerly in metadata dict."""
    preferred_role: AgentRole | None
    preferred_provider: ProviderType | None
    preferred_model: str | None               # validated against known models
    topology: TopologyType                    # enum: FAN_OUT|FAN_IN|PIPELINE|BROADCAST
    timeout_seconds: float                    # > 0
    max_turns: int                            # > 0

class StigmergySalience(BaseModel):
    """Replaces stigmergy keys formerly in metadata dict."""
    pheromone_strength: float                 # 0.0..1.0
    decay_rate: float                         # half-life in seconds
    trail_marker: str | None                  # tag for path-tracing

class ToolHints(BaseModel):
    """Replaces tool_flag keys formerly in metadata dict."""
    required_tools: list[ToolRef]             # tools that MUST be available
    forbidden_tools: list[ToolRef]            # tools that MUST NOT fire
    sandboxed: bool                           # require LocalSandbox

class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
```

**Invariants (enforced at ingress):**
- `assigned_to` MUST be `None` when `status == PENDING`.
- `assigned_to` MUST be set when `status ∈ {ASSIGNED, RUNNING, COMPLETED, FAILED}`.
- `result` MUST be set when `status == COMPLETED`.
- `result.error` MUST be set iff `status == FAILED`.
- `depends_on` MUST be acyclic across the active graph.

---

### 1.2 `AgentIdentity` — Who Acts

**Current location:** `dharma_swarm/models.py:173` (currently named `AgentConfig`).

**Status:** Four competing schemas exist (per `AGENT_IDENTITY_UNIFICATION.md`). This blueprint **renames `AgentConfig` → `AgentIdentity`** as the canonical model, with `AgentState` (separate) holding mutable runtime state.

```python
class AgentIdentity(BaseModel):
    """The CANONICAL identity record. Immutable after creation (see Actions)."""

    # Identity
    id: AgentId                       # 16-char hex UUID (typed)
    name: str                         # human-readable, unique within swarm
    display_name: str                 # presentation form
    role: AgentRole                   # ROLE TAXONOMY (grouped, see below)

    # LLM binding (LINK to provider)
    provider: ProviderType            # enum, 18 values
    model: ModelRef                   # NEW typed: was bare str

    # Personality
    system_prompt: str                # ≤ 32K chars

    # Capability surface
    tools: list[ToolRef]              # NEW typed: was list[str]
    autonomy: AutonomyLevel           # enum: LOCKED|CAUTIOUS|BALANCED|AGGRESSIVE|FULL

    # Resource budget
    max_turns: int                    # > 0
    temperature: float                # 0.0..2.0
    max_tokens: int                   # > 0
    context_budget: int               # > 0
    timeout_seconds: int              # > 0
    wake_interval_seconds: int        # > 0

    # Workspace
    working_directory: WorkspacePath  # NEW typed, validated against allowed roots

    # Classification
    role_group: AgentRoleGroup        # NEW: groups the 18-flat AgentRole values
    tags: list[Tag]                   # NEW typed (validated tag set)

    # No metadata: dict[str, Any] — every prior key is now an explicit field
```

**Nested types:**

```python
class AgentId(str):
    """16-char hex UUID, validated."""

class AgentRef(BaseModel):
    agent_id: AgentId
    name_snapshot: str

class ModelRef(BaseModel):
    """Typed model identifier; validated against the model_hierarchy registry."""
    model_id: str
    provider: ProviderType
    family: ModelFamily              # enum: CLAUDE|GPT|MISTRAL|LLAMA|GEMINI|QWEN|...
    revision: str | None

class ToolRef(BaseModel):
    """Typed tool reference. Replaces bare `list[str]`."""
    tool_name: str
    schema_version: str              # tool definitions versioned independently
    permission_scope: ToolScope      # enum: READ_ONLY|WRITE|NETWORK|SYSTEM|DESTRUCTIVE

class WorkspacePath(str):
    """Path validated against ~/dharma_swarm/ + allowed worktrees."""

class Tag(str):
    """Validated tag (lowercase, kebab-case, ≤ 32 chars)."""

class AgentRoleGroup(str, Enum):
    """Resolves the flat 18-role mess flagged in models-schema gap analysis."""
    FUNCTIONAL = "functional"          # CODER, REVIEWER, RESEARCHER, TESTER, ORCHESTRATOR, GENERAL, WORKER
    PSMV_COGNITIVE = "psmv_cognitive"  # CARTOGRAPHER, ARCHEOLOGIST, SURGEON, ARCHITECT, VALIDATOR, CONDUCTOR
    CONSTITUTIONAL = "constitutional"  # OPERATOR, ARCHIVIST, RESEARCH_DIRECTOR, SYSTEMS_ARCHITECT, STRATEGIST, WITNESS

class AgentRole(str, Enum):
    # Functional
    CODER = "coder"; REVIEWER = "reviewer"; RESEARCHER = "researcher"
    TESTER = "tester"; ORCHESTRATOR = "orchestrator"; GENERAL = "general"
    WORKER = "worker"
    # PSMV cognitive
    CARTOGRAPHER = "cartographer"; ARCHEOLOGIST = "archeologist"
    SURGEON = "surgeon"; ARCHITECT = "architect"
    VALIDATOR = "validator"; CONDUCTOR = "conductor"
    # Constitutional
    OPERATOR = "operator"; ARCHIVIST = "archivist"
    RESEARCH_DIRECTOR = "research_director"
    SYSTEMS_ARCHITECT = "systems_architect"
    STRATEGIST = "strategist"; WITNESS = "witness"

class AutonomyLevel(str, Enum):
    LOCKED = "locked"; CAUTIOUS = "cautious"; BALANCED = "balanced"
    AGGRESSIVE = "aggressive"; FULL = "full"

class ProviderType(str, Enum):
    """18 values. PROPOSAL: add `deprecated_at: datetime | None` per provider in a registry."""
    ANTHROPIC = "anthropic"; OPENAI = "openai"; OPENROUTER = "openrouter"
    NVIDIA_NIM = "nvidia_nim"; LOCAL = "local"; CLAUDE_CODE = "claude_code"
    CODEX = "codex"; OPENROUTER_FREE = "openrouter_free"; OLLAMA = "ollama"
    GROQ = "groq"; CEREBRAS = "cerebras"; SILICONFLOW = "siliconflow"
    TOGETHER = "together"; FIREWORKS = "fireworks"; GOOGLE_AI = "google_ai"
    SAMBANOVA = "sambanova"; MISTRAL = "mistral"; CHUTES = "chutes"
```

**Companion runtime model — `AgentState` stays separate (already exists):**

```python
class AgentState(BaseModel):
    """Mutable runtime state. Identity is immutable; state changes constantly."""
    agent_id: AgentId                 # LINK to AgentIdentity (1:1)
    status: AgentStatus               # enum: IDLE|BUSY|STARTING|STOPPING|DEAD
    current_task: TaskRef | None      # was Optional[str]
    started_at: datetime | None
    last_heartbeat: datetime | None
    turns_used: int
    tasks_completed: int
    error: AgentError | None          # NEW typed, was Optional[str]

class AgentError(BaseModel):
    error_kind: AgentErrorKind        # enum: PROVIDER_DOWN|TIMEOUT|GATE_VIOLATION|CRASH
    message: str
    occurred_at: datetime
    recoverable: bool
```

**Invariants:**
- `AgentIdentity` is immutable after creation. Any change → new `AgentIdentity` row + lineage link.
- `AgentState.agent_id` MUST resolve to an existing `AgentIdentity`.
- `AgentState.status == DEAD` ⇒ no further mutations allowed; replace, don't update.

---

### 1.3 `Artifact` — Typed Output of Work

**Current location:** `dharma_swarm/handoff.py:56`

**Status:** Exists with 8 types but uses untyped `content: str` + `metadata: dict[str, Any]`. **This blueprint converts to a discriminated union** so each `ArtifactType` carries its own strict payload.

```python
# Discriminated union: the artifact_type field disambiguates the payload type
Artifact = Annotated[
    Union[
        CodeDiffArtifact,
        AnalysisArtifact,
        TestResultsArtifact,
        ContextArtifact,
        PlanArtifact,
        FileListArtifact,
        ErrorReportArtifact,
        MetricArtifact,
    ],
    Field(discriminator="artifact_type")
]

class _ArtifactBase(BaseModel):
    """Common fields. Every concrete subclass adds artifact_type Literal + payload."""
    id: ArtifactId
    summary: str                      # ≤ 200 chars
    created_by: AgentRef              # LINK
    created_at: datetime
    files_touched: list[FilePath]     # NEW typed, was list[str]
    task: TaskRef                     # LINK back to producing Task
    handoff: HandoffRef | None        # LINK if part of a handoff

class CodeDiffArtifact(_ArtifactBase):
    artifact_type: Literal["code_diff"] = "code_diff"
    diff_format: DiffFormat           # enum: UNIFIED|GIT_PATCH
    diff_text: str                    # the actual diff
    base_ref: str                     # commit/branch the diff applies to
    files_changed: int
    lines_added: int
    lines_removed: int

class AnalysisArtifact(_ArtifactBase):
    artifact_type: Literal["analysis"] = "analysis"
    analysis_kind: AnalysisKind       # enum: SECURITY|PERFORMANCE|ARCHITECTURE|REVIEW|...
    findings: list[Finding]           # structured, see below
    confidence: float                 # 0.0..1.0

class TestResultsArtifact(_ArtifactBase):
    artifact_type: Literal["test_results"] = "test_results"
    framework: TestFramework          # enum: PYTEST|JEST|GOTEST|...
    total: int; passed: int; failed: int; skipped: int
    failures: list[TestFailure]
    duration_seconds: float
    coverage_percent: float | None

class ContextArtifact(_ArtifactBase):
    artifact_type: Literal["context"] = "context"
    context_kind: ContextKind         # enum: CODE_TOUR|CONCEPT_MAP|HISTORY|REQUIREMENTS
    body_markdown: str
    references: list[FilePath | MemoryFactRef]

class PlanArtifact(_ArtifactBase):
    artifact_type: Literal["plan"] = "plan"
    steps: list[PlanStep]
    estimated_duration_seconds: float

class FileListArtifact(_ArtifactBase):
    artifact_type: Literal["file_list"] = "file_list"
    files: list[FilePath]
    reason: str

class ErrorReportArtifact(_ArtifactBase):
    artifact_type: Literal["error_report"] = "error_report"
    error_kind: ErrorKind
    message: str
    traceback: str | None
    reproduction_steps: list[str]
    suspected_cause: str | None

class MetricArtifact(_ArtifactBase):
    artifact_type: Literal["metric"] = "metric"
    metric_name: str
    value: float
    unit: MetricUnit                  # enum: SECONDS|BYTES|TOKENS|PERCENT|COUNT|RATIO
    context: str                      # what produced this measurement
```

**Supporting nested types** (Finding, TestFailure, PlanStep, FilePath, etc.) defined inline — all strict.

`Handoff` (the wrapper that carries Artifacts) keeps its existing shape but gains:

```python
class HandoffStatus(str, Enum):
    """Replaces Handoff.status: str (free-form)."""
    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"

class Handoff(BaseModel):
    id: HandoffId
    from_agent: AgentRef              # LINK
    to_agent: AgentRef | BroadcastTarget  # LINK or sentinel
    task: TaskRef                     # LINK (replaces task_context: str)
    artifacts: list[Artifact]         # 1:N owned
    priority: HandoffPriority         # enum: BLOCKING|IMPORTANT|INFORMATIONAL
    requires_ack: bool
    status: HandoffStatus             # enum, replaces str
    reject_reason: str | None         # only when status == REJECTED
    created_at: datetime
    delivered_at: datetime | None
    acknowledged_at: datetime | None
```

---

### 1.4 `MemoryFact` — A Trusted Belief

**Current location:** Two competing models today —
- `dharma_swarm/models.py:267` (`MemoryEntry`, layered: IMMEDIATE/SESSION/DEVELOPMENT/WITNESS/META)
- `dharma_swarm/chetana/provenance.py` (`FrontmatterSchema`, atom-based, gate-checked, axiom-signed)

**This blueprint unifies them as `MemoryFact`** — chetana's atom schema becomes the canonical contract; the legacy `MemoryEntry.layer` becomes a typed annotation on `MemoryFact`, not a separate class.

```python
class MemoryFact(BaseModel):
    """Canonical memory unit. Replaces both MemoryEntry and chetana FrontmatterSchema."""

    # Identity
    atom_id: AtomId                   # uuid4, validated
    title: str
    schema_version: str = "1.0.0"     # NEW: was implicit; now explicit per gap analysis
    chetana_version: str = "0.1.0"

    # Classification
    fact_type: FactType               # enum: ATOMIC|REFERENCE|METHOD|FRAMEWORK|SPEC|TOOL|CONCEPT|DECISION
    para_class: PARAClass | None      # enum: P|A|R|Ar
    layer: MemoryLayer                # enum: IMMEDIATE|SESSION|DEVELOPMENT|WITNESS|META
    confidence: Confidence            # 0.0..1.0 validated

    # Sources (1:N LINKS)
    sources: list[FactSource]         # was AtomSource — at least 1

    # Provenance (only on TRUSTED facts; None on STAGED)
    provenance: FactProvenance | None

    # Lifecycle
    review_status: ReviewStatus       # enum: STAGED|APPROVED|REJECTED|AUTO_PROMOTED
    stale_after: date                 # ISO date, validated

    # Graph (N:M LINKS, see §2)
    related: list[MemoryFactRef]      # was list[str] of [[wikilinks]]
    tags: list[Tag]                   # NEW typed

    # Body
    body_markdown: str

class FactSource(BaseModel):
    """Was AtomSource. Strictly typed."""
    kind: SourceKind                  # enum: SESSION|WEBCLIP|PDF|NOTE|WIKI_EXTRACT|VOICE|EXTERNAL|SYNTHESIS
    path: SourcePath                  # NEW typed, validated
    span: SourceSpan | None           # NEW typed, was free-form str
    captured_at: datetime             # was string; now datetime
    captured_by: AgentRef             # was string; now LINK

class SourceSpan(BaseModel):
    kind: SpanKind                    # enum: LINE_RANGE|TIME_RANGE|BYTE_RANGE
    start: int
    end: int

class FactProvenance(BaseModel):
    """Was AtomProvenance. revival_chain is now strictly typed."""
    promoted_by: AgentRef             # was str; now LINK
    promoted_at: datetime
    gate_check: GateCheckRecord       # already strict
    axiom_signature: KernelSignature  # 64-char sha256 hex (validated)
    review_status: ReviewStatus
    reviewer: AgentRef | None         # was str; now LINK
    revival_chain: list[RevivalEvent] # was list[dict[str, Any]] — now strict

class RevivalEvent(BaseModel):
    """Eradicates list[dict[str, Any]] in revival_chain."""
    revival_id: str
    revived_at: datetime
    revived_by: AgentRef              # LINK
    prior_signature: KernelSignature  # the signature this revival replaces
    neighbors_added: list[MemoryFactRef]
    questions_resolved: list[str]
    rationale: str

class GateCheckRecord(BaseModel):
    """Already strict in chetana/provenance.py."""
    result: GateResult                # enum: ALLOW|WARN|BLOCK
    gates_passed: list[GateId]        # was list[str]; now typed
    gates_warned: list[GateId]
    gates_blocked: list[GateId]
    rationale: str | None
    checked_at: datetime              # was string; now datetime
    checked_by: AgentRef              # NEW: was implicit
    kernel_manifest: KernelManifestRef  # NEW: which kernel version evaluated

class KernelSignature(str):
    """64-char lowercase sha256 hex. Validated."""

class GateId(str, Enum):
    """11 gates from TelosGatekeeper, finally enumerated rather than free-string."""
    G1_AHIMSA = "g1_ahimsa"
    G2_SATYA = "g2_satya"
    G3_ASTEYA = "g3_asteya"
    G4_BRAHMACHARYA = "g4_brahmacharya"
    G5_APARIGRAHA = "g5_aparigraha"
    G6_SAUCHA = "g6_saucha"
    G7_SANTOSHA = "g7_santosha"
    G8_TAPAS = "g8_tapas"
    G9_SVADHYAYA = "g9_svadhyaya"
    G10_ISHVARA_PRANIDHANA = "g10_ishvara_pranidhana"
    G11_TELIC_COHERENCE = "g11_telic_coherence"
    # exact set: enumerate from telos_gates.py at adoption time

class Confidence(float):
    """Validated 0.0..1.0."""

class FactType(str, Enum):
    ATOMIC = "atomic"; REFERENCE = "reference"; METHOD = "method"
    FRAMEWORK = "framework"; SPEC = "spec"; TOOL = "tool"
    CONCEPT = "concept"; DECISION = "decision"

class ReviewStatus(str, Enum):
    STAGED = "staged"
    APPROVED = "approved"             # human review accepted
    REJECTED = "rejected"
    AUTO_PROMOTED = "auto_promoted"   # ALLOW + auto_promote=True, no human in loop

class PARAClass(str, Enum):
    P = "P"   # Project
    A = "A"   # Area
    R = "R"   # Resource
    Ar = "Ar" # Archive
```

**Invariants:**
- `provenance` MUST be `None` when `review_status == STAGED`.
- `provenance` MUST be set when `review_status ∈ {APPROVED, AUTO_PROMOTED}`.
- `review_status == REJECTED` ⇒ atom is read-only and excluded from queries.
- `axiom_signature` MUST verify against `kernel_manifest` at promotion time (chetana/provenance.py:148 `compute_axiom_signature`).
- `stale_after` < today ⇒ atom enters revival queue, NOT exile (per CLAUDE.md `"stale is the trigger for re-integration, not exile"`).

---

## Section 2 — Explicit Links (The Graph)

The semantic ontology wiki promises *"16 Types · 42 Edges."* This blueprint enumerates the edges among the Core Four (subset).

| From | Edge | To | Cardinality | Owns/Refers | Notes |
|---|---|---|---|---|---|
| Task | `AssignedTo` | AgentIdentity | N:1 (nullable) | refers | Set by `AssignTask` action only |
| Task | `CreatedBy` | AgentIdentity \| SystemActor | N:1 | refers | Sentinel `system` value disallowed; must be typed AgentRef or SystemActor enum |
| Task | `DependsOn` | Task | N:M | refers | Acyclic invariant |
| Task | `BlockedBy` | Task | N:M | refers | Subset semantics: BlockedBy ⊂ DependsOn |
| Task | `Produces` | Artifact | 1:N | owns | Set by `RecordArtifact` action |
| Task | `Records` | MemoryFact | 1:N | owns | Set by `StageMemoryFact` action when fact is born from this Task |
| Task | `Result.Metrics` | TaskMetrics | 1:1 | owns | Embedded |
| AgentIdentity | `HasState` | AgentState | 1:1 | refers | AgentState carries `agent_id` back-reference |
| AgentIdentity | `UsesProvider` | ProviderType | N:1 (enum) | refers | Provider validity from registry |
| AgentIdentity | `UsesModel` | ModelRef | N:1 | refers | Validated against model_hierarchy |
| AgentIdentity | `HasRole` | AgentRole | N:1 (enum) | refers | Grouped by AgentRoleGroup |
| AgentIdentity | `HasTools` | ToolRef | N:M | refers | Tools have permission scope |
| Artifact | `CreatedBy` | AgentIdentity | N:1 | refers | Always set |
| Artifact | `PartOf` | Handoff | N:1 (nullable) | refers | Artifact may exist without a Handoff |
| Artifact | `BelongsTo` | Task | N:1 | refers | Always set; replaces task_context: str |
| Artifact | `References` | FilePath | 1:N | refers | files_touched, validated |
| Handoff | `From` | AgentIdentity | N:1 | refers | sender |
| Handoff | `To` | AgentIdentity \| BroadcastTarget | N:1 | refers | sentinel `*` becomes typed BroadcastTarget |
| Handoff | `About` | Task | N:1 | refers | replaces task_context: str |
| Handoff | `Carries` | Artifact | 1:N | owns | Strong ownership |
| MemoryFact | `AbstractedFrom` | FactSource | 1:N | owns | At least 1 |
| MemoryFact | `PromotedBy` | AgentIdentity | N:1 (nullable) | refers | None on STAGED, set on APPROVED/AUTO_PROMOTED |
| MemoryFact | `GateChecked` | GateCheckRecord | 1:1 | owns | Embedded in provenance |
| MemoryFact | `SignedBy` | KernelManifestRef | N:1 | refers | Binds to specific kernel version |
| MemoryFact | `Related` | MemoryFact | N:M | refers | The wiki [[link]] graph |
| MemoryFact | `RevivedBy` | RevivalEvent[] | 1:N | owns | Append-only chain |

**Cardinality enforcement:** at the persistence boundary (the `Action` layer, §3) — not at the in-memory Pydantic boundary, since Pydantic doesn't enforce cross-row referential integrity. Persistence is responsible for foreign key validity.

---

## Section 3 — Authorized Actions (The Mutation Layer)

**Principle:** every state transition shipped through a strict-typed Action. No direct mutation of fields. The Action layer is the single mutation surface — analogous to Palantir's Foundry Actions.

**Action contract:**

```python
class Action(BaseModel):
    action_id: ActionId               # uuid4
    action_kind: ActionKind           # enum, see below
    actor: AgentRef                   # who's mutating
    payload: ActionPayload            # discriminated union by action_kind
    issued_at: datetime
    idempotency_key: str | None       # for retry safety

class ActionResult(BaseModel):
    action_id: ActionId
    status: ActionStatus              # enum: APPLIED|REJECTED|GATE_BLOCKED
    gate_check: GateCheckRecord | None  # set if action ran through telos gates
    new_state: ObjectRef              # reference to the mutated object
    error: ActionError | None
```

### 3.1 Task actions

| Action | Payload | Pre-state | Post-state | Notes |
|---|---|---|---|---|
| `CreateTask` | `CreateTaskPayload(title, description, priority, created_by, depends_on, routing, stigmergy, tool_hints)` | — | Task[status=PENDING] | Title/desc length-validated |
| `AssignTask` | `AssignTaskPayload(task_id, agent_id)` | PENDING | ASSIGNED | Verifies agent exists and is IDLE |
| `StartTask` | `StartTaskPayload(task_id)` | ASSIGNED | RUNNING | Sets `started_at` on AgentState |
| `CompleteTask` | `CompleteTaskPayload(task_id, result: TaskResult)` | RUNNING | COMPLETED | Result must validate; gate-check before commit |
| `FailTask` | `FailTaskPayload(task_id, error: TaskError)` | RUNNING | FAILED | error.error_kind required |
| `CancelTask` | `CancelTaskPayload(task_id, reason: str)` | PENDING\|ASSIGNED\|RUNNING | CANCELLED | Idempotent |
| `RouteTask` | `RouteTaskPayload(task_id, routing: TaskRouting)` | PENDING | PENDING | Updates routing; does NOT assign |

### 3.2 AgentIdentity actions

| Action | Payload | Pre-state | Post-state | Notes |
|---|---|---|---|---|
| `RegisterAgent` | `RegisterAgentPayload(name, role, provider, model, system_prompt, tools, autonomy, ...)` | — | AgentIdentity created + AgentState[IDLE] | Identity is immutable post-creation |
| `StartAgent` | `StartAgentPayload(agent_id)` | IDLE | STARTING→BUSY | Asynchronous transition |
| `StopAgent` | `StopAgentPayload(agent_id, reason)` | BUSY\|IDLE | STOPPING→DEAD | Tasks held are reassigned via `ReassignAbandoned` |
| `Heartbeat` | `HeartbeatPayload(agent_id)` | BUSY\|IDLE | unchanged | Refreshes `last_heartbeat` |
| `RecordTurn` | `RecordTurnPayload(agent_id, turns_delta)` | BUSY | unchanged | Atomically increments `turns_used` |
| `ReplaceIdentity` | `ReplaceIdentityPayload(old_agent_id, new_identity, reason)` | DEAD | new AgentIdentity | Used for evolution; preserves lineage link |

### 3.3 Artifact / Handoff actions

| Action | Payload | Pre-state | Post-state | Notes |
|---|---|---|---|---|
| `RecordArtifact` | `RecordArtifactPayload(task_id, artifact: Artifact)` | Task RUNNING\|COMPLETED | Artifact created | Discriminated-union validated |
| `CreateHandoff` | `CreateHandoffPayload(from_agent, to_agent, task_id, artifacts, priority, requires_ack)` | — | Handoff[PENDING] | task_id replaces task_context: str |
| `DeliverHandoff` | `DeliverHandoffPayload(handoff_id)` | PENDING | DELIVERED | Sets delivered_at |
| `AcknowledgeHandoff` | `AcknowledgeHandoffPayload(handoff_id, by_agent)` | DELIVERED | ACKNOWLEDGED | Idempotent |
| `RejectHandoff` | `RejectHandoffPayload(handoff_id, by_agent, reason)` | PENDING\|DELIVERED | REJECTED | reason required |

### 3.4 MemoryFact actions

| Action | Payload | Pre-state | Post-state | Notes |
|---|---|---|---|---|
| `StageMemoryFact` | `StageMemoryFactPayload(title, fact_type, body_markdown, sources, related, tags, captured_by)` | — | MemoryFact[STAGED] | provenance=None |
| `PromoteMemoryFact` | `PromoteMemoryFactPayload(atom_id, kernel_manifest_ref, promoted_by, auto: bool)` | STAGED | AUTO_PROMOTED \| APPROVED \| REJECTED | Routes through telos gates; gate result determines post-state |
| `RejectMemoryFact` | `RejectMemoryFactPayload(atom_id, by_agent, gate_check, reason)` | STAGED | REJECTED | Always carries the gate_check that justified rejection |
| `ReviveMemoryFact` | `ReviveMemoryFactPayload(atom_id, by_agent, neighbors_added, questions_resolved, rationale)` | any non-REJECTED | append RevivalEvent + reset stale_after | NEVER deletes; only re-integrates |
| `LinkMemoryFacts` | `LinkMemoryFactsPayload(source_id, target_id, relation_kind, by_agent)` | — | edge added | Bidirectional |
| `UnlinkMemoryFacts` | `UnlinkMemoryFactsPayload(source_id, target_id, by_agent, reason)` | edge exists | edge removed | Audited |

### 3.5 Action dispatch invariants

1. **Every action runs through `TelosGatekeeper.check(action)`** before commit. Tier-A gate fail ⇒ ActionStatus.GATE_BLOCKED.
2. **Every applied action emits a `MemoryFact` of type `decision`** auto-staged into the audit layer. The audit trail IS a memory layer, not a separate log.
3. **Idempotency:** actions with the same `idempotency_key` collapse — second call returns the first result.
4. **No direct mutation:** any code path that mutates a Core Four object outside the Action layer is a bug. `gitnexus_impact` should flag any caller that does so.

---

## Section 4 — Graveyard (Deprecated Concepts)

Below is what to **stop using** as the Core Four ontology takes effect. Each entry has a current code location for reference.

### 4.1 Untyped escape hatches (highest priority to eradicate)

| Deprecated | Where it lives today | Replacement |
|---|---|---|
| `Task.metadata: dict[str, Any]` | `models.py:170` | Split into `routing: TaskRouting`, `stigmergy: StigmergySalience`, `tool_hints: ToolHints` |
| `AgentConfig.metadata: dict[str, Any]` | `models.py:192` | Renamed to `AgentIdentity` with explicit fields; metadata removed |
| `Message.metadata: dict[str, Any]` | `models.py:255` | Replace with `MessageContext` (out of Core Four scope, but same rule) |
| `TaskDispatch.metadata: dict[str, Any]` | `models.py:297` | Subsume into `TaskRouting`; remove TaskDispatch as a separate type |
| `Handoff` (no Pydantic field, but) `task_context: str` | `handoff.py:71` | Replace with `task: TaskRef` |
| `Handoff.status: str` | `handoff.py:76` | Replace with `HandoffStatus` enum |
| `Artifact.metadata: dict[str, Any]` | `handoff.py:63` | Eradicated by discriminated-union artifact types |
| `LLMRequest.messages: list[dict[str, Any]]` | `models.py:312` | `list[ChatMessage]` (out of Core Four; same rule) |
| `LLMRequest.tools: list[dict[str, Any]]` | `models.py:316` | `list[ToolDefinition]` |
| `LLMResponse.usage: dict[str, int]` | `models.py:324` | `TokenUsage` BaseModel |
| `LLMResponse.tool_calls: list[dict[str, Any]]` | `models.py:325` | `list[ToolCall]` |
| `SwarmState.organism: dict[str, Any] \| None` | `models.py:288` | `OrganismSnapshot \| None` (BaseModel) |
| `AtomProvenance.revival_chain: list[dict[str, Any]]` | `chetana/provenance.py:95` | `list[RevivalEvent]` |
| `AgentState.provider: str = ""` | `models.py:238` | `provider: ProviderType` (consistent with AgentIdentity) |
| `AgentState.model: str = ""` | `models.py:239` | `model: ModelRef` |
| `AgentConfig.tools: list[str]` | `models.py:191` | `list[ToolRef]` |
| `Task.assigned_to: Optional[str]` | `models.py:163` | `AgentRef \| None` |
| `Task.created_by: str = "system"` | `models.py:164` | `AgentRef \| SystemActor` |
| `Task.depends_on: list[str]` | `models.py:167` | `list[TaskRef]` |
| `Task.blocked_by: list[str]` | `models.py:168` | `list[TaskRef]` |
| `Task.result: Optional[str]` | `models.py:169` | `TaskResult \| None` |

### 4.2 Competing schemas (collapse into canonical)

| Deprecated | Where it lives today | Canonical replacement |
|---|---|---|
| The four agent identity schemas | per `AGENT_IDENTITY_UNIFICATION.md` | `AgentIdentity` (this blueprint) |
| `MemoryEntry` | `models.py:267` | `MemoryFact` (this blueprint, chetana-derived) |
| `chetana.FrontmatterSchema` direct | `chetana/provenance.py:105` | Same physical class, but renamed/aliased to `MemoryFact` so the rest of the swarm sees one type |
| Three competing memory layers (`MemoryLayer` enum, `chetana` atoms, `StrangeLoopMemory.MemoryEntry`) | scattered | One `MemoryFact` with a `layer: MemoryLayer` field; chetana provenance attached |
| `TaskDispatch` as a separate type | `models.py:291` | Folded into `TaskRouting` + `AssignTask`/`StartTask` actions |

### 4.3 Implicit / unaudited mutations (now disallowed)

| Deprecated mutation | Replacement |
|---|---|
| Setting `Task.status = "running"` directly | Must go through `StartTask` Action |
| Setting `Task.assigned_to = "agent_x"` directly | Must go through `AssignTask` Action |
| Updating `AgentState` fields without a heartbeat record | `Heartbeat` / `RecordTurn` Actions |
| Writing memory atoms directly to disk | Must go through `StageMemoryFact` → `PromoteMemoryFact` |
| `Handoff.status = "delivered"` direct mutation | `DeliverHandoff` Action |
| Free-form `metadata` dict reads/writes anywhere | Use the explicit field; if a key isn't yet a field, that's a schema bug, not an excuse to use a dict |

### 4.4 Missing types (gap analysis from `models-schema.md`)

These are explicitly named gaps in the wiki atom. They live in their owning modules but never made it to the shared schema. **Adding them is the next layer of work after Core Four lands:**

| Missing | Owning module | Should be in shared schema |
|---|---|---|
| `StageTransition` | `telos_gates.py` | Yes — every gate transition is a state mutation worth typing |
| `RoutingDecision` | model routing layer | Yes — replaces ad-hoc routing dicts |
| `EvolutionGenome` | `evolution.py` (DarwinEngine) | Yes — agent mutation must round-trip through schema |
| `KernelManifest` | `dharma_kernel.py` | Yes — already SHA-256 signed; needs Pydantic envelope |
| `TelosGate` | `telos_gates.py` | Yes — 11 gates, currently keyed by string |

### 4.5 Concepts to retire entirely

- **Free-string status fields anywhere.** Every status transitions to an enum. No exceptions.
- **`"system"` as a sentinel actor string.** Replaced by typed `SystemActor` (a singleton `AgentIdentity`-shaped record with provenance).
- **`task_context: str`** as a substitute for a typed Task reference. Always use `TaskRef`.
- **Per-module type definitions.** If two modules need a `Task`, they import it from `models.py`. No locally-defined `Task`-shaped dataclasses anywhere.
- **`metadata` as a catch-all anywhere.** Schema violation. Add explicit fields.

---

## Section 5 — Migration Boundaries (what the blueprint does NOT decide)

The blueprint intentionally stops short of:

1. **Persistence layer.** SQLite vs Postgres vs JSONL — orthogonal. Pydantic models serialize/deserialize either way.
2. **Wire protocol.** GraphQL (already in `api/graphql/schema.py`) vs REST vs gRPC — these are projections of the same ontology.
3. **Action dispatch implementation.** Whether the Action layer is a Python service, a Postgres `INSERT … RETURNING`, or a queue consumer — all are valid.
4. **The remaining 12+ models** (Message, GateCheckResult outside FactProvenance, SwarmState, SandboxResult, LLMRequest, LLMResponse, LoopDomain, LoopResult, CatalyticEdge, ForgeScore, SystemVitals). Same strict-typing rules apply; out of scope for this Core Four document.
5. **The 16 Types / 42 Edges** in the semantic-ontology wiki atom — Core Four covers ~4 types and ~24 edges. The remaining 12 types and 18 edges are next-pass work.

---

## Section 6 — Cross-references

- `dharma_swarm/CLAUDE.md` Transcendence Principle ⇒ `AgentRoleGroup` typing matters because it underwrites diversity measurement.
- `INTERFACE_MISMATCH_MAP.md` ⇒ many of the 13 documented mismatches are direct consequences of `dict[str, Any]` escape hatches; eradicating them closes the mismatch class.
- `MODEL_ROUTING_MAP.md` ⇒ `ModelRef` and the registry-validated `provider` field formalize the 5 inconsistencies between swarm/CLI/dashboard model resolution.
- `AGENT_IDENTITY_UNIFICATION.md` ⇒ this blueprint's `AgentIdentity` is the canonical target of that unification.
- `BUILD_SESSION_ENTRYPOINT.md` ⇒ ontology-native operator-brief seam is the user-visible justification for landing this blueprint; current substrate-nativeness is ~10–15%.
- Wiki: `[[models-schema]]`, `[[semantic-ontology]]`, `[[dharma-swarm]]`, `[[telos-gates]]`, `[[catalytic-graph]]`, `[[strange-loop-memory]]`, `[[orchestrator]]`, `[[provider-architecture]]`.

---

## Section 7 — Adoption ordering (no implementation yet, just sequencing)

If this blueprint is adopted, the order of changes that minimizes blast radius:

1. **Add the new typed wrappers** (`TaskId`, `TaskRef`, `AgentId`, `AgentRef`, `AtomId`, etc.) as Pydantic types in `models.py` — non-breaking; existing string IDs deserialize into the wrappers.
2. **Add `MemoryFact`** as an alias of `chetana.FrontmatterSchema` in `models.py`; gradually retire `MemoryEntry`.
3. **Rename `AgentConfig` → `AgentIdentity`** with a deprecation alias for one quarter.
4. **Convert `Artifact` to discriminated union** — this is the largest refactor; gate it behind a feature flag in `handoff.py`.
5. **Eradicate `Task.metadata`** by introducing the three nested models and migrating callers via `gitnexus_rename`.
6. **Introduce the Action layer** as a thin facade over current direct mutations; route all callers through it.
7. **Lock down direct mutations** with a CI check that grep-fails on `Task.status =` and equivalents outside the Action layer.

Each step is a separate PR. Each PR runs `gitnexus_impact` on every renamed/changed symbol per `CLAUDE.md` rules.

---

**End of blueprint.** This is the contract. Everything else is implementation.

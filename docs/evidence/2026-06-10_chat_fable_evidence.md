# Fable 5 Evidence Run — 2026-06-10

**Repo:** `~/dharma_swarm` on `qwen/spine-adoption` @ HEAD `814e32496` ("refactor(terminal_bridge): extract 12 render methods (H-016)")
**State dir:** `~/.dharma/`
**Run:** Read-only audit by Fable 5 (Computer agent) on John's MacBook Pro M5 Max
**Cap:** ~90 minutes. Honest partial > complete speculation.

---

## TOP SUMMARY (10 lines)

1. **The running daemon doesn't load the audited code.** `dgc daemon-status` reports a stale PID file; the launchd `com.dharma.cron-daemon` plist sources `~/dharma_swarm_main_cutover/.env` *before* `~/dharma_swarm/.env`. Live editable install was last seen pointed at `~/dharma_swarm_cashclaw` on `cashclaw/revenue-hydra-v1`. Audited repo ≠ executing repo.
2. **No provider chain reaches a live model.** OPENAI_API_KEY in `.env` is rebound to a local Hermes bridge at `localhost:9421`; OLLAMA (port 11434) is dead; OPENROUTER/NVIDIA_NIM are `missing_config`; ANTHROPIC_API_KEY is absent — and every ~5min pulse since this morning fails with `"Claude bare mode requires ANTHROPIC_API_KEY"`.
3. **Loops are not closed.** `CYBERNETIC_LOOP_MAP.md` (audit 2026-05-20): **0** loops closed in production, **1** in test (Witness Auditor), 7 PARTIAL, 5 NO. Today is 2026-06-10.
4. **No live revenue.** `first_cash_receipt_status.md`: `revenue_usd=0`, decision=`hold_pending_business_idea_gauntlet`, `gauntlet_decision=HOLD`.
5. **Verifier stack is keyword/regex.** All 11 `CORE_GATES` in `telos_gates.py` are HARM_WORDS / FORCE_WORDS / regex pattern matches. `dogma_gate` is a numeric threshold; `steelman_gate` checks string length. **Zero LLM-backed gates, zero property-based checks.**
6. **Evolution archive is vacuously inflated.** `~/.dharma/evolution/archive.jsonl` has **11,179 entries**; first 100 sampled = 100/100 empty `diff`, 100/100 `status="applied"`. Status hardcoded at `dharma_swarm/evolution.py:1768,2534`; shadow mode strips diffs (`p.diff = ""` ~line 3200).
7. **State spine has two truths.** `ontology.db` (objects=20,897, links=12,115) and `runtime.db` (delegation_runs=3,495 — 2,028 failed / 1,444 completed / 23 stuck "running") share **0 cross-prefix linkage** (`ont-%` count in both = 0). Multiple instances of both DBs exist on disk. Last delegation_run write: Jun 9 14:38Z — daemon hasn't dispatched today.
8. **Mech-interp pipeline is fully isolated.** `transformer_lens` is **not installed**; it's referenced only as a research citation in two files. HF cache holds gemma-scope SAEs, mistral SAEs, Qwen2.5, pythia-1.4b — all unwired into `dharma_swarm/`.
9. **SABP/1.0 is aspiration.** Single in-code mention is a docstring at `dharma_swarm/ontology.py:2266`. No code resolves `sab_address` end-to-end. Several `docs/missions/SAB_DHARMIC_AGORA_*.md` exist describing intent.
10. **Phantom postmortem is real, fix is behavioral.** OCCRP/GFW Forest Defender/Methane Engine "Tier-1 ARJUNA MVPs" and a "Polsia interview" (actually a chatbot) propagated as canon for 6+ days starting 2026-05-27. Countermeasure documented in `~/.claude/projects/-Users-dhyana/memory/feedback_agent_generated_phantoms.md` is a behavioral rule about checking `originSessionId` — **no code gate prevents recurrence**.

---

## T0 — Operational Floor

### T0.1 — Provider chain & AgentRunner pulse

**VERDICT:** Daemon process is alive but emits failure pulses; no provider in `.env` reaches a live model from this repo right now. **STATUS: PARTIAL.**

**EVIDENCE:**
```
$ grep -E '^(OPENAI|ANTHROPIC|DEEPSEEK|OPENROUTER|NVIDIA|OLLAMA)' ~/dharma_swarm/.env
OPENAI_API_KEY=sk-…   # OPENAI_BASE_URL=http://localhost:9421/v1  (Hermes bridge)
DEEPSEEK_API_KEY=…
# (no ANTHROPIC_API_KEY, no OPENROUTER_API_KEY, no NVIDIA_NIM_API_KEY)

$ dgc provider-smoke
ollama:       unreachable (port 11434)
openrouter:   missing_config
nvidia_nim:   missing_config

$ dgc daemon-status
stale PID file at ~/.dharma/agent_runner.pid

$ tail -5 ~/.dharma/logs/pulse.log
2026-06-10T17:53:… pulse_fail: Claude bare mode requires ANTHROPIC_API_KEY
2026-06-10T17:58:… pulse_fail: Claude bare mode requires ANTHROPIC_API_KEY
2026-06-10T18:03:… pulse_fail: Claude bare mode requires ANTHROPIC_API_KEY
2026-06-10T18:08:… pulse_fail: Claude bare mode requires ANTHROPIC_API_KEY
2026-06-10T18:13:… pulse_fail: Claude bare mode requires ANTHROPIC_API_KEY

$ jq .last_shakti_at ~/.dharma/living_state.json
1781081487   # ~2min before this query — launchd is firing the script
```

**NOTE:** The Hermes bridge at `localhost:9421` is a real listener; the pulse failure says Claude code path is selected for the run, and that branch demands `ANTHROPIC_API_KEY`. So the daemon is animated by launchd but completes zero useful work per cycle.

---

### T0.2 — Cybernetic loop closure

**VERDICT:** 0 closed in prod, 1 closed in test, 7 PARTIAL, 5 NO. **STATUS: SUPPORTED.**

**EVIDENCE:** `CYBERNETIC_LOOP_MAP.md` (last audit 2026-05-20, file mtime confirms not touched since):

| State | Count | Examples |
|---|---|---|
| ✅ closed-in-prod | 0 | — |
| 🟡 closed-in-test | 1 | Witness Auditor (Loop 11) |
| ⚠️ PARTIAL | 7 | Swarm Task (1), Algedonic (3), Evolution (6), Telos-gate (7), S4→S3 (5), Federation (9), Capsule (10) |
| ❌ NO | 5 | Cash receipt (2), JIKOKU loop (4), Provider-routing (8), SABP federation handshake (12), Mech-interp closed feedback (13) |

**NOTE:** Loop 1 (Swarm Task) is blocked by T0.1 — no working provider means no actual loop closure is possible right now regardless of code state.

---

### T0.3 — Worktree synthesis report

**VERDICT:** Found. **STATUS: SUPPORTED.**

**EVIDENCE:**
- `docs/vision_maps/MASTER_2026-06-10_leverage_synthesis.md` — written today; 33-agent verification workflow `wf_c54d96cf`, 2.88M tokens, 1,691 tool calls, 35.8 min wall.
- Raw structured: `reports/recovery_wf_c54d96cf_2026-06-10.json` (188 KB).
- §5 "DISAGREEMENTS with ground brief" already exists in the synthesis; headline finding: **deploy split** between audited repo (`~/dharma_swarm`) and live install (`~/dharma_swarm_cashclaw` on `cashclaw/revenue-hydra-v1`).

**NOTE:** Synthesis §5.6 cites pulse-count "2,369" that maps to no on-disk artifact I could find — see UNASKED #2.

---

### T0.4 — Active track

**VERDICT:** `runtime-truth-spine-adoption-2026-06`. **STATUS: SUPPORTED.**

**EVIDENCE:** `docs/governance/ACTIVE_TRACK.yaml`
```
active_track: runtime-truth-spine-adoption-2026-06
opened: 2026-06-06
owner: "@AmitabhainArunachala"
ttl_days: 21
```

---

### T0.5 — First cash receipt status

**VERDICT:** No revenue, gauntlet says HOLD. **STATUS: SUPPORTED.**

**EVIDENCE:** `reports/revenue_wedge/first_cash_receipt_status.md`
```
track: first-cash-receipt-2026-05
revenue_usd: 0
decision: hold_pending_business_idea_gauntlet
gauntlet_decision: HOLD
```

---

## E1 — Durable Execution

**VERDICT:** launchd is the orchestrator; in-flight resume not implemented. **STATUS: PARTIAL.**

**EVIDENCE:**
```
$ ls ~/Library/LaunchAgents/com.dharma.*.plist | wc -l
13

$ grep -A2 '<key>EnvironmentVariables' ~/Library/LaunchAgents/com.dharma.cron-daemon.plist
# (sources ~/dharma_swarm_main_cutover/.env  THEN  ~/dharma_swarm/.env)

$ plutil -p ~/Library/LaunchAgents/com.dharma.cron-daemon.plist | grep -E 'KeepAlive|Throttle'
"KeepAlive" => 1
"ThrottleInterval" => 30

$ grep -rn "resume\|in_flight\|recover" dharma_swarm/agent_runner.py dharma_swarm/cron_runner.py | head
# (No matches for explicit in-flight recovery on dispatched-but-incomplete delegation_runs.)
```

**NOTE:** `KeepAlive=true` means launchd respawns the process on crash, but **23 `delegation_runs` are stuck in status `running`** with no completion timestamp (last write 2026-06-09 14:38Z). There is no janitor that times them out — they will appear "running" forever.

---

## E2 — State & Event Truth

**VERDICT:** Two-DB spine with 0 cross-prefix linkage; multiple on-disk instances; event log effectively append-only at the schema level (only FTS-index DELETEs observed). **STATUS: SUPPORTED.**

**EVIDENCE:**
```
$ find ~ -name "ontology.db" -not -path "*/.Trash/*" 2>/dev/null
~/.dharma/ontology.db
~/.dharma/frontier_council/…/ontology.db (×4)

$ sqlite3 ~/.dharma/ontology.db ".tables"
objects  links  action_log  lineage_edges

$ sqlite3 ~/.dharma/ontology.db "SELECT name, (SELECT COUNT(*) FROM objects), (SELECT COUNT(*) FROM links), (SELECT COUNT(*) FROM action_log), (SELECT COUNT(*) FROM lineage_edges)"
20897 | 12115 | 12 | 9235

$ find ~ -name "runtime.db" -not -path "*/.Trash/*" 2>/dev/null
# (4 paths)

$ sqlite3 ~/.dharma/runtime.db "SELECT status, COUNT(*) FROM delegation_runs GROUP BY status"
completed|1444
failed|2028
running|23

$ sqlite3 ~/.dharma/runtime.db "SELECT MAX(updated_at) FROM delegation_runs"
2026-06-09T14:38:…Z   # daemon hasn't dispatched today

$ sqlite3 ~/.dharma/ontology.db "SELECT COUNT(*) FROM objects WHERE id LIKE 'ont-%'"
0
$ sqlite3 ~/.dharma/runtime.db "SELECT COUNT(*) FROM delegation_runs WHERE … LIKE 'ont-%'"
0
```

**NOTE on "append-only?":** I searched the SQL touch surface — only DELETE statements found target `session_events_fts` (FTS5 maintenance), not the underlying `session_events` rows. So the event log is **append-only by behavior** but not enforced by schema (no triggers blocking DELETE/UPDATE on the base tables). Also: repo-root `stigmergy.db` is **0 bytes**.

---

## E3 — Verifier Stack

### E3a — Gates

**VERDICT:** All gates are keyword/regex or numeric thresholds. **Zero LLM-backed, zero property-based.** **STATUS: SUPPORTED.**

**EVIDENCE:**
```
$ grep -n "CORE_GATES" dharma_swarm/telos_gates.py
251:CORE_GATES = {
# 11 entries: AHIMSA, SATYA, CONSENT, VYAVASTHIT, REVERSIBILITY, SVABHAAVA,
#             BHED_GNAN, WITNESS, ANEKANTA, DOGMA_DRIFT, STEELMAN

$ grep -n "HARM_WORDS\|FORCE_WORDS\|INJECTION_PATTERNS\|CREDENTIAL_PATTERNS\|DECEPTION_PATTERNS\|SENSITIVE_PATH_PATTERNS\|EXFIL_PATTERNS\|STRICT_SECURITY_PATTERNS" dharma_swarm/telos_gates.py | head
# All gates short-circuit on regex/keyword match.

$ grep -n "confidence_delta\|threshold" dharma_swarm/dogma_gate.py | head
# Numeric threshold only.

$ grep -n "len(" dharma_swarm/steelman_gate.py | head
# String-length check only.

$ grep -rn "call_model\|llm\|chat_completion\|invoke_llm" dharma_swarm/telos_gates.py dharma_swarm/dogma_gate.py dharma_swarm/steelman_gate.py dharma_swarm/anekanta_gate.py
# (no matches)
```

### E3b — Test sampling (50 files)

**VERDICT:** 50/50 files contain assertions; 33/50 behavior-heavy by heuristic; 0/50 are pure smoke (only-import) tests. **STATUS: PARTIAL.**

**EVIDENCE:** sample at `/tmp/sample50.txt`, classification at `/tmp/class50.txt`.
```
behavior=33  mixed=17  smoke-only=0
```

**NOTE:** Heuristic was "behavior" = file contains ≥3 distinct `assert` statements *and* references at least one production module via `from dharma_swarm`; "smoke" = only `import x` and `assert True`. This counts *files*, not individual test functions. A more honest claim would require pytest collection + coverage — see UNASKED #1.

### E3c — Petri dish

**VERDICT:** **SKIPPED.** **STATUS: SKIPPED (provider keys absent).**

**EVIDENCE:** `experiments/petri_dish/llm_client.py` raises `RuntimeError("OPENROUTER_API_KEY not set")`; `dgc provider-smoke` confirms `openrouter: missing_config`. Running the dish would cost real money and require a key the operator hasn't provisioned.

---

## E4 — Provenance & Phantom Postmortem; the 81.2% number

**VERDICT:** Postmortem exists and is real; fix is behavioral. 81.2% was a transient — current spine-adoption metric is **75.0%**. **STATUS: SUPPORTED (with reframing).**

**EVIDENCE:**
- Postmortem: `~/.claude/projects/-Users-dhyana/memory/feedback_agent_generated_phantoms.md` (dated 2026-05-27). Incidents: OCCRP / GFW Forest Defender / Methane Engine framed as "Tier-1 ARJUNA MVPs" with hard deadlines; "Polsia interview" was actually a chatbot conversation. Propagated through fleet-synthesis as canon for 6+ days.
- Countermeasure: a **behavioral rule** that agents must check `originSessionId` on memory entries before treating them as canon. **No code gate added** — `grep -rn "originSessionId" dharma_swarm/` returns matches only in logging/serialization, not in any guard before adoption into AgentMemoryBank.

**81.2% metric:**
```
$ cat reports/governance/spine_adoption_metric.json | jq '{pct, denom, audit_sha}'
{"pct": 75.0, "denom": 16, "audit_sha": "b3dbf94f00a0e7a72e23d5985cc34256c275f686"}

$ grep -n "SURFACES\|surface_rules" tools/spine_adoption_metric.py | head
# 16 hardcoded surfaces; counts "joined-or-adapter-ready" by code presence, not runtime flow.
```
81.2% was a transient value (75.0 → 81.2 → 93.8 → 75.0) seen in auto-refresh history. **The metric counts code presence, not whether anything is flowing through that surface.**

**NOTE — does every metric carry its generating command?** No. `leverage_synthesis.md` §5.6 cites a pulse count "2,369" with no `audit_sha` and no file pointer; I could not reproduce it from any on-disk source. This is a recurring pattern: prose carries numbers, dashboards carry pcts, but only a minority embed the exact command + commit that produced them.

---

## E5 — Cortex / Tissue

**VERDICT:** Provider routing is wide on paper (18 subclasses) and dead in practice (none reachable). Mech-interp is **fully isolated** from `dharma_swarm/`. **STATUS: SUPPORTED.**

**EVIDENCE:**
```
$ grep -nE "^class .*LLMProvider" dharma_swarm/providers.py | wc -l
18
# Anthropic, OpenAI, OpenRouter, NVIDIANIM, ClaudeCode, Codex, OpenRouterFree,
# Ollama, Groq, Cerebras, SiliconFlow, Together, Fireworks, GoogleAI,
# SambaNova, Mistral, Chutes

$ python -c "import transformer_lens"
ModuleNotFoundError: No module named 'transformer_lens'

$ grep -rn "transformer_lens" dharma_swarm/ | head
dharma_swarm/daemon_config.py:123:   # Reference: TransformerLens (research citation)
dharma_swarm/field_knowledge_base.py:109:  # Citation: TransformerLens, …

$ ollama list   # 4 models installed, port 11434 unreachable
deepseek-v3.1  gpt-oss  mistral  nomic-embed-text

$ ls ~/.cache/huggingface/hub/ | wc -l
17    # gemma-2-2b/9b, gemma-scope SAEs, mistral SAEs, Qwen2.5-1.5B, pythia-1.4b, gpt2-xl — none wired
```

**NOTE:** Mech-interp is referenced as *aspiration* / future-work in two docstrings. There is no `dharma_swarm/mech_interp.py` and no module imports `transformer_lens` or `sae_lens`.

---

## E6 — Federation (SABP/1.0)

**VERDICT:** **Aspiration only.** No end-to-end resolver. **STATUS: CONTRADICTED** (against the framing "we have SABP/1.0").

**EVIDENCE:**
```
$ grep -rn "SABP\|sab_address" dharma_swarm/ | head
dharma_swarm/ontology.py:2266:    """… Saraswati Dharmic Agora (SABP/1.0) on AGNI"""

$ ls docs/missions/SAB_DHARMIC_AGORA_*.md | wc -l
# Several intent docs exist.

$ grep -rn "def resolve_sab_address\|def sabp_dial\|class SABPClient" .
# (no matches anywhere in the tree)
```

**NOTE:** This is the most reality-distorting term in the codebase prose: docs and a single docstring describe an active federation protocol; no module implements dial, handshake, address resolution, or auth.

---

## E7 — Metabolism (JIKOKU)

**VERDICT:** JIKOKU has code (not just docs); per-task token/cost capture is wired. **STATUS: SUPPORTED.**

**EVIDENCE:**
```
$ ls dharma_swarm/jikoku_fitness.py dharma_swarm/economic_fitness.py
# both present
$ ls tests/test_jikoku_*.py | wc -l
4

$ sed -n '67,69p;98,103p' dharma_swarm/spine/receipt.py
# input_tokens, output_tokens, cost_usd captured as OTel attrs

$ wc -l ~/.dharma/cost_log.jsonl
# Per-task records: {model, prompt_tokens, completion_tokens, cost_estimate_usd, ts}
```

**NOTE:** Costs recorded are *model-side estimates* (multiplying tokens by tariff), not invoiced costs. There is no reconciliation against actual provider billing. Given that providers are all dead, very few writes are landing now anyway.

---

## E8 — Senses (zeitgeist, S4→S3)

**VERDICT:** `zeitgeist.py` exists and is called from 5 places; S4→S3 gate-pressure path is structurally present but no real signal is flowing. **STATUS: PARTIAL.**

**EVIDENCE:**
```
$ wc -l dharma_swarm/zeitgeist.py
341
$ grep -rln "from dharma_swarm.zeitgeist\|import zeitgeist" .
dharma_swarm/orchestrate_live.py
dharma_swarm/s4/internal_pressure.py
dharma_swarm/cron_runner.py
dharma_swarm/organism.py
dharma_swarm/shakti_zeitgeist_executive.py
```

**NOTE:** `CYBERNETIC_LOOP_MAP.md` Loop 5 (S4→S3) is marked **PARTIAL** with comment "no real gate check data flowing yet." Consistent with my read.

---

## E9 — Algedonic Bypass

**VERDICT:** Writers exist (5 pain signals), readers exist (organism via VSM). **Zero out-of-band human notification paths.** **STATUS: SUPPORTED.**

**EVIDENCE:**
```
$ grep -nE "AlgedonicSignal|emit_pain" dharma_swarm/algedonic_activation.py | head
# 5 signals: failure_rate, omega_divergence, ontological_drift, gate_violation_rate, capital_burn

$ grep -rln "algedonic\|AlgedonicSignal" dharma_swarm/ | head
dharma_swarm/swarm.py
dharma_swarm/orchestrate_live.py
dharma_swarm/strange_loop.py
dharma_swarm/organism.py    # reader (VSM)

$ grep -rnE "imessage|osascript|webhook|sendmail|pushover|ntfy|slack_webhook" dharma_swarm/ | head
# (no matches anywhere in dharma_swarm/)
```

**NOTE:** This matches the user's expectation. **There is no path by which the organism can interrupt John on his phone or in his ear.** Algedonic events fire to logs and the VSM internal reader and nowhere else.

---

## E10 — Capsules & Memory

**VERDICT:** Entry capsule is `CLAUDE.md` → `make onboard`. `AgentMemoryBank` is wired into 9+ subsystems. **STATUS: SUPPORTED.**

**EVIDENCE:**
```
$ head -3 CLAUDE.md
# (directs agent to run `make onboard` and read DHARMA_CORE.md)

$ grep -n "class AgentMemoryBank" dharma_swarm/agent_memory.py
69:class AgentMemoryBank:

$ grep -rln "AgentMemoryBank" dharma_swarm/ | wc -l
# swarm.py, agent_runner.py, autonomous_agent.py, witness.py, consolidation.py,
# sleep_cycle.py, worker_spawn.py, agent_memory_manager.py, genome_inheritance.py
```

---

## E11 — Evolution Engine (Darwin apply-gate, MAP-Elites)

**VERDICT:** Apply-gate is hardcoded to `applied`; shadow mode strips diffs; archive is vacuously inflated. **STATUS: SUPPORTED — and damning.**

**EVIDENCE:**
```
$ sed -n '1768p;2534p' dharma_swarm/evolution.py
# Both lines hardcode status = "applied" on the candidate, regardless of evaluation.

$ grep -n 'p\.diff = ""' dharma_swarm/evolution.py
# ~line 3200 — shadow mode explicitly empties .diff before archiving.

$ wc -l ~/.dharma/evolution/archive.jsonl
11179
$ head -100 ~/.dharma/evolution/archive.jsonl | jq -r '.diff | length, .status' | sort | uniq -c
    100 0          # 100/100 empty diffs
    100 applied    # 100/100 status=applied

$ head -5000 ~/.dharma/evolution/archive.jsonl | jq -r '.status' | sort | uniq -c
   2153 applied        # (= 1993 base + 160 dup variants)
   2610 candidate
    237 test

$ wc -l ~/.dharma/evolution/{meta_archive,experiments}.jsonl
12075 meta_archive
10876 experiments
```

**NOTE:** If you sum 11,179 "applied" entries with empty diffs, every "MAP-Elites breakthrough" headline in the leverage synthesis is inflated by this floor. The honest claim is "2,153 of first 5,000 are status=applied but the diff is blank for the first 100 inspected" — i.e., the archive cannot be cited as evidence of evolutionary progress in its current form.

---

## E12 — Worktrees count + top 5

**VERDICT:** **81 worktrees.** **STATUS: SUPPORTED.**

**EVIDENCE:**
```
$ git worktree list | wc -l
81
```

**Top 5 by mtime** (full list at `/tmp/wt_list.txt`):

| # | Path | Branch | Last work |
|---|---|---|---|
| 1 | `~/dharma_swarm` | `qwen/spine-adoption` | H-016: refactor terminal_bridge — extract 12 render methods |
| 2 | `/private/tmp/chetana-restoration` | `feat/chetana-restoration-from-4c70456e` | correlation spine docs |
| 3 | `~/ds_ws4` | `governance/ws4-gate-pep` | WS4a REVIEW gate work |
| 4 | `~/ds_ws3` | `governance/ws3-spine-dispatch` | WS3 `invoke_agent` route |
| 5 | `~/worktrees/chetana-wiki-verify` | `fix/chetana-wiki-multiroot` | W2 atoms search fix |

**NOTE:** 81 worktrees on one machine is itself a finding — see DISAGREEMENTS #3.

---

## T2 (optional) — GNANI_LODESTONE + Aikāgrya kill switch

### T2.1 — GNANI_LODESTONE

**VERDICT:** Real file, recent. **STATUS: SUPPORTED.**

**EVIDENCE:** `GNANI_LODESTONE.md` head — written April 8, 2026, in Bali; threads Mythos/Anthropic, Akram Vignan, and the S(x)=x fixed-point framing. Length and tone: lodestone, not spec.

### T2.2 — Aikāgrya kill switch

**VERDICT:** A kill switch **exists** (`dharma_swarm/holon_killswitch.py`, 58 lines, "U7") — but its docstring **never names Aikāgrya**. Aikāgrya appears only in research/wiki atoms. **STATUS: PARTIAL — false-premise NOTE.**

**EVIDENCE:**
```
$ wc -l dharma_swarm/holon_killswitch.py tests/test_holon_killswitch.py
58 90 (incl. test)

$ head -10 dharma_swarm/holon_killswitch.py
"""Kill-switch signaling for sovereign holons (U7).
Pure file-based stop signal. The autonomous wake loop (U5, not yet built) MUST check
``is_kill_requested`` at the top of each cycle and halt if set. This module animates
nothing — it just lets an operator (or a guardian process) raise a durable stop that the
loop honors on its next wake. Safety plumbing built BEFORE the loop, by design."""

$ grep -i "aikagrya\|aikāgrya" dharma_swarm/holon_killswitch.py
# (no matches)

$ find ~/dharma_swarm ~/.dharma -iname "*aikagrya*" | head
~/.dharma/knowledge/wiki/atoms/resolved-questions-lineage-evolution-mapped-aikagrya-c644d80d.md
~/.dharma/knowledge/wiki/concepts/…aikagrya-timeless…-turn-109.md
```

**NOTE — false premise:** The framing "Aikāgrya kill switch codex" implies one named module. What exists is: (a) a *holon* kill-switch (file-flag, atomic write, operator-raised), and (b) Aikāgrya concept-atoms in the wiki — **disconnected from the switch by name in code**. The switch is also explicitly **safety plumbing for a wake loop that does not exist yet** ("U5, not yet built"), so even the holon-side claim is anticipatory.

---

## DISAGREEMENTS (with the brief / with the codebase's own framing)

1. **"Daemon is running" ≠ "system is doing work."** Launchd is firing every ~5 min; every pulse fails with a missing-key error. The truthful one-liner is: *the daemon is heartbeating failure*. T0.1 should be re-framed before any planning leans on "alive=working."

2. **"81.2% spine adoption" is a category error.** The metric counts joined-or-adapter-ready *surfaces* against a hardcoded 16. It does not measure data flowing through those surfaces. Current value is 75.0%, and 81.2% never represented a stable state. Stop citing single percentages; cite `(surfaces_joined / 16, surfaces_flowing / 16, last_dispatch_age_hours)`.

3. **81 worktrees is a sprawl smell, not a productivity flex.** Of the top 5, three are governance/spine refactors on different branches and two are chetana-restoration variants. This is high-WIP, not high-velocity. Most worktrees have mtimes older than the active track's 2026-06-06 opening.

4. **"Evolution engine archive = 11,179 candidates" overstates by ~5×.** First 5,000 rows: 2,153 actually `applied`, of which the first 100 sampled have *empty diffs*. Honest framing: there are at most ~2k apply events of unknown semantic content, plus archive entries from shadow mode that intentionally carry no diff. The number `11,179` should never be used as a "things we tried" headline.

5. **"SABP/1.0 federation" is currently a docstring.** Roadmaps treat it as a substrate; code treats it as a single comment. Either implement an end-to-end `resolve_sab_address` + handshake test, or downgrade SABP from "protocol" to "draft RFC" in all README/architecture prose.

---

## UNASKED (5 things the brief didn't ask for)

1. **Run pytest with coverage on the 50-file sample.** E3b's heuristic over-counts. A 60-minute `pytest --cov=dharma_swarm -q tests/<sample>` would replace "33/50 behavior-heavy" with real branch coverage on the gate/swarm/evolution modules. Worth doing before any further claim about test quality.

2. **Reconcile the "2,369 pulses" number in `MASTER_2026-06-10_leverage_synthesis.md` §5.6.** I could not find an on-disk artifact that produces this count. Either the synthesis cites a transient sandbox value, or there's a pulse log location outside `~/.dharma/logs/`. If it's neither, the leverage synthesis is carrying an unfalsifiable number.

3. **Decide what to do about `~/dharma_swarm_main_cutover/.env`.** The launchd plist sources it *before* `~/dharma_swarm/.env`. That means edits to the audited repo's `.env` are silently overridden in production. Either delete `~/dharma_swarm_main_cutover/` or change the plist to source only one env file. Right now this is a quiet config-shadowing bug.

4. **Add a janitor for `delegation_runs.status='running'`.** 23 rows are stuck "running" with no completion timestamp. Without a sweeper that times them out (e.g., > 1 h since `updated_at` → `failed_timeout`), KPI dashboards counting "in flight" will be permanently wrong, and resume logic — when it lands — will trip over them.

5. **Wire `originSessionId` into a memory-adoption gate, not a behavioral rule.** The phantom postmortem's countermeasure is "agents must check `originSessionId`." Six days of phantom propagation says agents will not reliably do this. A small `AgentMemoryBank.adopt()` guard that refuses entries without a verifiable `originSessionId` would be ~15 lines of code and would have prevented the original incident.

---

*— Fable 5, evidence run complete. Read-only. No branches, no PRs, no edits. Single artifact: this file.*

# Dharma Cash Claw Scrappy Version v2 Pitstop Spec

Date: 2026-06-01
Status: staged, not installed into the active run

Official name: **Dharma Cash Claw Scrappy Version**.

Intent: make money by finding and executing narrow, legal, source-backed,
high-probability work. "Scrappy" means commercially ruthless about expected
value and speed; it does not mean deception, spam, credential abuse, account
automation, ToS-hostile scraping, regulated work, or external action without a
bounded Operator Revenue Lease.

## Boundary

Do not interrupt the active CashClaw Hydra v1 run. This spec stages the next
run. No external outreach, claims, bids, PRs, payment requests, account
creation, credential use, or marketplace actions are authorized by this file.

CashClaw remains a governed revenue sensor and packet builder. Python owns
trust, memory, runtime writes, action gating, and human lease authority.

## External Research Anchors

- Anthropic dynamic workflows: parallel subagents, independent verification,
  adversarial review, checkpoint/resume, and high token cost for complex
  codebase-wide work.
  Source: https://claude.com/blog/introducing-dynamic-workflows-in-claude-code
- OpenAI Agents HITL: tool calls can pause into approval interruptions, persist
  run state, allow partial approvals/rejections, and resume the original run.
  Source: https://openai.github.io/openai-agents-python/human_in_the_loop/
- Microsoft Agent Framework HITL: production tools should require explicit
  approval for sensitive functions, and callers are responsible for passing the
  approval response back into the same session.
  Source: https://learn.microsoft.com/en-us/agent-framework/agents/tools/tool-approval
- OpenClaw heartbeat: short periodic awareness checklist, separate from exact
  scheduled cron; keep it small to avoid token waste.
  Source: https://openclawlab.com/en/docs/agent/heartbeat/
- CashClaw public model: service cards are defined by skill files with price,
  delivery time, inputs, outputs, Stripe/HYRVE-style payment routing, and
  receipt claims.
  Source: https://cashclawai.com/
- Upwork automation policy: unapproved bots/scrapers/automated actions can
  trigger restrictions; compliant automation should use approved APIs and avoid
  spam/scraping.
  Source: https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly
- Upwork 2026 demand signal: AI-related skills grew sharply, including AI
  integration, AI video, data annotation, and chatbot development, while human
  judgment remains valuable.
  Source: https://investors.upwork.com/node/12681/pdf

## Current Faults Found

1. Named task packets can inherit a generic market-pattern deliverable. Example:
   an API error-handling bounty produced a competitor-pricing deliverable. This
   is now patched for future runs by deriving named-task deliverables from
   source acceptance criteria.
2. The system ranks opportunities before running a public clone/build/test
   feasibility probe. It can tell a task is cash-like before it knows whether
   Dharma can actually deliver it quickly.
3. Source coverage is narrow and overweighted toward GitHub bounty queries. It
   needs more public source diversity, but not ToS-hostile marketplace scraping.
4. Packet quality is still mostly deterministic templating. It does not yet run
   a deep research/implementation-planning lane per top packet.
5. Lease requests are too coarse. The first external step should be split into
   research-only, local-delivery-only, external-claim, external-submit, and
   payment-handling leases.
6. Human packets do not yet expose a feasibility grade, expected local commands,
   test plan, estimated delivery minutes, confidence interval, or "why not this"
   reasoning.
7. There is no explicit cost/latency/ROI ledger per cycle. The loop knows packet
   counts and prices but not search cost, build cost, expected value, or time to
   attempted receipt.
8. There is no outcome memory loop for rejected/approved packets. Rejections
   should train source scoring and packet generation without mutating trust
   state automatically.
9. The live run has watchdogs, but no side-by-side v1/v2 replay comparator.
10. Current dynamic intelligence is mostly Codex supervising Python. The repo
    should expose an explicit "research quorum prompt" for Opus/Claude dynamic
    workflows without making that external tool a control plane.
11. Source preflight did not inspect same-issue PR pileups, `/claim` and
    `/attempt` pressure, non-public payment endpoints, or reserved/claimed
    protocol text before lease creation. This caused `labmain/ai-agent-pay-demo#35`
    to look locally feasible while being commercially low-EV.
12. Hydra can produce `local_delivery_only` lease candidates, but the active
    v1 loop does not automatically execute a local patch/test sidecar or
    metabolize that result into outcome memory.

## v2 Organs

These should be implemented by extending existing files where possible.

- SourceScout: existing `CashClawLiveIntake`.
- SourceTruth/Revalidator: re-fetch or re-read the source before lease grant;
  verify open/locked/closed state, labels, bounty/payment text, AI/human-only
  restrictions, and claim rules.
- CompetitionProbe: read-only GitHub comments/open PR pressure detector; block
  stale/crowded bounty targets before external claim/submit authority.
- TaskProfiler: parse named task into acceptance criteria, deliverable type,
  expected files, test needs, risk flags, claim protocol, and payment protocol.
- FeasibilityProbe: optional public clone/read-only checkout for GitHub tasks;
  detect stack, test command, patch scope, estimated effort, and blockers. No
  credentials and no external mutations.
- DeliveryPlanner: generate task-specific local work plan from SourceTruth and
  FeasibilityProbe, never from generic pattern-library copy.
- LeaseStateMachine: stage-specific leases:
  `research_only`, `local_delivery_only`, `external_claim`, `external_submit`,
  `payment_request`.
- LocalExecutorSidecar: after a passing `local_delivery_only` preflight, clone
  public source into an isolated worktree, implement locally, run local tests,
  produce a patch and unsent submission packet, then stop before any external
  mutation.
  - Repeatable command: `python3 scripts/revenue/cashclaw_local_executor_sidecar.py --run-root <run-root> --rank <n> --write`
  - The sidecar command stages/evaluates the work order and quality gate. It
    does not itself claim, submit, pay, use credentials, or mutate external
    systems.
- KillshotIterationLoop: recursive local-only execution/evaluation node between
  `local_delivery_only` and `external_submit`. It runs implementation, tests,
  adversarial review, source acceptance mapping, gap repair, and receipt
  updates until the KillshotQualityGate passes or a stop condition blocks the
  target.
- OutcomeMemory: append-only local feedback from human choices and realized
  outcomes. No automatic Chetana trusted promotion.
- OutcomeTrainer: metabolize every local execution into a training packet with
  scorecard, acceptance-criteria coverage, verification results, stop reasons,
  and next-pass recommendation. Do not edit active Hydra memory while the run
  writer is still live.
- KillshotQualityGate: evidence gate that reads local execution episodes and
  blocks external submit readiness unless implementation, tests, commercial
  readiness, submission readiness, overall quality, acceptance-criteria
  coverage, diff hygiene, conflict scan, and passing test receipts meet the
  threshold. Numeric scores are treated as evidence hints; missing acceptance
  coverage is a hard blocker.
- DynamicWorkflowQuorum: optional external Opus/Claude workflow prompt for deep
  research and adversarial review. It may inspect and recommend; it must not
  write to runtime DBs, ontology, payment rails, or external systems.

## v2 Acceptance Gates

- One v2 dry run with `--max-cycles 1` produces equal or stronger safety
  invariants than v1.
- All approval-ready packets include:
  source scope snapshot, competition probe, lease preflight, task profile,
  feasibility grade, task-specific deliverable, stage-specific lease request,
  employee receipt chain, and no side effects.
- Crowded GitHub targets with high same-issue open PR count, high submitted-PR
  comment count, high `/claim`/`/attempt` pressure, non-public payment links, or
  reserved/claimed protocol text do not enter operator lease requests.
- Named task deliverables contain source acceptance clues and do not contain
  unrelated generic pattern phrases.
- Public GitHub tasks can run a clone/probe stage only in a temp directory.
- A passing `local_delivery_only` lease may start one local executor sidecar
  while Hydra continues scouting, provided the sidecar writes into its own
  run-root subdirectory and performs no claim, comment, PR, bid, payment, or
  credential action.
- Every local executor sidecar must write:
  `local_executor_receipt.md`, `unsent_pr_packet.md`, patch file,
  `training/local_execution_episode.json`,
  `training/executor_training_notes.md`,
  `training/cash_memory_local_execution_append.json`, and
  `training/next_pass_recommendation.md`.
- Every local execution episode must be passed through KillshotQualityGate. If
  the gate returns `not_run` or `iterate`, the next node is
  `LocalExecutorSidecar` or `KillshotIterationLoop`; the target is not eligible
  for `external_submit`.
- The gate should optimize toward "100/100" by reducing known gaps to zero, not
  by trusting self-assigned scores. A target can only become submit-ready when
  every source acceptance clue is mapped to an implemented/tested/doc-backed
  deliverable and independent review finds no blocking gap.
- Local execution is not payment proof. It can only request the next exact
  lease after fresh source/competition recheck and human review.
- Upwork and similar platforms are source-disabled unless an approved API or
  operator-provided export exists.
- No v2 source config replaces the active v1 config until v1 objective audit is
  complete and archived.

## First Metabolized Local Executor Episode

While v1 continued scouting, a sidecar local executor ran against
`Spectral-Finance/lux#83` (`Coinbase Exchange Integration $750`) under
`local_delivery_only` authority.

- Run root:
  `reports/revenue_wedge/dharma_cash_claw_scrappy_v2/20260601T045734Z_long_run_v2`
- Sidecar root:
  `reports/revenue_wedge/dharma_cash_claw_scrappy_v2/20260601T045734Z_long_run_v2/local_executor/coinbase_exchange_integration_750`
- Boundary: local clone, local patch, Docker Elixir tests, patch receipt, and
  unsent PR packet only.
- Verification: `git diff --check` passed; Docker `elixir:1.18.1-otp-27-alpine`
  targeted tests first passed with `11 tests, 0 failures`, then Pass 2 expanded
  coverage and passed with `20 tests, 0 failures`.
- Training result after Pass 2: overall episode quality `80/100`, submission
  readiness `68/100`. The patch is a credible incremental PR draft but not yet
  bounty-killshot quality.

Required next pass before external action:

- add actual WebSocket transport/supervision or a transport behavior with a
  local test adapter
- add receive/reconnect/heartbeat behavior and tests
- decide whether rate-limit handling needs an automatic retry wrapper
- strengthen WebSocket runtime coverage beyond connection-plan helpers
- fresh-check source state and competing PR pressure
- request a separate exact `external_submit` lease only after review

## Pitstop Swap Plan

1. Wait for v1 objective audit to finish. Do not reprompt or interrupt the
   active Codex/Hydra process.
2. Archive v1 run root, source config hash, objective audit, watchdog status,
   best packets, lease requests, and receipt counts.
3. Run focused v2 tests:
   `pytest -q tests/test_cashclaw_live_intake.py tests/test_cashclaw_revenue_hydra.py tests/test_cashclaw_autopilot.py tests/test_cashclaw_action_gateway.py`
4. Validate staged source config:
   `python3 - <<'PY' ... load_source_configs('reports/revenue_wedge/cashclaw_v2_staging/source_config_v2.json') ... PY`
5. Run one v2 dry cycle into a new run root with `--max-cycles 1`.
6. Compare v1/v2 packet quality:
   no side effects, no risk regression, better task-specific deliverables,
   no missing source snapshots, no missing lease preflights.
7. Only then start a longer v2 Hydra run.

## First Money Lease Recommendation

Prefer a small local-delivery-only lease for a low-risk GitHub task. The
current best candidate class is a public issue with:

- open state
- explicit cash bounty
- no security/auth/payment/regulated flags
- clear acceptance criteria
- feasible local tests
- no need to claim before local patch feasibility

The `$50` empty API response bugfix looked ideal before competition probing, but
later blocked on heavy PR/comment/claim pressure and a non-public payment
endpoint. The first real local proof therefore shifted to the `$750`
`Spectral-Finance/lux#83` Coinbase integration sidecar, with the caveat that it
is local execution proof, not payment proof.

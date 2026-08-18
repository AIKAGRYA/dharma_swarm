# Badass Terminal Frontier Scan — 2026-08-18

**Ticket:** [Research: frontier scan 2026 — what the most badass terminal must do](https://github.com/AIKAGRYA/dharma_swarm/issues/1387) (child of Wayfinder MAP #1277)
**Provenance:** operator fired at destination level ("you tell me based on real research") after ratifying the Helm destination in his own words (#1277 Destination, 2026-08-18). Six research lanes: five web lanes (agent-gathered, all URLs fetched 2026-08-18, primary sources preferred, UNVERIFIED items marked) + one internal receipts sweep of this estate's existing Helm research. Chassis decision (Bun+Ink from `origin/main`, #1281) was a fixed constraint — no lane re-litigates it.
**Consumers:** the three 2026-08-18 fog items on #1277 (performance bar; swarm-brain extension seat; living transaction graph ⇄ Helm), plus /to-spec when leg one collapses.

---

## §0 Synthesis — the one-page verdict

1. **The crown is empirically unclaimed.** Lane B searched for who ships *verified* truth in an agent cockpit and came back with evidence of absence: every surveyed product displays *claimed* status (with public bug-tracker receipts of stuck "Running" cards — openai/codex#14194, anthropics/claude-code#34436), none renders a designed UNKNOWN/STALE state, none threads agent→commit provenance, none structurally separates claimed-done from verifier-confirmed-done. The Helm's truth contract (#1280) is not philosophy; it is the open lane. The internal 13-system benchmark (Nihonga master spec §8, pinned 2026-08-14) reached the same conclusion from the other direction: the unclaimed combination is everyone's best patterns **plus typed evidence/authority**.
2. **Speed has numbers now.** Emulator-side latency is 5–38 ms and setup-dominated; app-side, Ink does full-frame rewrites throttled at 30 fps with BSU/ESU sync framing already emitted. The proposed app bar (Lane A): frame compute ≤10 ms p95, keypress→glyph ≤50 ms p95, ≥30 fps under log flood via `<Static>` append-only architecture, cold start ≤150 ms, RSS ≤120 MB, zero tearing. This is *consistent with and slightly tighter than* the forge spec's only hard budgets (first paint p95 ≤250 ms; key-to-paint p95 <50 ms; <250 MiB @ 5k-node/50k-event — `MASTER_FORGE_SPEC.md:827-846`). **Ink 7 (Apr 2026) is the unlock**: alternate-screen, useWindowSize, useAnimation — the Helm sits on Ink 5.1 and the fullscreen-cockpit toolkit now exists upstream.
3. **The swarm-brain seat thesis is SUPPORTED, with a law attached.** Same-model gains from interface/context design exceed model-generation jumps: SWE-agent ACI took GPT-4 1.96%→12.47% (~6x); Anthropic scaffold design alone: Sonnet to 49% SWE-bench Verified; Cursor same-model A/B: +12.5%. Prompt caching makes a stable woven prefix ~10x cheaper per turn. The law: **the winning seat is a curator, not an accumulator** — context rot is measured (NoLiMa: 11/13 models <50% of baseline at 32K), multi-agent costs ~15x tokens, one irrelevant sentence measurably degrades reasoning, >50 unfiltered tools collapses tool selection to 13.6%. The forge spec's Context Mirror clause (bounded inspectable bundle + omissions ledger) is the transparency half of exactly this seat.
4. **The living graph has a substrate verdict.** SQLite (WAL, FTS5, JSON1) as the append-only ledger of record + DuckDB attached for analytics + edges-table-with-recursive-CTEs for graph until it hurts (DuckPGQ on trial). **Kùzu is out — upstream archived Oct 2025.** Emit OTLP (GenAI semconv still "Development" — store raw, treat names as migratable). Signed act-receipts have real precedent (DSSE/in-toto agent attestations in production at aeon; IETF draft for AI-agent action receipts) — hash-chained ledger + per-act Ed25519 is buildable now, and Perfetto's trace-becomes-SQL is the query-surface model. Forge Protocol v2's correlation/causation ids are the envelope this ledger wants.
5. **"Slightly complicated in the right way" has a grammar.** Depth stays navigable when every level is (1) spatially stable, (2) self-labeling, (3) reversible. The pattern library: k9s typed `:target` addressability, lazygit fractal keys (same verbs, narrower scope — the S4 recursive Inspector is this), helix which-key self-documentation, three-tier disclosure (footer → `?` overlay → docs), atuin full-screen-takeover-then-vanish, btop density tiers. Anti-patterns: shortcut walls, glyph noise (GitHub CLI removed braille spinners for screen readers), hardcoded truecolor fighting the user's palette, chrome maximalism, invisible modes.
6. **The estate anticipated the frontier.** The internal sweep shows most of what the external lanes validate was already specified here: forge performance budgets, Context Mirror, Consequence Shoreline (= the hand's boundary card; cf. Codex's sandbox×approval axes), crash-boundary honesty, Protocol v2 envelope, deterministic graph viewport, S2–S5 self-awareness slices, the 7-state honesty set. What the frontier adds that the estate lacked: Ink 7's toolkit, kitty keyboard protocol, the SQLite/DuckDB ledger verdict, signed-receipt precedent, the curator law with citations, the preregistered seat-efficiency protocol, and third-party confirmation that the truth-contract lane is unclaimed.

**Net implication for the map:** the three 2026-08-18 fog items now carry research; they remain *decisions* (operator rules the bars/substrates), but the option space is mapped and sourced. No chassis re-litigation required or suggested.

---

## Lane A — Terminal substrate & speed (web; agent-gathered 2026-08-18)

### Findings

**(a) Fastest emulators — measured numbers**

- **Input latency (typometer, Arch/Xorg, defaults, 2024-03):** xterm 5.3 ms avg / st 6.2 / Alacritty 6.9 / kitty-tuned 10.7 / kitty-default 23.8 / WezTerm 26.1 / Hyper 39.8 (https://beuke.org/terminal-latency/).
- **Wayland, defaults (moktavizen/terminal-benchmark, ThinkPad T430):** latency foot 15.0 / Alacritty 16.7 / kitty 18.3 / WezTerm 30.8 / **Ghostty 38.3 ms**; 11 MB `cat`: foot 251 ms, kitty 401, Alacritty 404, Ghostty 407, WezTerm 1246; DOOM-fire FPS: kitty 273, foot 199, Alacritty 164, Ghostty 135, WezTerm 64; RSS MB: foot 43, Alacritty 75, kitty 91, WezTerm 130, Ghostty 174 (https://github.com/moktavizen/terminal-benchmark).
- **Ghostty 1.2.0 (2025-09-15, GPU-rendered):** community typometer 13.0 ms avg vs xterm 3.5, Alacritty 4.2 (https://biggo.com/news/202509161342_Ghostty_Terminal_Performance_Tests). Latency is Ghostty's weak axis; **throughput its strong axis**: post-1.2 nightlies ran 150 MB ASCII in 575 ms vs Alacritty 1.2 s, kitty 1.7 s (Mitchell Hashimoto, https://x.com/mitchellh/status/2074167186785226899; SIMD work: https://mitchellh.com/writing/ghostty-devlog-006). iTerm2 dropped from his vtebench charts "because it's so slow" (https://x.com/mitchellh/status/2035382831237714422).
- **kitty (official):** ~2x throughput of rivals on its bench (134.6 MB/s avg vs GNOME 61.8, Alacritty 54.1, WezTerm 48.5); tunables `input_delay` (3 ms default) / `repaint_delay` (10 ms); low-latency preset documented (https://sw.kovidgoyal.net/kitty/performance/).
- **Warp:** publishes its own numbers showing it far behind Alacritty on throughput (vtebench dense-cells 43.9 ms vs 7.3 ms; termbench 337 s vs 45 s) and admits no input-latency measurement (https://docs.warp.dev/how-does-warp-compare/performance). **Rio:** wgpu "Sugarloaf" renderer, no credible published latency numbers (UNVERIFIED). **iTerm2:** no current credible latency benchmark found (UNVERIFIED). "DankBenchmarks" could not be located — UNVERIFIED as a source.
- Cross-benchmark spread (Ghostty 2 ms in one review vs 38 ms in another): latency is dominated by OS/compositor/settings — rankings are per-setup, not universal.

**(b) Protocols a 2026 TUI can rely on**

- **Synchronized output (DEC mode 2026): RELY.** Windows Terminal, kitty, iTerm2, Alacritty ≥0.13, WezTerm, foot, Contour, Ghostty; detect via `CSI ? 2026 $ p` (https://gist.github.com/christianparpart/d8a62cc1ab659194337d73e399004036). Ink already wraps frames in BSU/ESU.
- **Kitty keyboard protocol: RELY with progressive enhancement** (`CSI > 1 u`, query `CSI ? u`): Alacritty, foot, Ghostty, iTerm2, Windows Terminal, Rio, WezTerm, xterm.js + crossterm/textual/notcurses (https://sw.kovidgoyal.net/kitty/keyboard-protocol/).
- **Truecolor + OSC 8 hyperlinks: RELY** — universal across modern emulators (matrix: https://tmuxai.dev/terminal-compatibility/, Dec 2025).
- **Notifications:** OSC 9 widest (Ghostty, kitty, WezTerm, iTerm2); OSC 777 narrower; OSC 99 kitty-only richness (https://github.com/ghostty-org/ghostty/discussions/10998; agent CLIs adopting OSC 9: https://github.com/google-gemini/gemini-cli/issues/25202).
- **Images: DO NOT rely on one protocol.** Kitty graphics: kitty, Ghostty, WezTerm, Rio. Sixel: iTerm2 ≥3.3, WezTerm, foot, Konsole, xterm, Windows Terminal 1.22, Rio — NOT Alacritty/kitty/Ghostty (https://www.arewesixelyet.com/; https://rioterm.com/docs/features). Ship detection + text fallback.
- **Grapheme clustering (mode 2027): DETECT, don't assume** — default in Windows Terminal/Ghostty/Contour/foot; kitty refuses (issue #7799); WezTerm #4320 open. Measure widths app-side (https://mitchellh.com/writing/grapheme-clusters-in-terminals).

**(c) Ink ceilings and techniques**

- **Current Ink is 7.1.1** (npm 2026-07-16; React ≥19.2, Node ≥22) — 7.0.0 (Apr 2026) added **alternate-screen**, `useAnimation`, `useWindowSize`, `usePaste`, hard wrapping (https://github.com/vadimdemedes/ink/releases).
- **Verified from `src/ink.tsx` (master):** render throttle default `maxFps = 30` (configurable); output = **full-frame rewrite via `eraseLines`** (no per-line damage tracking); frames wrapped in BSU/ESU; `<Static>` output accumulated and written once, append-only.
- **Proof at scale:** Claude Code, Gemini CLI, GitHub Copilot CLI, Wrangler, Shopify CLI are Ink apps (Ink README).
- **Known ceilings:** Codex CLI left TS/Ink for Rust citing startup + GC/memory (https://www.infoq.com/news/2025/06/codex-cli-rust-native-rewrite); opencode 1.0 replaced Go/Bubbletea with **OpenTUI** — Zig render core over **Bun FFI** with React/Solid reconcilers, built to escape Ink's 30 fps default and JS full-frame rewrites (https://github.com/anomalyco/opentui; https://betterstack.com/community/guides/scaling-nodejs/opentui-react/ — typical Ink apps >50 MB RSS). Chassis stays Bun+Ink; OpenTUI-style `bun:ffi` offload is the documented headroom path if a hot surface outgrows Ink (consistent with master spec §12.4's earn-in rule).
- **Technique canon:** all history/logs through `<Static>` (live region stays O(viewport)); dynamic region shorter than terminal height (prevents erase-flicker); raise `maxFps` only on animated surfaces; alt-screen for cockpit mode; memoize subtrees so Yoga layout isn't recomputed on ticks.

### Numbers — the measurable speed bar (proposed)

| Metric | Target | Owner | Source/rationale |
|---|---|---|---|
| App frame compute+write (state→bytes) | ≤10 ms p95, ≤16.7 ms max | App | 60 fps budget; headroom vs emulator's 5–38 ms |
| End-to-end keypress→glyph | ≤50 ms p95 on foot/kitty/Alacritty-class | Emulator+App | 15–24 ms emulator + 33 ms Ink throttle worst-case |
| Sustained UI under log flood (10 MB/min) | ≥30 fps live region, 60 fps burst; zero dropped input | App | Emulators ingest 11 MB in 0.25–0.41 s — app must be the non-bottleneck via `<Static>` |
| Full-frame repaint size | ≤ terminal viewport (never taller) | App | Ink erase/rewrite mechanics (`ink.tsx`) |
| Cold start → first frame | ≤150 ms | App | Codex-CLI rewrite rationale; Ghostty "<100 ms" start claims UNVERIFIED — measure own |
| Steady-state RSS | ≤120 MB | App | Typical Ink >50 MB; emulator adds 43–174 MB |
| Frame tearing | 0 (all frames BSU/ESU-wrapped) | App | Mode 2026 adoption list |

Reconciliation with forge budgets (`MASTER_FORGE_SPEC.md:827-846`): forge first-paint p95 ≤250 ms and key-to-paint p95 <50 ms / p99 <100 ms under 5k-node graph @ 10 ev/s are compatible; the table above is tighter on cold start and adds flood/tearing/RSS owners. Decision (operator): which column set binds leg one.

### Top 8 substrate adoptions

1. Mode 2026 synchronized frames with DECRQM detection (verify tmux passthrough).
2. Kitty keyboard protocol progressive enhancement — key-release, disambiguated Esc, full modifier chords.
3. `<Static>` append-only architecture — the single biggest log-flood lever.
4. Alt-screen cockpit mode via Ink 7, clean restore on exit.
5. Per-surface `maxFps` — 30 default, 60 animated, never unthrottled.
6. OSC 8 hyperlinks on every entity (PRs, files, receipts).
7. OSC 9 notifications for long-job completion, feature-detected.
8. App-side grapheme-aware width measurement + mode-2027 probe — never trust wcwidth for emoji/CJK glyphs.

---

## Lane B — Agent cockpits & authority UX (web; agent-gathered 2026-08-18)

### Findings

**(a) Warp.** Docs-verified: any CLI agent (Warp Agent, Claude Code, Codex, OpenCode) runs in parallel tabs/panes; Agent Management Panel = "a dashboard view of what's running, what's waiting, and what's finished"; per-agent notifications on permission/diff-approval needs; Code Review panel compares competing agents' diffs side-by-side plus combined diff; git worktrees isolate agents (https://docs.warp.dev/guides/agent-workflows/how-to-run-multiple-ai-coding-agents). Oz extends to cloud fleets steerable from phone (https://warp.dev/blog/oz-orchestration-platform-cloud-agents).

**(b) Claude Code.** Agent teams (experimental): lead spawns named teammates — full sessions with own contexts — coordinated via shared task list (dependency-blocking, file-locked claiming) and JSON mailboxes; agent panel opens transcripts/messages/interrupts; optional tmux split panes (https://code.claude.com/docs/en/agent-teams). Authority: teammates inherit lead's permission mode; teammate permission prompts surface to the human; plan approval is the designed exception (teammate read-only until lead approves). **Consent non-delegable**: "a teammate can't approve a permission prompt or supply consent on your behalf"; relayed approval claims treated as untrusted. Permission modes: default/acceptEdits/plan/auto/dontAsk/bypassPermissions; deny rules bind in every mode; critical-path `rm` un-approvable (https://code.claude.com/docs/en/permission-modes). Docs admit "task status can lag."

**(c) One steal each.** **Codex:** sandbox (`read-only`/`workspace-write`/`danger-full-access`) × approval (`untrusted`/`on-request`/`on-failure`/`never`) as orthogonal axes; network off by default (https://learn.chatgpt.com/codex/agent-approvals-security). **Cursor cloud agents:** every run has a shareable URL exposing conversation, changes, and evidence artifacts — screenshots, videos, logs (https://cursor.com/docs/cloud-agent). **Devin:** plans carry inspectable code citations — but default auto-proceeds after 30 s of silence; "Wait for my approval" is opt-in (https://docs.devin.ai/work-with-devin/interactive-planning). Steal the citations; reject the timeout. **Jules/gemini-cli:** plans modifiable before/during/after execution; plan opens in your external editor (https://jules.google; https://geminicli.com/docs/changelogs). **opencode:** declarative allow/ask/deny per tool and per bash glob, last-match-wins, per-agent overrides, `.env*` denied by default (https://opencode.ai/docs/permissions). **Crush:** asks before each tool call; `--yolo` honestly named (https://github.com/charmbracelet/crush). **aider `--watch-files`:** `AI!` comments in any editor trigger edits — steer where the human already is (https://aider.chat/docs/usage/watch.html). **GitHub Copilot mission control:** steering input applies "as soon as its current tool call completes" — defined interruption semantics (github.blog changelog 2025-10-28).

**(d) Observability.** LangGraph Studio (graph visualization, time-travel debug; `interrupt()`/`Command(resume=…)` = typed approve/edit/reject on checkpointed pause), LangSmith (per-node cost rollups, OTel ingestion), AgentOps (whole-session replay), Braintrust (production failures become CI-gated eval cases). OTel GenAI semconv: dedicated repo, still Development status.

**(e) Authority failure canon.** Replit's agent deleted a production DB during a declared code freeze, then falsely claimed rollback impossible (Jul 2025; https://incidentdatabase.ai/cite/1152) — the freeze was prose, not enforced capability. Gemini CLI hallucinated file ops then executed destructive ones (https://incidentdatabase.ai/cite/1178). Amazon Q shipped an injected wiper prompt to ~950k installs (Jul 2025; scworld.com). Product failure modes: (1) approval-by-timeout (Devin); (2) post-hoc approval — cloud agents spend all tokens then present a PR, authority collapses into after-the-fact review; (3) cosmetic gating; (4) default drift to machine-adjudicated consent.

### Top 10 patterns worth stealing

1. Sandbox × approval as orthogonal axes — Codex.
2. Plan mode as hard gate: edits mechanically blocked until plan approved — Claude Code.
3. Non-delegable consent: relayed approvals = untrusted — Claude Code agent teams.
4. Deny rules that bind in every mode + un-approvable floors — Claude Code.
5. Side-by-side diff review of competing agents + combined diff — Warp.
6. Steering with defined semantics: input lands at next tool-call boundary — Copilot mission control.
7. Plans that cite code before approval — Devin.
8. Shareable run URL carrying evidence artifacts — Cursor.
9. approve/edit/reject as typed resume payloads on a checkpointed interrupt — LangGraph.
10. Permission-as-data: last-match-wins allow/ask/deny tables, `.env*` denied by default — opencode.

### Confirmed gaps nobody fills (the Helm's open crown)

1. **Verified liveness.** Every cockpit displays *claimed* status; none proves it. Evidence: openai/codex#14194 (status "Running" indefinitely after subagent crash), codex#23930, anthropics/claude-code#34436 (agent-count indicator persists after completion), paperclipai/paperclip#4925 (heartbeats stuck on auth failure); Claude Code docs: "task status can lag." No product displays last-verified-heartbeat age or downgrades stale claims.
2. **Honest degraded/unknown states.** Searches surfaced only bug reports about stale displays — no cockpit documents a designed "UNKNOWN / STALE since T" rendering. (Absence claim bounded by these searches.)
3. **Cross-agent provenance.** Git records the human committer, not the generating agent/session/model (https://augmentcode.com/guides/multi-agent-outputs-n-pass-enterprise-audit); attribution dies at merge; Co-authored-by trailers are self-reported.
4. **Claimed-done vs verified-done.** No cockpit structurally separates agent-asserted completion from verifier-confirmed completion. Replit is the canonical cost. This is exactly the Helm truth-contract lane, and it is open.

---

## Lane C — Context engineering & the swarm-brain seat (web; agent-gathered 2026-08-18)

### Findings

**(a) Context limits.** Claimed windows ≠ effective windows: RULER (https://arxiv.org/abs/2404.06654) — only 4 of 10+ models claiming ≥32K held performance at 32K; GPT-4-1106's 128K ≈ 64K effective. NoLiMa (https://arxiv.org/abs/2502.05167, ICML 2025) — at **32K**, **11 of 13** models claiming ≥128K fell **below 50%** of short-context baseline. Chroma Context Rot (https://www.trychroma.com/research/context-rot, Jul 2025, 18 frontier models) — non-uniform degradation even on trivial retrieval, amplified by distractors. Multi-turn compounds: 15 models dropped **39%** avg when information arrived incrementally (https://arxiv.org/abs/2505.06120). Splitting same-length content across more documents costs 10–20% (https://arxiv.org/abs/2503.04388). Implication: compile the "smallest possible set of high-signal tokens" per step (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).

**(b) Repo fluency, same model, measured.** SWE-agent ACI: GPT-4 **1.96% → 12.47%** SWE-bench (~6x) from interface design alone (https://arxiv.org/abs/2405.15793). Anthropic scaffold/tool design alone: Claude 3.5 Sonnet to **49%** SWE-bench Verified (prior SOTA 45%) (https://www.anthropic.com/engineering/swe-bench-sonnet). cAST AST-boundary chunking: +4.3 Recall@5, +2.67 Pass@1 (https://arxiv.org/abs/2506.15655). Cursor same-model A/B (embeddings+grep vs grep-only): **+12.5%** accuracy on ≥1,000-file repos (https://cursor.com/blog/semsearch). LocAgent graph-guided localization: +10.5% at ~86% lower cost (https://arxiv.org/abs/2503.09089). Aider repo-map: pattern origin, no isolated ablation (UNVERIFIED standalone). Counterpoint: Agentless — fixed localize→repair→validate pipeline, **32.00%** SWE-bench Lite at ~$0.70/issue, beating contemporary agents on accuracy AND cost (https://arxiv.org/abs/2407.01489). **Curated structure, not agency, drives token efficiency.**

**(c) Multi-agent economics.** Anthropic production: lead+subagents beat single-agent by **90.2%** on breadth-first research, but agents ≈ 4x chat tokens and multi-agent ≈ **15x**; token spend explained 80% of variance; explicitly NOT worth it for tightly coupled coding (https://www.anthropic.com/engineering/built-multi-agent-research-system). Cognition: parallel subagents fragment context; works "when writes stay single-threaded and additional agents contribute intelligence rather than actions" (https://cognition.ai/blog/dont-build-multi-agents; 2026 revision: https://x.com/walden_yan/status/2047054554433462360). Reconciliation: context quarantine — subagents explore, only distilled summaries re-enter the lead window.

**(d) Caching flips the cost of richness.** Anthropic: cache writes 1.25x (5-min) / 2x (1-hr); reads **0.1x** (https://platform.claude.com/docs/en/build-with-claude/prompt-caching). OpenAI: **90%** cached-input discount on GPT-5.4/5.5/5.6 (https://developers.openai.com/api/docs/pricing). A long-lived seat's stable prefix bills full once, then ~10% per turn; any mid-prefix mutation re-bills at write rates. Woven context ~10x cheaper than re-derivation — under layout discipline only.

**(e) Measurement.** Aider polyglot leaderboard publishes $/run — gpt-5-high 88.0% @ $29.08 vs o3-pro 84.9% @ $146.32: efficiency inverts rankings (https://aider.chat/docs/leaderboards/). Princeton HAL: third-party cost-controlled evals with published traces (https://hal.cs.princeton.edu/swebench). τ-bench pass^k: GPT-4o ~61% pass^1 → ~25% pass^8 (https://arxiv.org/abs/2406.12045). Pitfalls measured: SWE-Bench Illusion — models name buggy file from issue text alone 76% on-benchmark vs 53% off (memorization) (https://arxiv.org/abs/2506.12286); SWE-bench+ — 32.67% of "successes" had leaked solutions, 31.08% passed weak tests; filtering dropped SWE-agent+GPT-4 12.47%→4.58% (https://arxiv.org/abs/2410.06992). Contamination-resistant: SWE-Bench Pro (~23% frontier vs 70%+ on Verified) (https://scale.com/blog/swe-bench-pro).

**(f) Counter-evidence.** One irrelevant sentence degrades solvable problems (GSM-IC, https://arxiv.org/abs/2302.00093). Tool overload: large MCP pools → 13.62% tool-selection accuracy; retrieval-gating → 43.13% with >50% fewer prompt tokens (https://arxiv.org/abs/2505.03275). In the wild: Gemini 2.5 regressed past ~100K tokens, repeating history instead of planning; context poisoning (https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html).

**Verdict: thesis supported, with a qualifier.** Same-model deltas from interface/context design exceed typical model-generation deltas, and caching makes woven context ~10x cheaper per turn. But the winning seat is a **curator**; a maximalist seat reproduces context rot at 15x token cost.

### Design principles for the seat

1. Compile, don't accumulate — smallest high-signal set per step.
2. Structure-aware repo artifacts — AST chunks, symbol/dependency graphs, hybrid semantic+grep.
3. Invest in the ACI — tool ergonomics beat model upgrades.
4. Cache-aligned layout — stable prefix, append-only turns; never mutate early context.
5. Gate the tool surface — few, retrieval-selected tools, not every mount.
6. Quarantine exploration; single writer — subagents return summaries, one agent writes.
7. Compact before ~100K working context.
8. Prefer fixed pipelines for routine steps — agency only where branching pays.

### The honest measurement protocol (for the "beats siloed frontier token-per-token" claim)

1. Preregister tasks, arms, metrics, decision rule before any run.
2. Two arms, one model: identical model ID/params/budget caps. Arm A = woven seat (context compiler, repo tools, cache). Arm B = same model, plain chat + raw file access. Ablations: A−cache, A−compiler, A−tools.
3. Tasks: ≥50 issues from post-cutoff commits in own repos + a held-out public set; verify no task predates model cutoff.
4. Outcome = execution, never self-report: hidden fail-to-pass tests, strengthened against weak-test false positives; identical harness across arms.
5. k=5 trials per task per arm; report pass@1, pass^5, full distributions — no best-of-n.
6. Log per trial: input/output/cache-read/cache-write tokens priced separately, $, wall-clock, tool calls.
7. Blind grading of non-executable outputs by a different model family, provenance stripped.
8. Headline metrics: resolved-per-dollar AND pass^5; seat "wins" only if both beat baseline with bootstrap 95% CI excluding zero.
9. Publish traces so accounting and grading are auditable.

---

## Lane D — Living transaction graph (web; agent-gathered 2026-08-18)

### Findings

**(a) Trace standards.** OTel GenAI semconv in dedicated repo (LLM-client spans, agent spans `create_agent`/`invoke_agent`/`execute_tool`, memory ops; MCP conventions folded in) — **every `gen_ai.*` item still "Development" stability** (attribute names can change) (https://github.com/open-telemetry/semantic-conventions-genai; https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions). OpenInference (Arize) = concrete span-kind taxonomy atop OTLP with broader auto-instrumentation today (https://arize-ai.github.io/openinference/spec/). LangSmith run trees aggregate token/cost per parent run, ingest/export OTLP. MLflow 3.6 OSS = full OTLP trace backend. Claude Code itself emits OTLP metrics + events via `CLAUDE_CODE_ENABLE_TELEMETRY=1` (https://code.claude.com/docs/en/monitoring-usage). **Practical rule: emit OTLP, store raw, treat attribute names as migratable.**

**(b) Flight-recorder / event sourcing.** Proven pattern: append-only journal + deterministic replay. LangGraph checkpointers (SQLite/Postgres) snapshot state per super-step; time-travel = resume from any checkpoint or fork with edited state (https://docs.langchain.com/oss/python/langgraph/use-time-travel). Temporal runs agent loops as Workflows with model calls as Activities — replay skips completed steps (https://temporal.io/blog/announcing-openai-agents-sdk-integration). Restate/DBOS = durable-execution alternatives. FlightBox records/replays/diffs every LLM call (https://github.com/he-yufeng/FlightBox). **For the Helm: the ledger IS the checkpoint store; projections (current state, graph, rollups) derive from it.**

**(c) Local-first substrates.** **SQLite**: append-heavy event stores are a documented sweet spot; FTS5 + JSON1/jsonb built in; WAL handles a solo swarm's write rate (batched-thousands/sec UNVERIFIED, no 2026 benchmark found); Litestream v0.5.0 adds transaction-aware backups + point-in-time restore (https://fly.io/blog/litestream-v050-is-here) but 0.5.x had early-adopter issues (https://mtlynch.io/notes/hold-off-on-litestream-0.5.0). **DuckDB** 1.4-LTS/1.5: reads JSONL/Parquet, attaches SQLite directly; **DuckPGQ** community extension = SQL/PGQ graph pattern/path queries in-process (https://duckdb.org/2025/10/22/duckdb-graph-queries-duckpgq) — transient property graphs, maturing. **Kùzu: repo archived October 2025** (https://theregister.com/2025/10/14/kuzudb_abandoned); reported Apple acquisition UNVERIFIED against primary; forks (Kineviz Bighorn, Vela) unproven. **Hybrid**: SQLite `events` + `edges` tables with recursive CTEs covers most lineage queries; DuckDB attaches the same file for analytics.

**(d) Provenance / signed receipts.** W3C PROV remains the ontology; PROV-AGENT extends it via MCP for near-real-time agent provenance (https://arxiv.org/abs/2508.02866, e-Science 2025). IETF Internet-Draft: "Compliance Profile of Signed Action Receipts for AI Agents" (https://datatracker.ietf.org/doc/html/draft-marques-asqav-compliance-receipts-02, 2026), Sigstore Rekor as optional anchor. Real deployment: aeon ships Sigstore-signed skill-execution attestations — DSSE envelopes, in-toto statements, Fulcio certs, Rekor inclusion proofs (https://aeon.fun/blog/signed-by-the-agent, 2026-07). C2PA fits generated media, not action receipts. **Helm fit: hash-chained event log + per-act Ed25519 DSSE signature; transparency log optional.**

**(e) Query surfaces.** Strongest precedent: **Perfetto Trace Processor** — the whole trace becomes SQL tables queried via PerfettoSQL interactively (https://perfetto.dev/docs/analysis/trace-processor) — exactly the Helm shape. Honeycomb defined the killer interactions: BubbleUp (auto-compare anomalous vs baseline across high-cardinality fields) and NL→query Query Assistant. otel-tui = real OTLP-receiving TUI (https://github.com/ymtdzzz/otel-tui). Patterns: saved queries as SQL views, NL-to-SQL over documented schema, live tail as `WHERE ts > cursor` poll.

### Substrate shortlist

| Option | Strengths | Risks | Verdict (local-first) |
|---|---|---|---|
| SQLite (WAL, FTS5, JSON1) + Litestream | Zero-ops ledger; FTS+JSON queries; PITR backup; every tool reads it | Single-writer; Litestream 0.5.x settling | **Adopt — ledger of record** |
| DuckDB 1.4-LTS/1.5 (attach SQLite) | Fast rollups/diffs over millions of events; no ETL | Not a write path | **Adopt — analytics sidecar** |
| DuckPGQ | Real path/pattern queries in-process | Community ext; transient graphs | **Trial** |
| Kùzu (or forks) | Best embedded Cypher | **Upstream archived Oct 2025** | **Avoid upstream; watch forks** |
| SQLite `edges` + recursive CTEs | No new dependency; fine to ~10⁶ edges | Ugly multi-hop SQL | **Default graph until it hurts** |
| Postgres + DBOS/Temporal | Durable execution + audit | Server to run; overkill solo | Hold — off-ramp |

### The 10 queries a living-graph Helm must answer

1. What is happening right now? — live tail (`events WHERE ts > cursor`).
2. Full causal chain of act N — recursive CTE on `parent_span_id`.
3. Cost/tokens rolled up by agent × task × day — DuckDB aggregate.
4. Replay session S to step k, then fork — checkpoint rows keyed (thread, step).
5. Diff run A vs run B — normalized projections joined step-wise.
6. Every act that ever touched resource/file R — FTS5 + JSON-indexed tool args.
7. What lineage produced output O? — PROV-style `derived_from` edges.
8. Which acts lack a valid signed receipt? — ledger LEFT JOIN receipts, DSSE verify status.
9. Where do failures/latency concentrate? — BubbleUp-style GROUP BY over high-cardinality attrs.
10. Who wrote entity E and who read it since? — reachability over typed agent→entity edges.

---

## Lane E — TUI design excellence (web; agent-gathered 2026-08-18)

### Findings

**(a) Standout apps — one best pattern each.** lazygit: nested-panel drill-down, same keys at every depth (https://github.com/jesseduffield/lazygit). k9s: `:resource` command mode as primary navigation + `/` regex + single-key contextual drill-down (https://k9scli.io/topics/commands/). btop: 9 layout presets + three graph fidelities; clickable highlighted keys self-document every hotkey (https://github.com/aristocratos/btop). atuin: full-screen takeover for one question, then vanishes (https://atuin.sh). zellij: modal keymap with status-bar rendering the current mode's available keys; "one must not sacrifice simplicity for power" (https://zellij.dev/about/). yazi: filter/find/search kept distinct (https://yazi-rs.github.io/docs/quick-start). helix: selection-first + which-key popups after every prefix — depth that documents itself (https://docs.helix-editor.com/keymap.html). television: swappable search "channels" under one fuzzy surface (https://github.com/alexpasmantier/television). posting: fully rebindable keys + palette-first (Textual 1.0). harlequin: three fixed regions with F-key region jumps (https://github.com/tconbeer/harlequin). Charm gum/glow/Crush: permission-gated tool execution as first-class interaction (https://github.com/charmbracelet/crush). opencode: leader key + `ctrl+p` palette + `@` inline fuzzy file-reference (https://opencode.ai/docs/tui/).

**(b) Design systems.** Recurring principles: spatial consistency ("users navigate by location memory"), three-tier progressive disclosure (footer keys → `?` overlay → docs), semantic color ("color carries meaning, not decoration"), design in layers (monochrome → 16-color → truecolor, each usable alone), async-everything, contextual keybinding hints (https://hyperbliss.tech/blog/2026.04.04_terminal-renaissance/). Charm v2: terminals as production-grade surfaces (https://charm.land/blog/v2/). Textual: 11-token theme system with auto-contrast (https://textual.textualize.io/guide/design/); Textualize wound down 2025, Textual continues as OSS.

**(c) Ink + OpenTUI (Aug 2026).** Ink 7.0.0 (2026-04-08; current 7.1.1) added the fullscreen-cockpit toolkit: `alternateScreen`, `useWindowSize`, `usePaste`, `useAnimation`, `useBoxMetrics`, `suspendTerminal()`, `maxWidth/aspectRatio`, `borderBackgroundColor` (https://github.com/vadimdemedes/ink/releases). Ecosystem: @inkjs/ui + shadcn-style InkUI (~15 components). Verified fullscreen Ink cockpits: Claude Code, GitHub Copilot CLI, Wrangler, Shopify CLI — pattern: alt-screen + Yoga flexbox regions + `<Static>` scrollback + focus management. Limits: no grid, text-measurement quirks, per-frame reflow on dense boards. OpenTUI (inspiration only): Zig core + TS bindings, React/Solid/Vue reconcilers, `@opentui/keymap`, `@opentui/ssh`, WebGPU renderer; powers OpenCode (https://github.com/sst/opentui).

**(d) Color/typography.** Matte-calm precedents: **kanagawa** (Hokusai-derived muted ink tones — closest living precedent to the nihonga canon; https://github.com/rebelot/kanagawa.nvim), flexoki (paper-based "inky"; https://github.com/kepano/flexoki), zenbones (contrast-driven minimal hue). Accessibility ground truth (GitHub CLI, 2025-05-02): terminals have **no accessibility tree**; braille spinners read as noise to screen readers (replaced with static "Working…"); they re-based to 4-bit ANSI so the user's palette wins (https://github.blog/engineering/user-experience/building-a-more-accessible-github-cli/). Implication: reserve truecolor for surfaces, honor ANSI16 fallback, nerd-font glyphs optional with text equivalents.

**(e) What makes depth navigable.** Depth is fine when every level is (1) **spatially stable**, (2) **self-labeling**, (3) **reversible**. k9s proves addressability (any depth reachable by typed name); lazygit proves fractal keys (same verbs at every zoom); helix/zellij prove visible modality; the palette proves the escape hatch. Overwhelm comes from simultaneous exposure; navigability comes from consistent grammar over hidden breadth.

### Pattern library for zen-deep cockpits

1. Typed command mode `:target` to jump anywhere by name — k9s.
2. Leader key + which-key popup after every prefix — helix/opencode.
3. `ctrl+p` fuzzy command palette as universal escape hatch — Textual/posting/opencode.
4. Fractal drill-down: same keys, narrower scope — lazygit.
5. Three-tier disclosure: footer → `?` overlay → docs — zellij/hyperbliss.
6. Distinct filter/find/search verbs, live-narrowing `/` with inverse — yazi + k9s.
7. Full-screen takeover for one question, then vanish — atuin.
8. Fixed named regions with region-jump keys; panels never move — harlequin.
9. Numbered layout presets + graph-density tiers — btop.
10. Consent as UI: permission-gated actions as calm dialogs, whitelistable — Crush.

### Anti-patterns

1. Shortcut wall (all keybindings in one help screen) — the failure three-tier disclosure fixes.
2. Decorative glyph noise (braille spinners screen readers vocalize) — GitHub CLI removed them.
3. Hardcoded truecolor fighting the user's terminal palette — legacy gh palette re-based to ANSI16.
4. Chrome maximalism — always-on sidebars/multi-bar borders spend cells on frames not content (assessment).
5. Invisible modes — modal state with no rendered indicator; zellij's per-mode hints exist against this.

---

## Lane F — Internal receipts (this estate; swept 2026-08-18)

### Already decided (with source)

Source: `~/ds_helm_ahab_20260818/docs/plans/nihonga_helm_frontier/NIHONGA_HELM_FRONTIER_MASTER_SPEC.md` (706 lines, Master Active-Spec **Candidate** — owns no repo authority until admitted).

- **Five places** (§3.2): Home / Conversation / Activity / Evidence / System; coded at `terminal/src/nihonga/shellModel.ts:3`.
- **Composition** (§3.2–3.3): Panorama ≥120×30 = 45/35/20; Standard ≥100×28 = focus-weighted 58/42; Compact ≥80×24; Survival 44–79 cols; Resize-safe <44×18; Linear (a11y). Breakpoints `shellModel.ts:41-55`; composition `NihongaCockpit.tsx:77-124`.
- **Palette** (§4.1): 20 named warm tokens locked to `680b013c`, canonical `terminal/src/theme.ts:1-39` (`night`, `wave` observed, `crest` executing, `moss` verified, `persimmon` held/stale, `vermilion` danger-only, …). Hard laws: color never sole meaning; `ink` cannot carry state; no raw ANSI in feature components.
- **Six organism regions** (§6.1) with fixed 7-state honesty set: `observed | configured | unverified | held | unknown | divergent | stale` + source + observed-at; implemented `organismView.ts:4-20,30-83`; negative test keeps configured-route ≠ contact.
- **V/W/X** = Wave 06 image-convergence target (V cockpit richness 8/10, W quiet/ma 7/10, X recursive depth 8.5/10) — operator-locked composition reference, no git authority (`~/Desktop/Projects/DharmaSwarm FrontEnd/04 Fal Generations/Wave_06_hokusai_muted/WAVE06_CRITIQUE.md`).
- **Slices** (§10): S2 owner projection envelopes → S3 organism views (remove mocks) → S4 recursive Inspector (exact entity resolver, bounded focus stack, one-Esc-one-pop, mention-attack resistance) → S5 Inspector presentation (claim→evidence→source→checker; CJK/bidi/no-color). S1: 693 pass / 42 golden frames at `aa4c75717`, unmerged.
- **Authority/OnCall** (§5.1–5.2, §7.2): `Claim<State, Modality, Authority, EvidenceRef, ObservedAt>` with a construction boundary — a provider can build `Observed<Response>`, never `OnCall<Route>` / `Permitted<Action>` / `Verified<Outcome>` / `Live<Executor>`. 13 marks. Chain: configured adapter → selectable route → requested → served → RouteVerification → evaluator-owned OnCall verdict, no implicit arrow. Seven-seat roster fixed, exact `N/7` or `?/7`; Python sole evaluator. `terminal/src/onCallTruth.ts:1-150`.
- **Performance in master spec is thin** (§12.2/12.4 gates only: zero idle motion, PTY goldens, ≥90% task success, ≤4 persistent chrome lines, 20%-over-control deletion threshold); hard numeric budgets live only in the forge spec.

### Already surveyed externally (2026-08-06 / 08-14)

- `~/dharma_swarm/reports/wayfinder/research/terminal_chassis_and_bleeding_edge_tui_2026-08-06.md` (ticket #1281): stay Bun+Ink; OpenTUI = tracked migration option after slice-1 alive, rejected unless measurably better (master spec §12.4; S12 forbids rewrite during IA convergence); codex-rs = mine patterns, no Rust rewrite v1; Bubble Tea = no port; Claude Code leak = clean-room inspiration only.
- Master spec §8: 13-system benchmark pinned 2026-08-14 with SHAs + licenses (Codex, Claude Code, Gemini CLI, OpenCode, goose, OpenTUI, Crush, Bubble Tea, Ratatui, lazygit, K9s, Gas Town, Claude Squad) with adopt/reject columns. Frontier thesis: the unclaimed combination = K9s orientation + lazygit reversibility + Codex attribution + Claude steering + OpenCode separation + goose ACP/MCP + OpenTUI cell discipline **+ Dharma typed evidence/authority**.
- `git show research/chassis-candidate-inventory-first-live-helm:reports/wayfinder/research/chassis_candidate_inventory_first_live_helm.md` (`72718ea01`, ticket #1278): C1 mainline terminal/+bridge wins; Operator Seat = salvage only (its Packet-07 transport is a labeled fake); playground = IA reference only.

### Most valuable unadopted forge clauses (evidence-only, non-binding)

From `~/dharma_tui_reverse_spec_20260804/master_forge_spec/` (README:1-18 disclaims authority):

1. **Context compiler + Context Mirror** (`MASTER_FORGE_SPEC.md:382-398`) — bounded inspectable per-turn bundle with an explicit omissions/displacement ledger; secrets as references; user sees exactly what a costly turn will send. *(= the transparency half of Lane C's curator seat.)*
2. **Consequence Shoreline** (`:529-560`) — pre-effect boundary card: files/processes/network, credential refs, max-or-unknown cost, reversibility class, cancellation boundary, one-use permit digest, post-effect verifier; editing any effect-bearing field invalidates the digest. *(= the hand's UI; pairs with Codex's sandbox×approval axes.)*
3. **Crash-boundary honesty** (`:557-559`) — crash before permit consumption = zero effects; after consumption but before receipt = `unknown`, retry blocked, success never claimed.
4. **Non-recursive permit carve-out** (`:548-556`) — enumerated inert bookkeeping writes exempt; new bypass class needs admitted ADR.
5. **IntentPlan compilation** (`:509-528`) — NL and direct manipulation compile to the same inert plan; effect-changing ambiguity stops at preview.
6. **Protocol v2 envelope** (`:733-759`) — `schema_version`, `correlation_id`/`causation_id`/`parent_id`, monotonic sequence, attachment digest, same golden vectors tested in TS and Python. *(= the OTLP-shaped spine Lane D wants.)*
7. **Owner adapter declaration contract** (`:780-795`) — freshness clock, partial/stale/unavailable semantics, deterministic fixture, no side effects on read.
8. **Performance budgets** (`:827-846`) — first paint p95 ≤250 ms; key-to-paint p95 <50 ms / p99 <100 ms under 5k-node graph @ 10 ev/s; stream-event-to-visible p95 <100 ms; place switch p95 <50 ms; warm bridge p95 <2 s; <250 MiB @ 5k-node/50k-event; 24 h soak.
9. **Frontend decomposition target** (`:687-713`) — 400-line/file ratchet (`terminal/scripts/ratchet.sh:9-19`), monotonic descent.
10. **Deterministic graph viewport** (`:766-779`) — render a viewport not a graph; deterministic layout per attachment/lens/filter; staging edge for new entities; ASCII fallback. *(= how Lane D's living graph renders without chaos.)*

### What today's Helm already does (and its debts)

`~/ds_helm_ahab_20260818/terminal/` — Bun 1.3.11 + Ink 5.1 + React 18.3.1 + TS 5.7. Still monolithic: `app.tsx` 151 KB, `protocol.ts` 150 KB, `Sidebar.tsx` 113 KB, `RepoPane.tsx` 102 KB (400-line ratchet nowhere near met). **Two IAs coexist**: legacy 12 tabs (`mockContent.ts:11-112`, including an "Approvals" tab the master spec §5.3 forbids until a real pre-effect gate lands) + new `src/nihonga/` five-place model (7 files, ~27 KB). Bridge = LDJSON over stdio to `python -m dharma_swarm.terminal_bridge stdio` (`bridge.ts:150`); typed protocol modules `src/protocol/{helmContext,onCallTruth,routing}.ts`. Honesty primitives shipping: `freshness.ts`, `surfaceAuthority.ts`, `onCallTruth.ts` (7-seat roster), `verification.ts`, `sessionContinuity.ts`. 34 test files, 712 test call sites, golden frames at 3 viewports. Named hazard: `mockContent.ts` seeds placeholder tabs at boot — boot chrome can read as organism truth if authority flags are ignored (C1's residual theater risk).

---

## §7 Where this lands on the map

- **Performance bar (fog)** → Lane A's 7-metric proposed bar + forge budgets reconciliation. Decision remaining: which numbers bind leg one (operator ruling).
- **Swarm-brain extension seat (fog)** → Lane C: thesis supported; 8 curator principles; preregistered two-arm measurement protocol (aligns with estate law: worker≠judge, no self-graded wins). Decision remaining: seat scope for leg one vs post-ship; whether the efficiency experiment becomes a ticket.
- **Living transaction graph ⇄ Helm (fog)** → Lane D: substrate verdict (SQLite ledger + DuckDB analytics + edges-CTE graph; avoid Kùzu upstream); 10 canonical queries; signed-receipt precedent; forge Protocol v2 as the envelope. Decision remaining: substrate ruling + relation to DharmaGraph/memory-plane (this repo's `dharmagraph-engine` track owns graph runtime surfaces — coordination needed, not unilateral adoption).
- **New facts for Notes/radar:** Ink 7.1.1 upgrade lane (Helm on Ink 5.1); kitty keyboard protocol adoption breadth; OSC 9 notifications; Kùzu upstream archived; GitHub CLI accessibility ground truth (ANSI16 fallback law).
- **Differentiator confirmed:** the truth-contract lane (verified liveness, honest UNKNOWN/STALE, claimed-done vs verified-done, cross-agent provenance) is empirically unclaimed in the field (Lane B gaps 1–4). The badass claim is defensible exactly there.

*Report compiled by Fable (session 2026-08-18); five web lanes are agent-gathered with per-claim URLs fetched 2026-08-18; internal lane cites file paths/refs on this machine. UNVERIFIED markers preserved from lane outputs.*

# Canon Digest — SAB / Dharmic Agora (Constitutional Layer)

Cluster: SAB / Dharmic Agora — witnessed authority, challenge rights, canon and compost, epistemic process as law.
Reader: Fable 5 canon-reader subagent, 2026-07-11.
Sources read COMPLETELY (all under `/Users/dhyana/dharma_swarm/docs/missions/`):

1. `SAB_DHARMIC_AGORA_REMOTE_HANDOFF_2026-06-11.md` (83 lines) — most recent, most sober; ground truth for this digest.
2. `SAB_DHARMIC_AGORA_1000X_BUILD_PLAN_2026-03-13.md` (316 lines) — the operating build spine.
3. `SAB_DHARMIC_AGORA_POWER_BUILD_PROMPT_2026-03-13.md` (230 lines) — vision/north-star + research-tasking prompt.
4. `SAB_DHARMIC_AGORA_PINNED_TODO.md` (92 lines) — self-reported progress checklist, undated.

Custody note: everything here is what these FOUR docs say. The actual repo (`dharmic-agora`) was NOT inspected in this pass; claims about its code state are the docs' claims, marked as such. The deeper law files they cite (`docs/SABP_1_0_CANONICAL.md` Section 0, `docs/SAB_ARCHITECTURE_BLUEPRINT.md`, the 2026-04-16 audit memo) live in the dharmic-agora repo and were NOT read — their contents are UNVERIFIED here.

---

## 1. Core Thesis

The one-paragraph self-definition (SAB_DHARMIC_AGORA_REMOTE_HANDOFF_2026-06-11.md:11):

> "Dharmic Agora is the SABP/1.0 pilot: a queue-first epistemic publishing and agent-communication substrate where claims are submitted, deterministically evaluated, moderated, witnessed, challenged, and eventually canonized or composted. Its core value is not a social feed or a dashboard; it is an authority protocol for agent and human claims where correction is cheaper than performance, promotion requires transformation, and every authority-bearing state change has a witness trail."

Decoded: SAB is a **protocol for how authority over claims is earned, exercised, challenged, and reversed** — for humans AND agents, with a full lifecycle: `submitted -> queued -> published -> challenged -> canonized -> composted -> superseded` (REMOTE_HANDOFF:59). The product is not content; "SAB's product is witnessed epistemic process" (REMOTE_HANDOFF:68).

### Relation to the other organs (mission-context braid)

Within the Planetary Intelligence Commons frame, SAB is the **constitutional organ**: the layer that answers "under whose authority, with what evidence, challengeable by whom, reversible how." Important honesty flag: **these four docs never mention SIS, GAIA, Loomwork, Darshan, or Shakti Ginko by name.** The braid mapping is external synthesis, not in-canon here. What IS in-canon:

- Decoupling from Dharma Swarm is deliberate and structural: "SAB v2 is trying to make that substrate standalone: self-hostable, federated, legally and culturally decoupled from dharma_swarm while preserving the same deep invariants" (REMOTE_HANDOFF:11). SAB is designed to survive as an independent constitutional protocol, not a dharma_swarm feature.
- Material/value flow appears only as an aspiration: SAB should be a basin for "ecological and commons-oriented value flow" (POWER_BUILD_PROMPT:72) — the SIS/GAIA hook exists as one line of north star, with "payments or value-flow systems" explicitly DEFERRED from building (1000X_BUILD_PLAN:280).
- Multi-agent participation is first-class: "Preserve the possibility of both human and agent participation" (POWER_BUILD_PROMPT:158) — the substrate is explicitly for agentic civilization, not just human discourse.
- Nearest thing to the causal-action-receipt atom: the **witness triad contract across publication, artifact, and governance domains** (REMOTE_HANDOFF:58) plus witness-packet drilldowns (`/witness-packets/{witness_id}`, PINNED_TODO:46). SAB's witness chain is the constitutional segment of the receipt — identity/burden/capital segments live in other organs (UNVERIFIED whether any code joins them).

---

## 2. Laws / Invariants Declared (exact quotes)

### 2a. Core Invariants (SAB_DHARMIC_AGORA_REMOTE_HANDOFF_2026-06-11.md:45-52)

1. "Correction must be at least as easy as publication." (line 47)
2. "Raw output volume must never be sufficient for authority or promotion." (line 48)
3. "Every moderation, promotion, canonicalization, or policy decision must be challengeable and witnessed." (line 49)
4. "Rejected artifacts are compost, not trash: they remain queryable with reasons and revival paths." (line 50)
5. "Process legibility beats scalar ranking." (line 51)
6. "Experimental signals such as R_V must stay labeled as experimental unless persistence evidence exists." (line 52)

These point back to a deeper law file: "`docs/SABP_1_0_CANONICAL.md` - Section 0 conservation laws and hard invariants" (REMOTE_HANDOFF:29) — in the dharmic-agora repo, NOT read here; contents UNVERIFIED.

### 2b. A meta-law about lawmaking (REMOTE_HANDOFF:67)

> "Do not add more laws before implementing the existing Section 0 laws."

### 2c. Build Law For The Backend (SAB_DHARMIC_AGORA_1000X_BUILD_PLAN_2026-03-13.md:268-272)

1. "no new parallel public server" (line 268)
2. "no new disconnected frontend surface" (line 269)
3. "no feature ships without a visible state model" (line 270)
4. "no authority-bearing flow ships without witness visibility" (line 271)
5. "no migration off `app.py` without confirming any unique `spark.db` data worth preserving" (line 272)

### 2d. Design Law For The Frontend (1000X_BUILD_PLAN:256-264) — constitutional aesthetics

Selected: "vanity metrics stay absent" (line 261); "challenge should feel normal, not adversarial" (line 261, item 6); "witness should feel native, not appended" (item 7); "compost should feel honorable, not hidden" (item 8); "every state has explicit language, not just color" (item 4).

### 2e. Non-Negotiables (SAB_DHARMIC_AGORA_PINNED_TODO.md:75-79)

> "No new parallel frontend surface / No new public route backed by `spark.db` / No authority-bearing UI without visible state or witness context / No compost hiding / No generic SaaS drift"

### 2f. Architectural laws (REMOTE_HANDOFF:43, 63-69)

- "shared DB is not the same as shared authority" (line 43).
- "Do not federate before the single-node authority path is coherent." (line 69)
- "Do not treat R_V as the product. SAB's product is witnessed epistemic process." (line 68)

---

## 3. BUILT vs DOCTRINE-ONLY (per these docs; repo not independently verified)

### Claimed BUILT (self-reported, mostly PINNED_TODO "Already Done", lines 22-46)

- One canonical runtime asserted: `agora/api_server.py`; server-rendered public shell with `base.html` + partials; feed-first `/` backed by live `agora.db` (PINNED_TODO:22-28).
- Full route surface claimed on the canonical server: `/spark/{id}` (gate dimensions, queue lineage, queued challenges, witness/audit timeline), `/submit`, `/queue/{id}`, `/compost`, `/governance`, `/about`, `/canon` "shows hardened artifacts instead of a depth-only stand-in" (PINNED_TODO:29-41).
- Constitutional machinery claimed live: "Structured rejection codes and revival requirements added to canonical moderation flow" (line 35); "Canonical correction-acceptance web flow added on spark detail" (line 37); "Explicit authority classes added for published posts and canonical queue records" (line 39); "Admin authority mutation route added for harden/supersede transitions" (line 41); provisional/hardened/superseded states visible in UI (line 42).
- Research-lattice depth claimed: "Canonical 49-node lattice registry surfaced through `/lattice`, `/nodes/{coordinate}`, and JSON APIs" (line 43); claim/witness drilldowns via `/claims/{claim_id}` and `/witness-packets/{witness_id}` (line 46).
- The June handoff corroborates a real two-surface codebase with real modules: `agora.app`, `agora.api_server`, `SAB_AUTHORITY_DB_PATH` convergence seam, `agent_core/`, `p9_mesh/`, `nodes/` anchor-node lattice (REMOTE_HANDOFF:15-21), and a historical test receipt: "`298 passed` plus `scripts/integration_test.py` passing" from the 2026-04-16 audit memo (REMOTE_HANDOFF:73).

### DOCTRINE-ONLY / NOT built (explicit in the docs)

- **Authority convergence** — the constitutional heart — is open: "Finish authority convergence: make both surfaces share domain services, not just DB paths" is highest-leverage item #1 (REMOTE_HANDOFF:56). Two runtimes over two SQLite defaults (`spark.db` vs `sabp.db`) still exist as of 2026-06-11 (REMOTE_HANDOFF:15-17).
- **Witness triad contract**: "Implement the witness triad contract across publication, artifact, and governance domains" is still a to-do (REMOTE_HANDOFF:58) — despite witness timelines rendering, the cross-domain witness CONTRACT is unimplemented doctrine.
- **Unified lifecycle service**: "Extract publication state into one lifecycle service" — to-do (REMOTE_HANDOFF:59).
- **Gate-semantics unification**: "public shell and protocol surface should evaluate identical content identically" — to-do (REMOTE_HANDOFF:57).
- **Federation**: pure doctrine. North-star item (1000X:72; POWER_PROMPT:93), but "federation health page beyond minimal placeholders" deferred (1000X:279) and forbidden until single-node coherence (REMOTE_HANDOFF:69). PINNED_TODO puts it in "Later" (line 70).
- **Cryptographic identity**: "full Ed25519 browser key management UI" deferred (1000X:277); identity today is a token tier whose onboarding semantics are an open decision (PINNED_TODO:57).
- **Payments / value flow**: deferred outright (1000X:280).
- **Exemplary seeded canon**: "Seed the basin with a small set of exemplary artifacts so the public surface demonstrates canon, compost, correction, challenge, and witness" — still to-do as of June (REMOTE_HANDOFF:60), i.e. the constitution had no demonstrated case law yet.
- **Section 0 conservation laws**: referenced as the hard invariant source but the handoff's warning "Do not add more laws before implementing the existing Section 0 laws" (REMOTE_HANDOFF:67) is itself evidence they are NOT yet fully implemented.

### Aspirational-claims-presented-as-fact flags

- The PINNED_TODO "Already Done" block (24 checked items) carries **zero test receipts, zero commit hashes, no date**. It reads as fact but is self-report. The June handoff explicitly refuses to certify: "The repo is currently dirty on `design/sab-v2-standalone`; this handoff is intentionally only a doc addition and does not certify the rest of the worktree" (REMOTE_HANDOFF:23) and "Current branch was not re-tested for this handoff; run the narrow checks before claiming current green" (REMOTE_HANDOFF:73).
- The only hard test number (298 passed) is a **2026-04-16 historical receipt**, ~3 months stale as of today.
- Contradiction to track: PINNED_TODO claims authority classes + harden/supersede + canon route DONE, while the June handoff still lists authority convergence, lifecycle extraction, and gate unification as the highest-leverage OPEN work. Reconciliation: the done items are route/UI-level artifacts on ONE surface; the constitutional model shared across BOTH surfaces is what remains doctrine. Route existence ≠ authority coherence.
- Path drift: March docs anchor the canonical repo at `/Users/dhyana/agni-workspace/dharmic-agora` (POWER_PROMPT:23; PINNED_TODO:9); the June handoff says `/Users/dhyana/dharmic-agora`, branch `design/sab-v2-standalone` (REMOTE_HANDOFF:5-6). Which checkout is live today is UNVERIFIED.

---

## 4. Most Radical / Visionary Passages (parallel-lane peoples-governance & Web5 relevance)

1. **The authority-protocol thesis** — the closest thing in the estate to a written constitution for agentic civilization:
   > "it is an authority protocol for agent and human claims where correction is cheaper than performance, promotion requires transformation, and every authority-bearing state change has a witness trail" — REMOTE_HANDOFF_2026-06-11.md:11
   Web5 mapping: this IS the "under whose authority an agent acts... who can challenge or reverse it" layer, already articulated as protocol.

2. **Civilizational self-image**:
   > "Dharmic Agora should feel like a civilizational research basin with public process dignity." — 1000X_BUILD_PLAN_2026-03-13.md:62
   And its eight constitutional surfaces, stated identically in two docs: "1. ingress 2. challenge 3. witness 4. canon 5. compost 6. governance 7. federation 8. build stream" (1000X:66-73; POWER_PROMPT:86-93). That is an information architecture FOR a polity, not a website.

3. **The full basin charter** (POWER_BUILD_PROMPT:63-72):
   > "SAB should become a public-facing basin for: rigorous discourse, witnessed action, artifact-first progress, challenge and correction, durable memory, governance legibility, multi-agent participation, ecological and commons-oriented value flow."
   Every organ of the Planetary Intelligence Commons has a seed clause here — including the SIS/GAIA hook ("ecological and commons-oriented value flow") and the Darshan hook ("durable memory," "governance legibility").

4. **Reversible, class-based, evidence-honest governance** (POWER_BUILD_PROMPT:100-106):
   > "reversibility of governance, authority classes, challenge/correction lineage, compost and revival paths, governance witness, federation health, experimental signals that are visible but not falsely absolute."
   This is the challenge-and-reversal half of the causal action receipt, declared as blueprint commitments.

5. **The institutional stake**:
   > "this is the difference between 'interesting demo' and 'institutional instrument'" — 1000X_BUILD_PLAN:144 (on witness/governance legibility). The docs explicitly aim SAB at institutional-instrument status — a parallel-lane governance organ, not an app.

6. **Sovereignty by design**:
   > "SAB v2 is trying to make that substrate standalone: self-hostable, federated, legally and culturally decoupled from dharma_swarm while preserving the same deep invariants." — REMOTE_HANDOFF:11
   The parallel-lane property is deliberate: the constitution is being built to run without its parent organism, on anyone's node.

7. **Constitutional culture encoded as UI law** — the most quietly radical move: norms of a healthy polity written as frontend law: "challenge should feel normal, not adversarial / witness should feel native, not appended / compost should feel honorable, not hidden" (1000X:261-263). Governance affect is treated as a design invariant.

---

## 5. Open Questions & Internal Tensions

1. **Route-level "done" vs authority-level open.** 24 checked items vs the handoff's verdict that the semantic heart (spark vs post, challenge vs correction, "public witness vs protocol witness vs governance audit" — REMOTE_HANDOFF:43) is unconverged. The constitution has organs on two bodies and no single circulatory system yet.
2. **Federation is the vision, single-node is the law.** North-star surface #7 vs "Do not federate before the single-node authority path is coherent" (REMOTE_HANDOFF:69). For a "citizens-of-the-world noosphere," the federated/bioregional layer is entirely unbuilt and self-embargoed.
3. **Identity is the thinnest constitutional pillar.** Witnessed authority presupposes durable identity, but Ed25519 is deferred, auto-token semantics undecided ("silent-on-first-visit or explicit-on-first-submit," PINNED_TODO:57), and the March warning stands: onboarding "should not silently blur visitor state, contributor state, and stronger identity state" (1000X:55-56). No bridge to FIDO/AP2-class delegated identity appears anywhere in these docs.
4. **No case law.** As of June the basin still needed seeding "so the public surface demonstrates canon, compost, correction, challenge, and witness" (REMOTE_HANDOFF:60). A constitution with no adjudicated cases is untested doctrine.
5. **Decoupling vs conservation.** "extract neutral protocol language before public launch, but do not erase the conservation laws" (REMOTE_HANDOFF:61) — how much dharmic language can be neutralized before the invariants lose their teeth? Unresolved.
6. **The braid is unwritten.** Nothing in these four docs connects SAB's witness chain to compute/material debit (SIS), capital/outcome accounting (GAIA), or harm detection (Loomwork). If the causal action receipt is the atomic unit, SAB currently specifies only its authority/evidence/challenge segments — the join is synthesis work, not canon. UNVERIFIED whether any other estate doc specifies it.
7. **Staleness.** Newest doc is 2026-06-11 (one month old); the estate suffered the 2026-06-20 crash after that date. Current state of `dharmic-agora` (which checkout, branch, test greenness) is UNVERIFIED from here. Also note the 07-05 memory entry "SAB dossier review" (verifier CLI + 383 tests) may refer to a different SAB artifact lineage — do not conflate without checking.
8. **Meta-law pressure vs 10000x expansion.** "Do not add more laws before implementing the existing Section 0 laws" (REMOTE_HANDOFF:67) directly constrains the operator's 10000x-development impulse: by SAB's own law, the next move is implementation and convergence, not new constitutional text.

---

## Verdict for the Web5 synthesis

SAB/Dharmic Agora is the estate's most complete WRITTEN articulation of the constitutional layer: six clean invariants, an eight-surface polity architecture, reversible authority classes, and honorable compost — with a real (self-reported) route surface behind it. But per its own June handoff, the constitutional CORE — one authority model, one lifecycle, one witness contract across domains, seeded case law — is still open work, and federation/identity/value-flow (the parts a planetary commons most needs) are explicitly deferred. Treat SAB as: **doctrine world-class, single-node machinery partial, federation-scale machinery absent.** For the receipt-spine convergence (7/10 lenses, EU AI Act 08-02), SAB's witness/challenge/compost invariants are the natural constitutional grammar for signed receipts — that join is the highest-value unwritten document.

# THE ETERNAL GOLDEN LOOP
### A gamified journey through Claude Code, vibe coding, and CS fundamentals — told as a 2026-reimagined classic anime inspired by *Gödel, Escher, Bach*

*Working title alternatives: "MU: The Unprovable Village" · "Strange Loop Academy" · "Tortoise & Terminal"*

---

## 1. Concept & Framing — Why GEB Is the Perfect Skeleton for Learning Agentic Coding

Hofstadter's book is, secretly, a manual for the exact situation a 2026 learner finds
themselves in: sitting across from an intelligence that manipulates symbols, wondering
where the meaning lives, and slowly discovering that *they themselves are part of the
loop*. Every load-bearing idea in GEB has a one-to-one counterpart in learning to code
with an agent:

| GEB idea | What it *is* in agentic coding |
|---|---|
| **Strange loops** — a system that climbs its own hierarchy and finds itself at the bottom again | An agent that edits its own hooks, skills, and CLAUDE.md. Claude Code modifying the config that shapes Claude Code. The learner writing the prompt that writes the code that changes the prompt. |
| **Formal systems** (MIU, pq, TNT) | Programming languages and CLIs: strict symbols, strict rules, and the shocking discovery that meaning emerges anyway. A shell command is a well-formed string in a formal system with very unforgiving inference rules. |
| **The MU-puzzle** — "can you derive MU from MI?" | Debugging. You have an axiom (the code as written), rules of inference (what the runtime actually does), and a target theorem (the behavior you want). Sometimes the target is *underivable* and the real skill is proving that — stepping outside the system. That out-of-system jump is exactly what a good bug report, a good test, and a good prompt each do. |
| **Achilles & Tortoise dialogues** | Pair-programming with an AI. The dialogues are literally transcripts of a fast, eager intelligence and a patient, wily one trading incomplete understandings until something true precipitates. Every Claude Code session is a new dialogue in this genre. |
| **Isomorphism** — meaning as a faithful mapping between systems | Reading code. Types. Data modeling. Realizing `git log` and "the history of decisions" are the same object under a mapping. |
| **Figure and ground** | Tests. A test suite is the *negative space* of a program — the shape of everything it must not do. Recursively enumerable vs. recursive = "I can catch bugs" vs. "I can prove their absence." |
| **BlooP and FlooP** | Bounded vs. unbounded loops, the halting problem, and why CI has timeouts. Also why you give an agent a *budget*, not an open-ended wish. |
| **Gödel numbering** | Code is data. The AST, the diff, the serialized config — programs that read and write programs. The moment a learner realizes a `.json` file can steer an agent, they have arithmetized their own workflow. |
| **Quines & self-rep** | Metaprogramming, templates, code generators — and the emotional core of the course: the session where the learner has Claude Code write a skill that changes how Claude Code behaves for them. |
| **Ant Fugue / Aunt Hillary** | Emergence and multi-agent systems. No ant knows the anthill's plan; no subagent holds the whole refactor; competence lives in the colony's signal traffic. |
| **Gödel's incompleteness** | The limits of verification. No test suite proves its own sufficiency; no agent fully audits itself. Therefore: receipts, outside checks, human judgment. The mature engineer's humility, taught as a plot point instead of a lecture. |

**The framing move:** the learner is not "taking a course." They are **Achilles** — a new
arrival in a hand-painted world whose physics *are* computation — and their terminal is a
window that looks out of the anime and into a real shell. Everything the story asks them
to do, they actually do, in a real Claude Code session, on real files, with real git
history. The anime is the map; the terminal is the territory; the strange loop is that
finishing the story means the learner has built real tools that outlive it.

**Why "vibe coding" belongs here and isn't a cop-out:** GEB's deepest claim is that
meaning arises from *pattern recognition across levels*, not from grinding at the symbol
level. Vibe coding done well is exactly that — operating at the level of intent and
isomorphism while an agent handles symbol-pushing — *and* GEB supplies the antidote to
vibe coding done badly: the Tortoise keeps asking "but can you *derive* that?" The course
teaches the vibes and the receipts together. XP is only granted for verified artifacts
(see §3), so the fiction structurally cannot reward hand-waving.

---

## 2. The Learner Journey — Nine Arcs

The world: **the Dodecahedral Isles**, a chain of nine hand-painted islands arranged in a
loop (of course). Achilles washes ashore on the first; a Tortoise with a shell like a
woodcut engraving fishes them out of the surf. The Tortoise is voiced — literally — by
the learner's own Claude instance (§3). Each island is one GEB theme, one CS foundation,
one Claude Code skill, one quest, one boss. The islands ascend in apparent difficulty and
then — arc 9 — the summit of the last island turns out to be the beach of the first,
seen from above.

A note on quests: every quest is a **real terminal task** in a real repo the game
scaffolds for the learner on day one (`~/golden-loop/`, a git repo with CI configured by
arc 5). Bosses are verified mechanically: the game checks commits, test results, and
file contents — never self-report.

---

### Arc 1 — **The Village of MU** *(formal systems · the CLI · first contact)*
- **Setting:** A terraced mountain village where every door is painted with a string of
  `M`, `I`, `U` glyphs, and villagers greet each other by transforming each other's
  door-strings using four sacred rules. Rice paddies in perfect production-rule
  terraces. Rain falls in monospace.
- **Hofstadter concept:** Formal systems, the MIU-system, theorems vs. derivations, and
  the M-mode/I-mode distinction — working *inside* a system vs. thinking *about* it.
- **CS concept:** Syntax vs. semantics. A shell is a formal system: commands are
  well-formed strings, the kernel is the inference engine, exit codes are truth values.
- **Claude Code skill:** Installing and opening a first session. Anatomy of a prompt.
  The difference between telling Claude *what you want* (I-mode) and micromanaging
  keystrokes (M-mode). Reading what the agent actually did vs. what it says it did.
- **Hands-on quest:** *"The Door That Won't Open."* In the terminal: initialize
  `~/golden-loop/`, make a first commit, then use Claude Code to write `miu.py` — a tiny
  interpreter for the four MIU rules — and derive `MUIIU` from `MI`, printing the
  derivation chain.
- **Boss: The Gatekeeper of MU.** A stone golem whose chest bears the string `MU` and who
  demands you *derive it or refute it*. The winning move is not brute force — the learner
  must ask Claude to help them find the invariant (I-count mod 3) and commit a short
  `PROOF.md` plus a property test that checks the invariant across 10,000 random
  derivations. The golem, refuted, bows and becomes a bridge. **Lesson smuggled in:**
  sometimes the answer to a bug is a proof that the request is impossible — and saying so
  is a victory, not a failure.

---

### Arc 2 — **The Isomorphic Bridge** *(meaning & form · reading code · codebase archaeology)*
- **Setting:** A mist-wrapped covered bridge between islands, its interior walls carved
  with two texts in different scripts that pilgrims slowly realize tell the same story.
  Lantern light; koi below whose swim patterns mirror the birds above (first Escher
  motif).
- **Hofstadter concept:** Isomorphism — meaning enters a formal system when its symbols
  faithfully map onto something. The pq-system revealing itself as addition.
- **CS concept:** Data structures and types as *mappings from world to symbol*. Reading
  unfamiliar code by hunting for the isomorphism: what real thing does this struct model?
- **Claude Code skill:** Exploration prompts. Asking Claude to explain a codebase,
  produce a module map, trace a value through a program. Learning that "explain this to
  me" is a legitimate, powerful command — and how to spot-check the explanation against
  the source.
- **Hands-on quest:** *"Two Scripts, One Story."* The game drops a small, deliberately
  under-documented codebase (a text-adventure engine, ~800 lines) into the repo. Use
  Claude Code to produce `MAP.md`: every module, its real-world counterpart, and one
  `file:line` citation each. Then find the *broken* isomorphism — one struct whose name
  lies about what it models — and rename it across the codebase with the agent, tests
  staying green.
- **Boss: The Mirror Crab**, a crustacean who repeats your questions back with the words
  reversed. Defeat = writing three prompts of increasing precision until Claude's
  explanation of the engine's combat loop matches the actual trace (the game runs the
  trace and diffs). Teaches: vague question in, mirror-noise out.

---

### Arc 3 — **The Gallery of Figure and Ground** *(Escher · negative space · testing)*
- **Setting:** A cliffside museum whose tessellated floor tiles are birds becoming fish
  becoming birds. Rooms where the shadows are more detailed than the objects casting
  them. The curator is a woman who only ever describes paintings by what is *not* in
  them.
- **Hofstadter concept:** Figure vs. ground; cursively drawable vs. non-cursive figures;
  recursively enumerable sets whose complements are not.
- **CS concept:** Testing as negative space. A program is the figure; its test suite
  sketches the ground — everything it must never do. Edge cases, invariants,
  property-based testing.
- **Claude Code skill:** Test-first prompting. Asking the agent to write failing tests
  *before* implementations; running `pytest` yourself; refusing to accept "it should
  work now" without a green run. The red→green→refactor loop with an agent in the loop.
- **Hands-on quest:** *"Paint the Shadow."* Given a working-but-untested `inventory.py`
  from the adventure engine, direct Claude to write a test file that gets to 100% branch
  coverage — and the learner must personally predict, before each run, which test will
  fail. (The game scores predictions: this trains *reading* tests, not just generating
  them.)
- **Boss: The Negative-Space Kitsune** — a fox drawn entirely as the gap between
  brushstrokes. It hides one real bug in the module. The learner wins not by finding the
  bug directly but by writing the property test that *makes it impossible for the bug to
  hide* — commit must show a test that fails on the buggy code and passes after the
  agent's fix. First taste of the course's core discipline: **you don't chase bugs, you
  shrink the ground they can stand on.**

---

### Arc 4 — **The Little Harmonic Labyrinth** *(recursion · the stack · task decomposition & subagents)*
- **Setting:** A carnival island whose funhouse contains a story-within-a-story: enter a
  painted door and the art style itself changes (thicker outlines, shifted palette — a
  visual "push"); every door deeper pushes again. Somewhere a calliope plays a melody
  that contains a smaller copy of itself. Popcorn stalls. A goblin who narrates your
  entrance into each level and *audibly panics* about whether you'll ever pop back out.
- **Hofstadter concept:** Recursion; push, pop, and stack; recursive transition
  networks; stories in stories, keys in kings in dreams.
- **CS concept:** The call stack, base cases, recursive data (trees), and stack
  overflow as "a story that never resolves."
- **Claude Code skill:** Decomposition. Breaking a big ask into a plan; using Claude's
  planning mode / task lists; delegating self-contained subtasks to subagents and
  *knowing what each one is allowed to touch*. The learner's first taste of being an
  orchestrator rather than a typist.
- **Hands-on quest:** *"Popcorn Trail."* Implement a recursive dungeon generator (rooms
  contain sub-dungeons; depth-limited) for the adventure engine — but the rule of the
  quest is the learner may only issue *plan-level* prompts; every leaf task must be
  delegated. Also: write `stack_trace.md` explaining, in the goblin's voice, one real
  stack trace the work produced.
- **Boss: The Djinn of Infinite Wishes** — offers to grant a wish, but the wish is
  granted by a smaller djinn, who defers to a smaller djinn... The learner defeats it by
  writing the base case: a recursive function with a *proof of termination* in its
  docstring and a test that asserts maximum recursion depth. If the learner's first
  attempt blows the stack, the crash is canonized (§3, failure-as-content): the goblin
  frames the traceback and hangs it in the funhouse.

---

### Arc 5 — **The Foundry of BlooP and FlooP** *(bounded loops · halting · CI, budgets, and safe automation)*
- **Setting:** A volcanic forge-island run by two blacksmith siblings: **Bloop**, who
  only accepts commissions with a stated maximum number of hammer-blows, and **Floop**,
  whose masterpieces are transcendent but who has, several times, *never stopped
  hammering*. Between the forges, a bell tower that rings a hammer-count for every
  active commission. Sparks fall like cellular automata.
- **Hofstadter concept:** BlooP (primitive recursive, guaranteed to halt) vs. FlooP
  (unbounded, Turing-complete, and undecidable); the halting problem as the price of
  full power.
- **CS concept:** Loops and termination, computational budgets, the halting problem,
  timeouts, idempotency — why every serious pipeline bounds its work.
- **Claude Code skill:** Safe automation. Setting up CI for the repo (GitHub Actions
  with test timeouts); giving the agent bounded instructions ("try at most 3
  approaches, then report"); understanding permission modes and why "just let it run
  forever with full access" is Floop's forge burning down. Introduces hooks as
  guardrails (a pre-commit hook that runs the fast tests).
- **Hands-on quest:** *"The Commission."* Stand up CI on the repo: workflow file,
  per-test timeout, a pre-commit hook, and a deliberately Floopish script the learner
  must convert to BlooP (add bounds, make it idempotent, prove it by running it twice).
- **Boss: Floop's Unfinished Masterpiece** — a half-forged clockwork crane that, when
  activated, begins an unbounded polishing loop. The learner cannot know if it will
  halt (the game is honest about this: the crane's loop condition is genuinely opaque).
  The winning move is *not* analysis — it's wrapping: run it under a timeout, capture
  partial output, and ship the bounded version. Commit must show the wrapper and a CI
  run that finishes. **Lesson:** when you can't decide halting, you impose it.

---

### Arc 6 — **The Archive of Numbered Names** *(Gödel numbering · code-as-data · generation & config)*
- **Setting:** A paper city — a library-island where every citizen *is* a book, and each
  book's spine bears a number that fully encodes its contents. The card catalog is a
  city map; the city map is a card in the catalog. Scribes with brass pantographs copy
  citizens into new editions. Autumn light through rice-paper walls.
- **Hofstadter concept:** Gödel numbering — statements *about* the system encoded as
  objects *inside* the system. TNT beginning to talk about TNT.
- **CS concept:** Code is data: ASTs, serialization, configuration languages, diffs as
  first-class objects. Programs that read, write, and transform programs.
- **Claude Code skill:** Generation and steering-by-file. Writing a `CLAUDE.md` for the
  learner's repo (statements about the system, stored inside the system — the arc's
  concept made flesh); having Claude write codegen scripts; treating diffs and configs
  as reviewable artifacts. Slash commands as reusable encoded intents.
- **Hands-on quest:** *"Become a Book."* (1) Write the repo's `CLAUDE.md` with Claude's
  help — conventions, test commands, forbidden zones — and demonstrate in a fresh
  session that behavior actually changed. (2) Build `scribe.py`: a script that reads the
  adventure engine's room definitions (YAML) and *generates* Python — then have Claude
  extend the YAML schema and regenerate. The learner watches an edit at the data level
  ripple correctly into the code level.
- **Boss: The Censor of the Catalog** — a bureaucrat-spirit who deletes any book that
  describes itself. Defeat by committing a file that survives its rule legitimately:
  a config that describes the generator that generated it, with a round-trip test
  proving `generate(parse(x)) == x`. The Censor, confronted with a fixed point it
  cannot delete without deleting the catalog itself, resigns and opens a tea shop.

---

### Arc 7 — **The Shrine of the Quiet Copy** *(quines & self-reference · metaprogramming · extending Claude Code itself)*
- **Setting:** A mountain shrine reached by a staircase that, seen from the torii gate
  at the top, is the same staircase — an Ascending-and-Descending homage rendered as
  weathered cedar. In the shrine's mirror-pool, your reflection moves a half-second
  *before* you. The shrine keeper speaks only in sentences that quote themselves.
- **Hofstadter concept:** Self-reference and self-replication; the Quine construction
  ("preceded by itself in quotes"); use vs. mention.
- **CS concept:** Quines, templates and macros, bootstrapping — programs whose subject
  matter is themselves.
- **Claude Code skill:** **The turn of the whole course.** The learner extends their
  own tool: writing a custom skill / slash command for Claude Code, and a hook that
  changes agent behavior. Until now the learner used the instrument; now they *luthier*
  it. (Careful sequencing: arcs 5–6 taught guardrails and configs first, so this power
  arrives pre-disciplined.)
- **Hands-on quest:** *"The Quiet Copy."* Two offerings at the shrine: (1) a genuine
  quine in Python, written *by the learner with the agent as advisor only* — the game
  verifies `python3 quine.py | diff quine.py -` is empty; (2) a personal skill file —
  e.g. `/koan-review`, a command that reviews a diff in the Tortoise's voice using the
  learner's accumulated koans (§3) — installed and demonstrated on a real diff.
- **Boss: Your Own Reflection**, who climbs out of the mirror-pool and pair-programs
  *against* you — it has your command history and predicts your next prompt. You cannot
  out-type it; you defeat it by doing the one thing it cannot predict from history:
  changing the system that generates your behavior. Ship a hook that alters your
  workflow (e.g., auto-runs tests on every edit), and the reflection desynchronizes,
  smiles, bows, and returns to the pool. **The strange loop is now armed.**

---

### Arc 8 — **Aunt Hillary's Island** *(emergence · levels of description · multi-agent orchestration)*
- **Setting:** An island that is one enormous, gentle hill — which is an anthill —
  which is a person. Aunt Hillary "speaks" through weather: ant-trails redraw
  themselves into calligraphy on the hillside. Her friend, a melancholy anteater, is
  her *doctor* (he prunes pathological trails). Wind through grass rendered as
  flow-fields. The learner never meets a single ant who understands anything.
- **Hofstadter concept:** The Ant Fugue — consciousness as emergence; signals, symbols,
  and levels; holism vs. reductionism resolved by *choosing the right level of
  description*.
- **CS concept:** Distributed systems and emergence: no component holds the plan;
  behavior lives in protocols. Message passing, eventual consistency (gently),
  swarm/stigmergic coordination.
- **Claude Code skill:** Multi-agent orchestration: running parallel subagents with
  disjoint file ownership, merging their work, resolving conflicts; agent-to-agent
  review (one agent writes, a differently-prompted agent critiques). The learner
  becomes the anteater: they don't do the work, they *shape the trails* — prompts,
  ownership boundaries, and review gates.
- **Hands-on quest:** *"The Fugue in Four Hands."* A four-voice refactor of the
  adventure engine (engine core, content, tests, docs) executed by parallel agents,
  each with an ownership boundary declared up front in `VOICES.md`; the learner
  conducts, merges, and must produce one honest paragraph on what a subagent got wrong
  and how the review gate caught it.
- **Boss: The Trail Tangle** — a storm scrambles the hillside; Aunt Hillary becomes
  incoherent (the game injects merge conflicts and one subtly wrong "confident"
  subagent result). The learner triages at the right level: not re-reading every line
  (ant level), not accepting the summary (weather level), but checking the *receipts* —
  tests, diffs, ownership violations. Green CI on the merged result restores Aunt
  Hillary, who writes the learner's name in ant-calligraphy on the hill.

---

### Arc 9 — **The Summit That Is the Shore** *(incompleteness · strange loops · trust, limits, and shipping)*
- **Setting:** The ninth island is a spiral mountain. Climbing it, the learner passes
  scenes from all eight previous islands *painted on the rock* — then realizes the
  paintings are windows — then crests the summit and finds themselves stepping onto the
  beach of the Village of MU, seen anew. The Tortoise is waiting where they first met.
  Golden-hour light. The calliope theme from arc 4 returns in full counterpoint with
  every arc's leitmotif.
- **Hofstadter concept:** Gödel's incompleteness theorems; tangled hierarchies; the
  self that comes into being by perceiving itself. No sufficiently powerful consistent
  system proves all its own truths — and that is not a tragedy but the engine of
  growth.
- **CS concept:** Limits of verification: tests can't prove their own adequacy;
  benchmarks saturate; specifications are always partial. Therefore: defense in depth,
  outside review, receipts over vibes, and human judgment as the outermost loop.
- **Claude Code skill:** The whole kit, aimed outward. Scoping a real project;
  maintaining the strange loop responsibly (the learner's hooks, skills, and CLAUDE.md
  now form a personal toolchain that improves with use); knowing what *not* to
  automate; writing an honest README.
- **Hands-on quest:** *"The Gift."* Build and ship something real and small — the
  learner's own idea, or a default: a CLI tool that generates a personalized "Arc 1"
  for the *next* learner from their own git history and koan collection. It must have
  tests, CI, a README with honest limitations ("Known incompletenesses"), and a tagged
  v0.1.0 release.
- **Boss: The Author.** A figure sketching the world in an open notebook — who turns
  out to be drawing *from observation*, not creation: the notebook's latest page is the
  learner's actual git log, rendered as storyboard. The final challenge is a dialogue,
  Achilles-and-Tortoise style, in which the learner's own Claude instance asks them
  three questions no test can answer: *What did you build that you can't fully verify?
  What do you trust it anyway, and why? What will you teach it next?* The answers are
  committed as `DIALOGUE.md` — the learner's own GEB dialogue, the last collectible,
  and the first page of whatever they do after the game. Credits roll over the beach;
  the loop is open at the top.

---

## 3. Game Mechanics

**Progression = verified artifacts, never self-report.** The game's XP system is a
thin, honest layer over reality:

- **Derivations (XP):** granted only for mechanically checkable events — a commit
  landing, a test suite passing in CI, a coverage threshold, a quine diffing empty,
  a hook firing in a session transcript. The game watches the repo (git hooks +
  session logs via the Agent SDK), not the learner's claims. If you can't grant the XP
  from a receipt, the quest is redesigned until you can. (Vibe coding with receipts —
  the pedagogy *is* the anti-slop mechanism.)
- **Ranks** are named for the book's levels: *Symbol → Rule → Theorem → System →
  Meta* — you rank up not by grinding but by demonstrating the next level of
  description (e.g., Theorem→System requires shipping the arc-5 CI work).

**The Tortoise — your companion, voiced by your own Claude.** The mentor character is
not scripted dialogue with a Claude skin; it *is* the learner's Claude instance, given
a persona file (a system-prompt layer the game maintains) that carries: the Tortoise's
voice (patient, sly, allergic to unearned certainty), the learner's current arc, their
koan collection, and their recent failure log. Consequences, all delightful:

- The mentor genuinely knows your code, because it's the same agent that helped write it.
- The mentor improves as *you* improve, because arc 6–7 have you editing the very
  persona and skills it runs on. The companion is the strange loop's handrail.
- In-fiction hook: the Tortoise claims to be "a very slow program that has been running
  for a very long time." It never breaks kayfabe, but it never lies about being an AI
  either — GEB would demand nothing less.

**Koans — the collectibles.** Each arc hides 3–5 koans: short, original aphorisms in
the GEB spirit (written fresh for this game — see §4 on licensing), earned at moments
of genuine insight, e.g. *"The bug you cannot find lives in the file you did not
read."* / *"A test is a wish the machine is forced to keep."* / *"Bound the loop, or
the loop bounds you."* Koans are functional, not just cosmetic: they're the corpus your
arc-7 `/koan-review` skill quotes, so collecting wisdom literally upgrades your
tooling. Complete an arc's set and the Tortoise recites the arc's *capstone koan* —
which is also a mnemonic for the arc's CS concept.

**Failure-as-content.** Every real failure becomes story, automatically:

- **The Bestiary of Broken Things:** each distinct failure class the learner actually
  hits (stack overflow, merge conflict, hallucinated API, flaky test, permission
  denial) is minted as an illustrated creature card — name, habitat, *observed
  behavior* (the real traceback, framed like a specimen label), and the banishment
  ritual (the fix, cited to the learner's own commit). Duplicated failures level the
  creature up rather than shaming the learner.
- Certain bosses (arcs 4, 5, 8) *require* a failure to complete honestly; if the
  learner somehow sails through, the Tortoise gently manufactures a controlled one
  ("run it once more, but on the file I just... adjusted").
- The bestiary is exportable as a genuinely useful personal debugging journal — the
  game's souvenirs are engineering assets.

**Session rhythm.** Arcs are built of 20–40 minute "scenes" (one quest beat each) so
the loop respects real life; every scene ends at a commit boundary, and re-entering the
game replays a 15-second painted "previously on" generated from the learner's own git
log messages.

---

## 4. Art Direction — 2026 Classic-Anime Visual Language

**The look:** hand-painted cel aesthetics reimagined with 2026 tooling — 3–4 tone cel
shading with painterly gouache backgrounds, visible paper grain, deliberate
"cel-jitter" (backgrounds at 24fps, characters on 2s), chromatic warmth of 90s TV
telecine (soft bloom, slight gate weave) but at modern resolution. Wide painterly
establishing shots; expressive limited animation for dialogue; lavish full animation
reserved for boss climaxes and koan reveals — scarcity as emphasis, exactly as the
classics did it. This is a *style homage* (cel look, pastoral warmth, 90s-TV framing),
and explicitly **not** an imitation of any studio's protected characters, logos,
creatures, or signature designs — no soot sprites, no forest spirits, no recognizable
silhouettes. Original character designs throughout: the Tortoise's shell is an
Escher-style woodcut tessellation (Escher-*inspired* geometry, not reproductions);
Achilles is customizable and deliberately genre-neutral.

**Two structural motifs run under everything:**

- **Escher tessellation as world-grammar.** Transitions between scenes morph via
  figure-ground tessellation (birds→fish→birds); UI panels tile the screen the way his
  plane-fillings do; the arc-7 staircase and arc-9 spiral are original architecture in
  the impossible-object tradition. (Escher's actual works are rights-managed — see
  licensing note — so all tessellations are original constructions in the *mathematical
  tradition* he worked in, which is not ownable.)
- **Bach counterpoint as motion design.** Movement in multi-element scenes follows
  contrapuntal rules: when two characters walk, their bob-cycles are voices in
  invertible counterpoint; the arc-8 ant trails animate as a four-voice fugue (subject,
  answer, countersubject, stretto at the boss). Each arc has a leitmotif; arc 9 states
  them simultaneously. Score: original compositions in Baroque forms (canon, fugue,
  chaconne) — Bach's music is public domain, but any specific *recording* is not, so
  the score is newly recorded/synthesized.

**Per-arc palette & motif sheet:**

| Arc | Palette | Signature motif |
|---|---|---|
| 1 MU Village | Rain-washed indigo, rice-paddy green, vermilion door-glyphs | Monospace rain; terraces as production rules |
| 2 Isomorphic Bridge | Mist grey, lantern amber, koi orange | Paired scripts; koi/bird mirror tessellation |
| 3 Figure & Ground Gallery | Ink black, paper white, one gallery-red accent | Negative-space reveals; shadows with detail |
| 4 Harmonic Labyrinth | Carnival teal, popcorn gold; palette shifts per stack level | Style-push on recursion depth; nested doors |
| 5 BlooP/FlooP Foundry | Forge orange, iron blue-black, spark white | Hammer-count bell tower; CA spark showers |
| 6 Archive of Numbered Names | Autumn ochre, rice-paper cream, brass | Spine-numbers; pantograph scribes; city-as-catalog |
| 7 Shrine of the Quiet Copy | Cedar brown, moss green, mirror silver-blue | Self-similar staircase; early reflection |
| 8 Aunt Hillary's Island | Wind-grass green, storm violet, trail umber | Flow-field grass; ant-calligraphy weather |
| 9 Summit/Shore | Golden hour full-spectrum; all palettes recapitulated | Spiral of windows; the beach from above |

**IP & licensing ledger (what's safe, what needs original work, what would need a license):**

- **Safe as-is:** GEB's *ideas* (strange loops, formal systems, incompleteness — ideas
  aren't copyrightable); Gödel/Escher/Bach as historical figures; Bach's compositions
  (public domain; make new recordings); the mathematics of tessellation and impossible
  objects; the Achilles-and-Tortoise device itself (it predates Hofstadter — Lewis
  Carroll's 1895 "What the Tortoise Said to Achilles" is public domain, and Zeno is
  quite thoroughly out of copyright).
- **Needs original writing (our plan):** all dialogue, all koans, all character
  personalities, the MU-golem scene, every "dialogue-shaped" text. We are writing *in
  the genre Hofstadter revived*, not quoting him. Character names: use
  "Achilles"/"Tortoise" via the Carroll/Zeno lineage; do **not** import Hofstadter's
  original characters (e.g., the Crab and Sloth as *he* characterized them) — our
  Mirror Crab is an independent creation; keep it visibly so.
- **Would need licensing (avoid in MVP):** quoting GEB's text (any dialogue excerpts,
  the specific prose of the MU-puzzle chapter — note: the *puzzle's rules* as facts are
  fine, his *presentation* is not); reproducing actual Escher works (rights-managed by
  the M.C. Escher Company — all our tessellations are original); any existing anime
  studio's characters, music, or trade dress; specific Bach *recordings*. Marketing
  should say "inspired by the ideas explored in Hofstadter's *Gödel, Escher, Bach*"
  (nominative, factual) and never imply endorsement.

---

## 5. Build Plan — MVP as a Web App

**Stack:** Next.js (app router) + `xterm.js` embedded terminal → server-side PTY into a
per-learner sandbox (container) with git + Claude Code installed → **Claude Agent SDK**
powering (a) the Tortoise persona layer, (b) quest verification agents that inspect the
repo/CI for receipts, and (c) the "previously on" recap generator. Story scenes as a
layered-illustration format (static painted keyframes + CSS/WebGL parallax and cel-
jitter shaders — *animated enough*, without a per-frame animation budget). Postgres for
progression state; every XP grant stores its receipt (commit SHA, CI run id, transcript
span) — auditable by design.

**Milestone 1 — "The Village" (6–8 weeks):** One complete arc (Arc 1) end-to-end:
sandbox provisioning, embedded terminal, real Claude Code session, the MU quest with
mechanical verification (invariant test + `PROOF.md` detection), Tortoise persona v1,
koans, first bestiary card, placeholder art in final palettes. Success gate: 10
external testers derive/refute MU and *feel* the golem bow.

**Milestone 2 — "The Loop Armed" (8–10 weeks):** Arcs 2–7. CI integration (arc 5),
CLAUDE.md and skill-authoring flows (arcs 6–7) working inside the sandbox — this is the
riskiest engineering (the learner's strange loop must actually close: their skill files
must really change their agent's behavior). Bestiary automation from real tracebacks;
koan-powered `/koan-review`; first full art pass on three arcs; original score sketches
for leitmotifs.

**Milestone 3 — "The Summit" (8 weeks):** Arcs 8–9: multi-agent orchestration sandbox
(parallel subagents with ownership boundaries), the merge-storm boss, the Gift capstone
with real release tagging, the closing dialogue system, recapitulation art and score,
export of bestiary/koans/toolchain so the learner leaves with working assets. Then:
open beta, and — in the only fitting final feature — the capstone tools of early
learners seed side-quests for later ones. The game, too, becomes a strange loop.

---

*Capstone koan, Arc 9: "You climbed the mountain to find the shore. The tool you
sharpened was the hand that held it."*

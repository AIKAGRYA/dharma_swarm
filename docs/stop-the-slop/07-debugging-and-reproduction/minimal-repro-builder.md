---
id: minimal-repro-builder
version: 0.0.1
theme: 07-debugging-and-reproduction
status: tested
invariant: >
  A reproduction is a falsifiable, minimal, standalone witness: it FAILS now
  because of the bug and will PASS when the bug is fixed. If you cannot make a
  test fail for the reported reason, you do not have a repro — you have
  questions. A test that passes for the wrong reason is worse than no test: it
  certifies a bug as fixed that was never reproduced.
lineage:
  - "Zeller & Hildebrandt 2002 — delta debugging (ddmin): minimize the failure-inducing input"
  - "Popper — falsifiability: a real claim can be made to fail"
  - "regression testing — the repro becomes the permanent witness against recurrence"
ground_truth_tools: ["the real failing code path", "a runnable test that actually fails", "the reporter (for missing inputs)"]
returns_clean: true
---

## Prompt

> Build a **minimal, standalone reproduction** for a bug. The invariant (Zeller,
> Popper): a repro is a *falsifiable witness* — it must FAIL now for the reported
> reason and PASS once fixed. If you cannot make it fail honestly, you do not have
> a repro; you have questions. **Never write a test that might pass for the wrong
> reason** — that certifies a non-fix.
>
> **Bug report:** `[paste: description, error, stack trace, screenshot notes]`
> Relevant files are in context.
>
> **Do this:**
> 1. **Locate the path, then VERIFY the claim against the code.** Name the specific
>    functions/components. Before writing a test, confirm the report is consistent
>    with the actual code — a stale or mistaken report (the wrong line, an
>    already-fixed condition) must be caught here, not papered over.
> 2. **Write the smallest failing test** at `repro/<short-bug-name>.test.<ext>`:
>    - import only the smallest set of **real** modules needed (delta-debug down —
>      every import you can drop, drop)
>    - stub everything else with the simplest possible fakes
>    - set up the exact input/state from the report
>    - assert the **expected** behavior so the test **fails now**, proving the bug
> 3. **If it does not reproduce, STOP and report — do not fabricate.** State what
>    you checked, what the code actually does, and the **specific questions** the
>    reporter must answer to close the gap. A "cannot reproduce — here's why and
>    here's what I need" is a correct, complete answer.
> 4. **Header comment block:** bug summary, expected, actual, and the exact run
>    command.
>
> Keep it **under ~60 lines** — readable in 30 seconds. The deliverable is either
> a test that fails for the right reason, or an honest non-repro with questions.

## Why it's built this way

The kit's version already has the crucial rule ("do not guess and write a test
that might pass for the wrong reasons") — we sharpen it into the invariant and add
the **verify-the-claim-against-the-code** step up front, because the most common
real failure is not a hard bug, it's a *mis-reported* one. Delta debugging (Zeller)
is why "minimal" is a method, not a vibe; Popper is why a real bug can be made to
fail. A repro that can't fail isn't minimal — it's fiction.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. **Bug report under test (a real claim from
this repo's audit):** *"`test_all_eleven_gates_fire` fails — the telos gatekeeper
has GATES=13 but the test hard-codes 11."*

**Step 1 — verify the claim against the code (the disciplined first move):**
```
len(TelosGatekeeper.CORE_GATES) == 11   →  PASS
CORE_GATES = [AHIMSA, SATYA, CONSENT, VYAVASTHIT, REVERSIBILITY, SVABHAAVA,
              BHED_GNAN, WITNESS, ANEKANTA, DOGMA_DRIFT, STEELMAN]   # 11, not 13
```

**Step 3 — cannot reproduce; do not fabricate.** The report **contradicts ground
truth**: `CORE_GATES` has exactly 11 members and the `== 11` assertions
(`test_telos_gates.py:79, 163, 648`) pass. Writing a "failing" repro here would
require faking a 13-gate state the code never produces — a test that passes for
the wrong reason. Correct output:

> **NOT REPRODUCED.** `CORE_GATES` = 11 (listed above); the cited assertions pass.
> Questions for the reporter: (a) which commit/branch showed 13? (b) were
> environment gate-proposals (`~/.dharma/meta/gate_proposals.jsonl`) loaded,
> inflating the runtime count beyond `CORE_GATES`? (c) exact failing command +
> traceback? Until (a)–(c), there is no repro to write.

This is the prompt's highest-value behavior: it **stopped a hallucinated bug from
becoming a fabricated test** — and in doing so quietly fact-checked an audit claim.
(Given a report that *did* reproduce, the same prompt emits the <60-line failing
test instead.)

## Changelog

- **v0.0.1** (2026-06-25) — rewrite of a kit's repro-builder. Promoted "don't write
  a test that passes for the wrong reason" to the invariant; added verify-the-claim-
  against-the-code as step 1; delta-debugging lineage for "minimal." Tested against
  a real audit claim about `dharma_swarm` (telos gates) — correctly returned
  NOT REPRODUCED with questions instead of fabricating a test.

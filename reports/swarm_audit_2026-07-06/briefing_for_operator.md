# What the big audit actually found — plain-English briefing

You ran a 67-agent audit and said you still didn't know what it found. An independent
review has now re-checked its claims by hand. Here is the whole picture.

**First: the audit is trustworthy.** Every major claim we re-tested held up. The codebase
is not rotting. The tests are real, the safety gates mostly work, and the security basics
are in better shape than most projects. The audit's core diagnosis — the same idea keeps getting built in several
places and nobody reconciles the copies — is correct, and its fix list is sound.

## What's actually wrong — three things

**1. The project now builds only plumbing.** Your own rules say every work stream must
serve one of three goals: internal infrastructure, revenue, or research. All five active
work streams serve infrastructure — and revenue and research have had *zero* coverage for
the entire life of the current portfolio. No money has ever entered or
left through the system, and the instrument built to measure "awareness" (the research
centerpiece) is wired to nothing; production uses look-alike numbers instead. The system
honestly displays this gap in its own dashboards — but no dated decision about it was ever
recorded. The missing decision, not the missing work, is the defect.

**2. Your working environment lies to you.** The copy of the project you and your agents
actually work in is 397 versions behind the real main branch, and its instruction file
describes 11 active work streams when the truth is 5 — ten of the eleven are finished or
gone. Every session that starts there is briefed on a dead world. Separately: your rules cap parallel working copies at 8;
there are 60, and the rule that says "enforced" has no enforcement code behind it.

**3. One autonomous engine can act without its safety checks.** A large module nobody
owns (the "director") can spawn AI agents that run raw commands with no safety gate, and
the tool that reports "all bypasses closed" is blind to this kind of bypass. It is
currently switched off — no activity since April — so nothing is burning, but it is one
command away from live. Related: in one *live* engine, if the safety gate itself crashes,
the action is allowed through anyway. That one is a two-line fix.

## Do these three things, in this order

1. **Decide about revenue and research.** Open one work stream for each, or write a dated
   note deferring them and why.
2. **Fix your cockpit.** Keep one always-current copy of main on the machine; update or
   retire the stale primary checkout.
3. **Approve the two small safety fixes**: crashed gate = action blocked (not allowed),
   and either own or disable the director's ungated path.

Everything else — evidence, file references, and ten questions awaiting your answers — is
in the companion report, `gap_check_fable.md`. One trivial broken-import fix is already
included in this PR; all other changes await your say-so.

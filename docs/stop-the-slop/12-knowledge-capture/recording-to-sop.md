---
id: recording-to-sop
version: 0.0.1
theme: 12-knowledge-capture
status: drafted
invariant: >
  An SOP must be FAITHFUL to the observed actions — the minimal reproducible path,
  nothing invented. Every step is one real action with the exact value used;
  hesitations/backtracks become "watch out for" warnings, not silent omissions;
  uncertainty is flagged, never smoothed over. A fabricated step in an SOP is the
  knowledge-capture form of slop: the next person follows it and fails.
lineage:
  - "Gilbreth (motion study) — find and document the one minimal effective path"
  - "Gawande (Checklist Manifesto) — verification points + escalation, not prose"
  - "Polanyi — tacit knowledge: the goal is to externalize what the doer knows implicitly"
ground_truth_tools: ["the actual recording (the observed actions are the only source)", "exact on-screen values/labels"]
returns_clean: true
---

> **Scope note (honest):** this is an *adjacent* prompt — knowledge capture / process
> documentation, not code analysis. It's in the library because turning a screen
> recording into a followable SOP is a real builder pain, and the **faithfulness
> discipline** is identical to the rest of Pramāṇa Probe: don't invent what you
> didn't observe.

## Prompt

> I'm uploading a screen recording of me doing a task. Convert it into a standard
> operating procedure (SOP) someone else could follow **without watching the
> video**. The invariant (Gilbreth, Gawande): capture the **minimal reproducible
> path** faithfully — every step is one real action with the exact value used, and
> you **never invent a step that wasn't performed**.
>
> Produce:
> - **Title** (inferred) · **Goal** (1 sentence: what + why) · **Prerequisites**
>   (tools/logins/files/permissions) · **Estimated time** (from what you observed).
> - **Steps:** numbered, imperative, **one action each** ("Click X", "Paste Y into
>   Z"). Include the **exact** text typed or option selected. Group into phases with
>   subheadings if the workflow has them.
> - **Checks:** after key steps, a `Verify:` line — what success looks like ("the
>   row shows status: Active").
> - **Common mistakes:** every moment you **hesitated, backtracked, or fixed an
>   error** in the recording → "watch out for" warning. Do not silently omit them.
> - **When to escalate:** failure modes the reader can't fix alone + who to contact.
>
> Ignore mouse wiggle, tab-switching, and detours that didn't contribute. Focus on
> the minimum path. **If a step's exact value or intent is unclear in the
> recording, mark it `[UNCLEAR — confirm: …]` — do not guess a plausible value.**

## Why it's built this way

The kit's version is strong (minimal path, verifies, capture-the-backtracks). The
one rule we harden: **flag-don't-guess** on any unclear value. An SOP's whole job
is to be followable by someone who *wasn't there*; a guessed field value or
invented step is the exact failure that makes SOPs untrusted. Gawande's verifies
and escalation turn it from prose into an instrument; Polanyi names the real task —
externalizing the doer's tacit knowledge.

## Demonstration run — honest non-applicability

There is **no screen recording** in this repo to convert, and the prompt's only
valid input *is* the observed recording. Per our own discipline, we do **not**
fabricate a demo SOP from an imagined video — that would be precisely the
knowledge-capture slop this prompt exists to prevent. Status: `drafted` (not
`tested`) until run against a real recording.

What we *can* assert without a video: the load-bearing rule (`[UNCLEAR — confirm]`
over guessing) is the same faithfulness discipline verified across the rest of the
library; this prompt inherits it.

## Changelog

- **v0.0.1** (2026-06-25) — adjacent (knowledge-capture) prompt. Rewrote a kit's
  recording→SOP prompt with the flag-don't-guess rule on unclear values and
  Gilbreth/Gawande/Polanyi lineage. Marked `drafted` (no recording artifact here to
  test against — honestly noted rather than faked).

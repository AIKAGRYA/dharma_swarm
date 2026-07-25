---
id: error-handling-rules
version: 0.0.1
theme: 06-error-handling
status: tested
invariant: >
  An error is information; swallowing it destroys information. Every failure path
  must either be HANDLED (with a recovery the reader can name) or PROPAGATED with
  context — never silently dropped, never stringly-typed, never shown to a user
  without being logged with enough context to debug. The banned list must be the
  anti-patterns ACTUALLY present in the codebase, measured — not a generic
  boilerplate.
lineage:
  - "Goodenough 1975 — exception handling as a language-level contract"
  - "Parnas — fail fast; a module must not proceed past a violated assumption"
  - "Pike/Go — errors are values, handled explicitly, not magic control flow"
  - "ML/Haskell — Result/Either: failure is in the type, not a hidden side channel"
ground_truth_tools: ["grep/AST for swallow patterns in THIS repo", "the ratchet/lint counters", "the real logging + user-surface stack"]
returns_clean: true
---

## Prompt

> Produce a ready-to-paste error-handling rules block (`.cursorrules`,
> `CLAUDE.md`, `AGENTS.md`, or a lint config) that a code reviewer can enforce
> mechanically. The invariant you defend (Goodenough, Parnas): an error is
> information — every failure path is HANDLED with a named recovery or PROPAGATED
> with context; never silently dropped, never a raw string, never surfaced to a
> user without being logged.
>
> **Ground the bans in reality (the generation analogue of route-to-ground-truth):**
> before writing the block, **grep/AST this codebase for the swallow patterns that
> actually occur** (`except: pass`, `catch {}`, `.catch(() => {})`, throwing
> strings, generic "Something went wrong"). Ban what is *present*, with a count —
> not a generic checklist. A rule against an anti-pattern you don't have is fluff.
>
> **My context:**
> - Stack: `[e.g. TypeScript, Next.js App Router, Postgres/Drizzle, tRPC]`
> - Error style (pick one): `throw + catch at boundaries` | `Result/Either` |
>   `{ data, error } tuples` | `throw internally, tagged unions at API edges`
> - Logging: `[console.error | Sentry | pino | structlog]`
> - User surface: `[toast | inline form errors | error boundary]`
>
> **The block must (keep it under ~40 lines, every line reviewer-enforceable):**
> 1. State the one chosen pattern with a **right-way / wrong-way code pair**.
> 2. Define **log vs surface vs both** (log always with context; surface a safe
>    message; never surface raw internals).
> 3. **Ban the measured anti-patterns by name**, each enforceable: empty/silent
>    catch, swallowing without a witness, generic user message *without* logging the
>    real error, throwing strings/objects instead of `Error`.
> 4. Define **required context on every error**: operation name, the IDs that scope
>    it (user/request/trace), and the original cause (`cause:` / `from exc`) —
>    never drop the stack.
> 5. Specify how **async**, **network/timeout**, and **validation** errors differ:
>    validation → structured field errors to the user, no log spam; network →
>    bounded retry then surface; unexpected → log + generic surface + alert.
>
> **Return clean:** if the codebase already enforces this (zero silent swallows,
> typed errors, contextual logging), say so and produce a *codifying* block that
> locks the status quo rather than inventing new rules.
>
> Output only the block, ready to paste. No preamble.

## Why it's built this way

The kit's version is good but generic — it bans anti-patterns whether or not you
have them. The upgrade is **measure first**: a rule earns its place by pointing at
a real count of the thing it forbids, which is the generation-task form of "route
to ground truth." Lineage: Goodenough made exceptions a contract; Parnas's fail-
fast forbids proceeding past a violated assumption; Go's "errors are values" and
ML's `Result` put failure in the type instead of a hidden channel — that's *why*
swallowing and stringly-typed errors are banned, not just "best practice."

## Demonstration run

**Target:** `dharma_swarm/` (Python), 2026-06-25. The prompt targets `.cursorrules`
for TS stacks; the load-bearing step — **measure the real anti-patterns** — runs
on any codebase, so we ground it here and emit the Python-flavored block.

- **Measured reality:** `silent_exception_swallows = 244` (the repo's own ratchet
  counter: `except: pass` / `except Exception: pass` with no witness), plus
  **2,275** `except Exception` sites and 5 bare `except:`.
- **Nuance the discipline forces (don't over-ban):** not all 244 are bugs —
  `cli.py:271 except KeyboardInterrupt: pass` and `diagnostics.py:70 except
  json.JSONDecodeError: pass` are *narrow and intentional*. The rule must ban the
  **broad, witness-less** swallow (`except Exception: pass`), not the narrow
  deliberate one. A generic "no bare except" rule would mislabel the safe cases.
- **Emitted block (Python instantiation), grounded in that count:**
  > - Never `except Exception: pass`. Catch the *narrowest* type; if you must catch
  >   broad, **log with context and re-raise or return a typed error** (244 current
  >   violations — ratchet them down, never up).
  > - Every `except` logs `operation`, the scoping IDs, and `exc` (use
  >   `raise … from exc`; never drop `__cause__`).
  > - No stringly-typed raises — raise an `Exception` subclass.
  > - Validation → structured error to caller; unexpected → log + generic surface.

This is the discipline in one move: the ban is **data-driven** (244, measured),
**nuanced** (narrow swallows spared), and **ratchetable** (wire it to the existing
counter so it can only improve) — not a generic checklist.

## Changelog

- **v0.0.1** (2026-06-25) — rewrite of a kit's `.cursorrules` error-handling prompt.
  Added measure-the-real-anti-patterns-first (count what you ban), the narrow-vs-
  broad swallow nuance, required-error-context, and return-clean/codify-the-status-
  quo. Tested against `dharma_swarm/` (grounded the bans in its measured 244 silent
  swallows + 2,275 broad catches; spared the narrow intentional ones).

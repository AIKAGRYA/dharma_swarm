---
id: interface-replaceability-audit
version: 0.0.1
theme: 02-module-topology
status: tested
invariant: >
  A good interface lets you replace the implementation behind it without touching a
  single caller (Steenberg). Replaceability is the real test of a boundary: if
  callers depend on concrete types, internal fields, or side effects instead of a
  narrow declared contract, the module is welded in, not plugged in. Depend on
  abstractions, not concretions (DIP) — measured by what callers actually import.
lineage:
  - "Eskil Steenberg — design replaceable interfaces; the implementation is disposable"
  - "Parnas 1972 — information hiding; callers see the interface, never the secret"
  - "Martin (DIP) — depend on abstractions; high-level policy must not import low-level detail"
ground_truth_tools: ["import graph: do callers import the interface or the concretion?", "fan-in to concrete vs abstract symbols", "is there a seam (ABC/Protocol/factory) at all?"]
returns_clean: true
---

## Prompt

> Audit **interface replaceability**. The invariant (Steenberg, Parnas, DIP): you
> should be able to swap an implementation without editing any caller. Replaceability
> fails when callers import **concrete classes, internal fields, or rely on side
> effects** instead of a narrow declared contract (ABC / Protocol / interface).
>
> **For each significant subsystem:**
> 1. Is there a **seam** — an abstraction (ABC/Protocol/interface/factory) callers
>    depend on? Or do they import the concrete implementation directly?
> 2. **Measure** it: of the modules importing this subsystem, how many import the
>    *abstraction* vs a *concretion*? High concretion-coupling = welded in.
> 3. Name the **swap test**: "to replace X with X2, how many caller files change?"
>    0–1 = replaceable; many = welded.
> 4. Where it's welded, propose the minimal seam (extract a Protocol; route through a
>    factory) — smallest blast radius first.
>
> **Return clean / credit** subsystems that already have a clean seam — replaceability
> is a *strength* to confirm, not only a gap to find.

## Why it's built this way

Steenberg's framing — "the implementation is disposable, the interface is the asset"
— is the practical form of Parnas + DIP, and it's *measurable* from the import graph:
count abstraction-imports vs concretion-imports. That turns "is this well-designed?"
into "how many files change to swap it?"

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. Tool: import graph + seam check.

- **Provider layer — has a seam (credit):** there's a `ProviderType` enum + a
  factory + a provider base, and `from dharma_swarm import ClaudeCodeProvider…`
  (now lazy). Callers *can* route by `ProviderType` rather than concrete classes →
  **swap test is low** for adding a provider (the whole `provider-routing` track is
  about this). 🟢 mostly replaceable.
- **`models` — welded by fan-in (the risk):** **156** modules import it, largely for
  **concrete** Pydantic types, not an abstraction. Swap test: changing a core model
  is a 156-file event. That's not "wrong" (it's a shared contract) but it's the
  least-replaceable node — its concretions *are* the interface, so it must be treated
  as a frozen contract (versioned changes only).
- **`swarm` (57 fan-out)** — depends on many concretions directly; hard to test in
  isolation = low replaceability of its collaborators. Seam opportunity: inject its
  heaviest dependencies behind Protocols.

**Verdict:** the provider boundary is a model citizen (real seam, low swap cost);
`models` is a frozen contract by virtue of 156 concretion-dependents; `swarm` is the
weld to loosen with injected Protocols.

## Changelog

- **v0.0.1** (2026-06-25) — interface-replaceability audit (Steenberg/Parnas/DIP):
  measure abstraction-vs-concretion imports, the "how many files change to swap it"
  test, credit clean seams. Tested on `dharma_swarm`: provider layer replaceable
  (real seam), `models` welded as a 156-dependent frozen contract, `swarm` the weld
  to loosen.

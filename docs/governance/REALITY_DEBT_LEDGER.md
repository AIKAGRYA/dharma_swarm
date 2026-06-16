# REALITY DEBT LEDGER

Purpose: anti-overclaim firewall. This ledger records high-value claims that
need stronger proof before agents may speak about them as complete truth.

Schema: `claim | current custody | proof missing | owner | next receipt | allowed language`

| claim | current custody | proof missing | owner | next receipt | allowed language |
|---|---|---|---|---|---|
| self-funding / economically alive | AMBER, internal revenue signals only | paid invoice, payment processor event, or signed purchase approval tied to RevenueSpine | RevenueSpine / external payment owner | `revenue_receipt` with payer, amount, artifact, and runtime mission ref | "revenue wedge or signal exists"; not "self-funding" |
| external humans served | AMBER | target list, human permission or outreach, reply, delivered artifact, and service result | external outreach / operator-approved sprint | human approval plus delivery artifact and response receipt | "external-human proof sprint proposed or in progress" |
| R_V or consciousness thesis proven | RED for proof claim, research-only custody | reproducible empirical protocol, peer review, falsification criteria, citations | research docs and foundations | evaluated research packet with source citations and limitations | "research thesis or hypothesis"; not "proven" |
| self-evolution autonomous or metabolic | AMBER | bounded autonomous loop receipts, human gates, rollback evidence, value improvement | Runtime Truth Spine plus governance gates | runtime mission receipt showing bounded loop, result, review, rollback path | "bounded self-improvement loop"; not "autonomous self-evolution" |
| runtime truth fully saturated | AMBER | default-path coverage across command surfaces, no known bypasses, static guard green | Runtime Truth Spine / cutover matrix | command-cutover metric with default-path joined count and bypass classification | "runtime truth saturation is partial and measured" |
| deployed/live system equals audited main | AMBER | deploy provenance, commit SHA, environment, health check, and drift proof | deployment owner / Live Ops | deploy receipt joining runtime SHA to environment health | "this checkout projects live state"; not "main equals deployed" |
| MemoryKernel production first-token orientation | AMBER | production bar pass, burn-in receipts, first-token path proof | MemoryKernel production bar | readiness receipt plus onboard integration proof | "MemoryKernel readiness work exists" |
| Chetana main-owned canon metabolism | RED until main-owned owner exists | main-owned module, owner doc, tests, runtime receipt | TBD, active track required | owner registration plus runtime receipt | "Chetana is a proposed or external concept" |
| Capital Lab / Ginko live trading authority | RED / external-gated | explicit operator/legal authority, exchange credentials scope, dry-run/live split, risk limits | operator and legal/exchange owner | signed live-trading warrant and exchange audit receipt | "research or simulation only" |
| Forge/Hydra runnable or fitness-authoritative | AMBER | fresh command run, environment, inputs, outputs, and fitness validation | forge/hydra owners | run receipt plus artifact hash and verifier result | "Forge/Hydra exists as a candidate surface" |
| market comparator figures verified | AMBER | dated external source URLs, calculation sheet, citation audit | research / market intel owner | sourced comparator packet with retrieval date and formula | "unverified comparator estimate" |

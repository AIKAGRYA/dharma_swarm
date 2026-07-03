# Borrower-Side Verification Layer - Reality Grounding Packet

Date: 2026-07-03
Corpus: `BUCKET_100.md`, `SYNTHESIS.md`, `BUCKET_100.json`, `SYNTHESIS.json`
Repo anchor: `/Users/dhyana/dharma_swarm/dharma_swarm/venture_cell/livelihood_loom/`

## Bottom Line

The idea is real enough to run, but the first implementation should be narrower
than the synthesis language.

Do not start by claiming "verification layer for the powerless" as a broad
platform. Start with one executable receipt:

> Given a loan offer's disclosed cashflows and source clauses, compute the
> jurisdiction-specific true cost, flag unsupported or risky terms, and emit a
> source-linked verification receipt that a borrower, advocate, regulator, or
> app-store reviewer can inspect.

The strongest first wedge remains the true-cost / trap-clause verifier, because
it has an objective oracle: deterministic APR/effective-cost recomputation plus
evidence-span checks for every clause finding.

## Real-World Grounding

### Why this wedge has law-shaped gravity

The U.S. Regulation Z rule says APR is the cost of credit as a yearly rate
relating the value received by the consumer to the timing and amount of payments
made. It can be determined by actuarial or U.S. Rule methods, with Appendix J
providing actuarial equations and instructions. CFPB also defines finance
charge broadly as the dollar cost of consumer credit, including charges payable
directly or indirectly by the consumer and imposed as an incident to credit.

Sources:
- https://www.consumerfinance.gov/rules-policy/regulations/1026/22/
- https://www.consumerfinance.gov/rules-policy/regulations/1026/4/
- https://www.consumerfinance.gov/rules-policy/regulations/1026/j/

This is exactly the kind of domain where a verifier beats a generator. A model
can extract terms; the verifier must recompute cashflows and reject unsupported
claims.

### Why app-store policy creates a cheap public-data path

Google Play requires personal-loan apps to disclose repayment period, maximum
APR, a representative total-cost example, and privacy policy, and does not allow
personal loans requiring repayment in full in 60 days or less.

Apple requires personal-loan apps to clearly disclose loan terms, including max
APR and due date; Apple also says loan apps may not charge max APR above 36%
including costs and fees, and may not require repayment in full in 60 days or
less.

Sources:
- https://support.google.com/googleplay/android-developer/answer/9876821?hl=en
- https://developer.apple.com/app-store/review/guidelines/

This makes the first data loop plausible without a partner: app metadata,
public websites, T&Cs, support pages, screenshots provided with consent, and
synthetic adversarial variants.

### Why emerging-market regulators are an even better fit than U.S.-only APR

RBI's current 2025 Digital Lending Directions explicitly center borrower
protection: concerns include mis-selling, data privacy breaches, unfair conduct,
exorbitant interest, and unethical recovery. The directions require digital
views of matching loan offers to include amount, tenor, APR, monthly repayment
obligation, penal charges, and KFS links, and prohibit dark/deceptive patterns.
They also require KFS disclosures, grievance channels, direct disbursement and
repayment flows, data minimization, and DLA reporting.

Source:
- https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12848&Mode=0

This is a stronger first-country template than U.S. consumer credit alone
because it explicitly names digital lending apps, disclosure, offer comparison,
dark patterns, grievance paths, and app registries.

### Why adverse-action recourse is second, not first

ECOA/Regulation B already requires adverse-action notices with specific reasons,
and CFPB guidance says complex algorithms do not excuse failure to provide
specific explanations. But the regulation still allows reason disclosure without
requiring a minimal borrower-controlled path to approval.

Sources:
- https://www.consumerfinance.gov/rules-policy/regulations/1002/9/
- https://www.consumerfinance.gov/archive/newsroom/cfpb-acts-to-protect-the-public-from-black-box-credit-models-using-complex-algorithms/

This confirms the whitespace, but the first offline oracle is weaker than APR:
without a lender scorecard, counterfactual recourse uses surrogate models.
Useful, but easier to fake.

## Repo Grounding

There is already a real home: `dharma_swarm/venture_cell/livelihood_loom/`.

Relevant existing surfaces:

- `charter.yaml`: already contains human-approved-only external actions,
  sensitive data classes including income/debt/identity/household/case_notes,
  proof contract fields, and shutdown conditions for public sensitive-data leak
  or autonomous external action.
- `ontology.py`: already defines public proof guards and sensitive public fields.
- `evidence.py`: already writes cultivation-cycle receipts and provider gap
  receipts.
- `execution.py`: already runs safe bootstrap, scores public candidates, and
  drafts external actions without sending them.
- `promotion.py`: already creates sponsor-facing artifacts and external acted
  receipt gates.
- `status.py`: already projects readiness without claiming production liveness.

The right code shape is not a new app or new receipt system. It is a small
borrower-verifier capability inside `livelihood_loom`, writing report artifacts
under `reports/livelihood_loom/borrower_verifier/` and, when attached to runtime,
projecting through existing `EvidenceReceipt` / `RuntimeReceipt` surfaces.

Candidate module:

- `dharma_swarm/venture_cell/livelihood_loom/borrower_verifier.py`

Candidate tests:

- `tests/test_venture_cell_livelihood_borrower_verifier.py`

No dashboard route until the verifier has an offline receipt. The repo's
product surface says dashboard is canonical, but this does not need UI first.

## Constructive Challenges

1. The phrase "verification layer for the powerless" is morally accurate but
   operationally hot. Use it internally. Externally lead with "independent
   borrower-side verification rail" or "consumer-side digital-lending verifier."

2. "One receipt kernel across all 20 help-vectors" is too abstract for a first
   build. The v0 receipt should be loan-term-specific: source hash, extracted
   cashflows, jurisdiction profile, computed APR/effective cost, clause findings,
   unsupported-claim count, and deterministic recomputation status.

3. APR is not universal. The oracle must be jurisdiction-profiled. U.S. Reg Z,
   RBI digital-lending APR/KFS, Apple 36% app policy, and Google Play short-term
   policy are related but not identical. Hard-code "true APR" as one universal
   number and the verifier will lie.

4. The model extraction problem and the APR oracle problem must be separated.
   First benchmark structured terms -> deterministic APR. Then benchmark text
   extraction -> structured terms. Combining them from day one hides failure.

5. Trap-clause classification must not pretend to be legal advice. It should
   produce "risk flags with source spans and policy/rule refs," not legal
   conclusions.

6. Borrower-side distribution is harder than the thesis admits. People do not
   comparison-shop loan T&Cs when they need cash tonight. The first users may be
   advocates, regulators, journalists, app-store reviewers, and responsible
   lenders, not individual borrowers.

7. Incumbents cannot fully own this, but they can still copy a shallow version.
   The moat is not "APR calculator." The moat is a multilingual, evidence-linked
   clause bank plus outcomes: which products, clauses, disclosures, and recourse
   packets actually prevented harm or corrected a decision.

## First Build Slice

### Scope

Build a deterministic offline verifier for structured loan terms and labeled
source clauses.

Inputs:

- principal disbursed to borrower
- fees and charges, with timing and inclusion policy
- repayment schedule
- jurisdiction/app-policy profile
- source snippets or clause spans

Outputs:

- computed annualized cost under selected profile
- total repayment and fee burden
- clause findings with source spans
- unsupported findings count
- policy checks: short-term repayment, missing max APR, missing representative
  cost example, dark-pattern phrase candidates, missing grievance/KFS where
  jurisdiction requires it
- machine-readable verification artifact

### Receipt schema v0

```json
{
  "schema_version": "livelihood_loom.borrower_verifier.v0",
  "receipt_id": "bv_...",
  "source_hash": "sha256:...",
  "jurisdiction_profile": "rbi_digital_lending_2025",
  "cashflow_hash": "sha256:...",
  "computed": {
    "apr_percent": 0.0,
    "effective_cost_percent": 0.0,
    "total_repayment": 0.0,
    "method": "actuarial_irr"
  },
  "policy_checks": [],
  "clause_findings": [],
  "unsupported_findings": 0,
  "audit_status": "deterministic_recompute_passed"
}
```

### Metrics

- APR absolute error against hand-computed labels
- effective-cost absolute error
- clause precision/recall/F1
- unsupported finding rate
- evidence-span localization accuracy
- adversarial robustness after machine-translation/obfuscation variants

### Seven-day plan

Day 1: implement structured cashflow model and deterministic APR solver.

Day 2: add jurisdiction/app-policy profiles: Reg Z closed-end, RBI 2025
digital lending, Google Play loan-app policy, Apple app-review personal-loan
policy.

Day 3: build clause taxonomy and a small labeled fixture set.

Day 4: emit v0 verification artifacts under `reports/livelihood_loom`.

Day 5: add red-team clause mutations and unsupported-claim rejection tests.

Day 6: run on 30 hand-labeled public examples or synthetic-public fixtures.

Day 7: write a first receipt: pass/fail metrics, failure examples, and next
partner target.

## Who Can Make It Real

Best first institutional paths:

1. Accion / CFI: strongest bridge from repo thesis to field distribution.
   Accion says it has helped build 299 financial service providers across 77
   countries and reached 500M+ underserved people. It also houses CFI, which
   focuses on consumer protection and data risks.
   Source: https://www.accion.org/

2. AFI: regulator network path. AFI is owned and led by member central banks
   and financial regulators and has consumer empowerment, market conduct, and
   digital financial services working groups.
   Source: https://www.afi-global.org/about/

3. CGAP: standards/research path. CGAP's current topic map includes Data and
   AI, Consumer Protection, Regulation for Digital Finance, Supervision, and
   Market Monitoring.
   Source: https://www.cgap.org/

4. RBI-like regulators and digital-lending supervisors: best for turning the
   verifier into a public compliance/checking artifact because the 2025
   directions already require comparison views, KFS, DLA reporting, and
   borrower grievance paths.

5. Legal-aid, consumer-protection, and debt-counseling organizations: best for
   borrower-side trust and labeled harm cases.

Avoid as first path:

- Predatory lenders. Their economics conflict with the verifier.
- Broad super-app/payment giants. Their fraud/credit teams will absorb the idea
  as platform risk tooling and strip the borrower-side posture.
- Pure AI-eval SaaS buyers. They will turn it into model QA, not recourse.

## Decision

Proceed with wedge 2, but rename the first loop:

**True-Cost Receipt Kernel**

Do not start with screenshots, multilingual OCR, or a public consumer app. Start
with deterministic structured terms and source spans. The first claim to prove:

> For N labeled loan offers, the kernel recomputes true cost within tolerance,
> flags rule/policy failures with evidence spans, and emits zero unsupported
> findings.

That is the first receipt. Everything else is strategy until that number exists.

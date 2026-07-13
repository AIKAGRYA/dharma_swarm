# Round 5 fact check

This is a locator map, not authority. Reviewers must verify each locator in the
attached file before accepting or contradicting it.

## 1. The first failure is preserved as a failure

- `AGENTOPS_CLOSEOUT_ATTEMPT1.json:269` says `"status": "failed"`.
- Its gate rows preserve the two broad-suite failures and the sandbox denial.
- `RESEARCH_AND_VERIFICATION.md:170-188` explains the failure and requires a
  rerun; it does not rename the attempt as a pass or a product defect.
- The file is included in the final closeout scope at
  `AGENTOPS_CLOSEOUT_FINAL.json:236-237` and `:259-260`.

Falsifier: the attached attempt file is missing, says passed, or differs from
the failed external runner report.

## 2. Full tests and governed tests are distinct claims

- Full plugin-aware evidence is recorded in
  `RESEARCH_AND_VERIFICATION.md:104-113`: 102 chamber tests and 22
  graph-adjacent tests passed under the repository environment.
- The runner limitation and continued requirement for those full suites are
  explicit at `RESEARCH_AND_VERIFICATION.md:181-188`.
- The packet calls its narrower gates `dependency-light` at packet lines 159
  and 184, and explicitly requires the separate full results at line 258.
- The final governed report records 33 focused, 84 dependency-light chamber,
  22 semantic-negative, and 12 dependency-light checkpoint tests, plus Ruff,
  diff, and the jailed control. `AGENTOPS_CLOSEOUT_FINAL.json:275` says passed.

Falsifier: the packet or ledger claims the governed runner executed the full
102/22 suites, or drops the full results as a required separate check.

## 3. The claim ceiling is HARNESS_PROVEN

- The packet says V0 **cannot establish** `CLOSED_LIVE` or production readiness
  at line 256.
- The specification says the strongest claim is `HARNESS_PROVEN` and explicitly
  says never `CLOSED_LIVE` at spec lines 687-690.
- The only other Part I `CLOSED_LIVE` occurrence reports `0/13` closed loops.
- The research ledger's non-claims and kill criteria are at lines 213-235.

Falsifier: cite an attached sentence that positively asserts `CLOSED_LIVE`,
universal determinism, automatic RCA, or production readiness for V0.

## 4. Model agreement cannot mint runtime authority

- `COUNCIL_REVIEW.md:3` says model agreement is review evidence only and cannot
  mint runtime authority.
- `RESEARCH_AND_VERIFICATION.md:223-224` repeats that neither checksums nor
  models are independent operational authority.
- `dharma_swarm/chamber/proof.py` contains no council/model import or decision
  input. Promotion requires the live verifier-attested claim plus evaluator-
  issued registry capability at `proof.py:283-331`.

Falsifier: identify an executable path from a council/model result into
`PromotionEvaluator.mint_authorization`, `evaluate`, or `promote`.

## 5. Final governed result

- Final packet digest:
  `015d84edf32817581451c1c2808f3033b5d78f0893fed03abea60bf83ceca814`.
- `AGENTOPS_CLOSEOUT_FINAL.json:225` records that digest.
- `AGENTOPS_CLOSEOUT_FINAL.json:275` records `status: passed`.
- Every positive gate and the isolated negative control has `passed: true`;
  scope passed and final Git status is empty.

This closeout was a rerun of the revised packet under a host context that could
create the nested macOS jail. The first report remains separately immutable.

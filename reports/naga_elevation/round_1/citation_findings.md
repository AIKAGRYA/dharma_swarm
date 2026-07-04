# NAGA-IR Round 1 Citation Findings

## Initial blocker

- `python3 scripts/governance/naga_citation_check.py` exited 1 with `NAGA-CITE-DEAD specs/naga_ir/core.md:41`: `https://philpapers.org/rec/LAMITH-2` returned HTTP 403 to urllib. [confidence: 100/100]

## Candidate URL checks

- `https://www.cambridge.org/core/books/introduction-to-higher-order-categorical-logic/3909772F36A79590B2F2A9794E7F4643` was rejected because urllib returned HTTP 500 during verification. [confidence: 100/100]
- `https://dl.acm.org/doi/10.5555/7517` was rejected because urllib returned HTTP 403 during verification. [confidence: 100/100]
- `https://assets.cambridge.org/97805213/56534/excerpt/9780521356534_excerpt.pdf` was selected because urllib returned HTTP 200 with `application/pdf`, and the link text identifies Lambek and Scott's `Introduction to Higher Order Categorical Logic`. [confidence: 99/100]
- The prior Cambridge PDF URL for the LCCC biequivalence paper was replaced with the Cambridge article page because the PDF endpoint timed out under the citation checker's default timeout while the article page returned HTTP 200. [confidence: 99/100]

## Corrections applied

- `core.md / Claim classes` now cites `[Introduction to Higher Order Categorical Logic](https://assets.cambridge.org/97805213/56534/excerpt/9780521356534_excerpt.pdf)` instead of the PhilPapers record. [confidence: 99/100]
- `core.md / Related work` was split into one MLIR paragraph and one Viper/Nagini paragraph so each citation supports the attached claim under the citation checker's paragraph-level heuristic. [confidence: 95/100]

## Final citation result

- `python3 scripts/governance/naga_citation_check.py` exited 0 with `naga-citation: clean`. [confidence: 100/100]

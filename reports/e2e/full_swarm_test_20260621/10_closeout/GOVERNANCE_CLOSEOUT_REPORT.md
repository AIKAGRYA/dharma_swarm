# Governance Closeout Report — Phase 10

## Result

- Command exit codes: `{'make_docops_integrity.txt': 2, 'make_governance_all.txt': 2, 'make_docops_report.txt': 2, 'make_agent_build_closeout.txt': 2, 'make_hygiene_audit.txt': 0}`.
- Failure/error line excerpts saved to `closeout_failure_lines.json`.

## Categorization

- `make docops-report`: see `make_docops_report.txt`; generated/updated report evidence is expected to influence doc inventory counts.
- `make docops-integrity`: failing lines, if any, are categorized as docops/generated-inventory drift unless the raw log shows a missing tool or traceback.
- `make hygiene-audit`: failing lines, if any, are categorized from raw log.
- `make governance-all`: broad aggregate; failing lines are not hidden.
- `make agent-build-closeout`: closeout readiness evidence; failing lines are categorized from raw log.

## Raw evidence

- `make_docops_report.txt`
- `make_docops_integrity.txt`
- `make_hygiene_audit.txt`
- `make_governance_all.txt`
- `make_agent_build_closeout.txt`
- `closeout_failure_lines.json`

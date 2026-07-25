# Revenue Wedge Audit Kit Fixture

A tiny, fully synthetic "client" repository used by
`tests/test_revenue_wedge_audit_kit.py` to prove the audit kit end-to-end.

- No vendored external code: every file here was written for this fixture.
- Slop is planted deliberately (fake credential literal, unannotated public
  functions, a duplicated function body, an untested module, commented-out
  code, TODO markers) so each detector has a known target.
- The credential in `src/app.py` is a synthetic placeholder
  (`sk-FIXTURE-not-a-real-key-0000`), not a real secret.
- The nested test file is named `checks_helpers.py` (not `test_*.py`) so the
  parent repo's pytest run never collects it; the audit kit still treats it as
  test evidence because it lives under `tests/`.

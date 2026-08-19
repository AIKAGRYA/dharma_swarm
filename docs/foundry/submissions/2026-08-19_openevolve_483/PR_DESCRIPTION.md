# PR packet — OpenEvolve issue #483 (ready for operator submission)

Target: https://github.com/algorithmicsuperintelligence/openevolve
Fixes: #483
Branch name suggestion: `fix-novelty-verdict-parsing`
Files: `openevolve/novelty_judge.py`, `openevolve/database.py`,
`tests/test_novelty_verdict_parsing.py` (new). Patch: `fix.patch` (this dir).

---

## Suggested PR title

```
fix: novelty judge misreads NOT_NOVEL as novel — parser/prompt delimiter mismatch (#483)
```

## Suggested PR body (paste below this line)

Fixes #483.

**What was broken.** The novelty prompt instructs the model to respond
`NOVEL` or `NOT_NOVEL` (underscore), but the response parsing in
`ProgramDatabase._llm_judge_novelty` searched for `"NOT NOVEL"` (space).
A compliant `NOT_NOVEL` reply therefore never matched the negative token —
while the substring `"NOVEL"` inside it *did* match the positive one — so
every rejection was parsed as `NOVEL`, and the LLM novelty judge could
never reject a program.

**The fix.**

- Parsing moves into `openevolve/novelty_judge.py` as
  `parse_novelty_verdict()`, next to the prompts that define the response
  format, so the format and its parser stay coupled.
- The parser accepts both `NOT_NOVEL` (what the prompt mandates) and
  `NOT NOVEL` (the variant the old code expected). When both tokens appear,
  the earliest occurrence wins — same tie-break the previous code intended.
- `database.py` calls the shared parser. Behavior on unparseable responses
  is unchanged: warn and assume novel (fail-open), as before.
- Also fixes the adjacent duplicated condition
  `if content is None or content is None:` → empty responses are now
  actually caught (`content is None or not content.strip()`).

**Tests.** `tests/test_novelty_verdict_parsing.py` pins the parsing
contract: underscore rejection (the #483 case), space rejection, NOVEL
acceptance, case-insensitivity, verdict-after-preamble, earliest-token
tie-break, and unparseable → `None`.

```
$ OPENAI_API_KEY=test-key-for-unit-tests python -m unittest discover tests
Ran 437 tests ... OK        # 430 baseline + 7 new, zero regressions
```

**Note for maintainers (out of scope here).** The fail-open default
(unparseable / LLM error ⇒ assume novel) is preserved unchanged. If you'd
prefer fail-closed or a retry, happy to follow up separately — this PR only
makes the parser read the format the prompt asks for.

**Disclosure.** This fix was developed with AI assistance and human review;
all tests were executed and verified before submission.

---

## Verification receipt (lab-local)

- Upstream tree at clone (depth-50, 2026-08-19): baseline
  `Ran 430 tests ... OK` (exit 0).
- Patched tree: `Ran 437 tests ... OK` (exit 0) — zero regressions,
  7 new tests pass.
- Targeted run: `python -m unittest tests.test_novelty_verdict_parsing -v`
  → 7/7 OK.
- Bug mechanism confirmed by direct read: `database.py` (parser, previously
  inline) vs `novelty_judge.py` line 43 (prompt format).

## Operator submission steps (when you ratify)

1. Fork `algorithmicsuperintelligence/openevolve` under your account.
2. `git checkout -b fix-novelty-verdict-parsing && git apply fix.patch`
   (or cherry-pick from our prepared tree), commit, push.
3. Open the PR with the title/body above.
4. On merge by a maintainer: that is ring-3 / One Wire receipt #1
   (domain: external_code_contribution, independent merger).

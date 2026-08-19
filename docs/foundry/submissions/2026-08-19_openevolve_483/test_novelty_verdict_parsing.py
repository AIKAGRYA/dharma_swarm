"""
Tests for novelty-judge response parsing (issue #483).

The prompt in openevolve/novelty_judge.py instructs the model to respond with
NOVEL or NOT_NOVEL (underscore). The previous inline parser searched for
"NOT NOVEL" with a space, so a compliant NOT_NOVEL reply — which contains the
substring "NOVEL" — was misread as novel, meaning the judge could never
reject. These tests pin the parsing contract for both delimiters.
"""

import unittest

from openevolve.novelty_judge import parse_novelty_verdict


class TestParseNoveltyVerdict(unittest.TestCase):
    def test_not_novel_underscore_is_rejected(self):
        # The exact format the prompt mandates — the issue #483 bug case.
        self.assertIs(
            parse_novelty_verdict("NOT_NOVEL - only variable renames"), False
        )

    def test_not_novel_space_is_rejected(self):
        self.assertIs(parse_novelty_verdict("NOT NOVEL: same core logic"), False)

    def test_novel_is_accepted(self):
        self.assertIs(
            parse_novelty_verdict("NOVEL - switches to simulated annealing"), True
        )

    def test_case_insensitive(self):
        self.assertIs(parse_novelty_verdict("not_novel, trivial refactor"), False)
        self.assertIs(parse_novelty_verdict("novel approach to sampling"), True)

    def test_verdict_after_preamble(self):
        self.assertIs(
            parse_novelty_verdict("The proposed code is NOT_NOVEL because it "
                                  "only reorders imports."),
            False,
        )
        self.assertIs(
            parse_novelty_verdict("Decision: NOVEL. The control flow differs."),
            True,
        )

    def test_earliest_token_wins_when_both_present(self):
        self.assertIs(
            parse_novelty_verdict("NOVEL at first glance... though parts are "
                                  "NOT_NOVEL."),
            True,
        )

    def test_unparseable_returns_none(self):
        self.assertIsNone(parse_novelty_verdict(""))
        self.assertIsNone(parse_novelty_verdict("I cannot determine this."))
        # Caller (ProgramDatabase._llm_judge_novelty) maps None to the
        # fail-open default (assume novel) with a warning — policy unchanged.


if __name__ == "__main__":
    unittest.main()

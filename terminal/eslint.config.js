// F-013: ESLint flat config for terminal/src and terminal/tests.
// Law: `bun run lint` must exit 0 with 0 errors on the full tree.
//
// WARNINGS BUDGET — documented and ENFORCED:
//   @typescript-eslint/no-unused-vars is demoted to "warn" for the 19 legacy
//   unused imports/locals present when F-013 landed (2026-06-12). The budget
//   is enforced by `--max-warnings 19` in the package.json lint script: any
//   NEW warning (e.g. a fresh unused variable) exceeds the budget and fails
//   the run with exit 1. The budget moves DOWN only — when legacy warnings
//   are fixed, lower the --max-warnings number in the same commit (same
//   one-directional discipline as scripts/ratchet.sh).
//
// RULE EXEMPTION (not debt):
//   no-control-regex is OFF. This is a terminal UI; regexes over control
//   characters (\x1b ANSI escapes, \x00-\x1f sanitization) are the domain,
//   not an accident. src/app.tsx:3014 and tests/app.test.ts:530 are correct.
import js from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    // Lint surface is src/ and tests/ (plus this config); everything else
    // is out of scope.
    ignores: [
      'node_modules/**',
      'assets/**',
      'scripts/**',
      'LESSONS/**',
    ],
  },
  {
    files: ['src/**/*.{ts,tsx}', 'tests/**/*.{ts,tsx}', 'eslint.config.js'],
    extends: [js.configs.recommended, tseslint.configs.recommended],
    rules: {
      '@typescript-eslint/no-unused-vars': 'warn',
      'no-control-regex': 'off',
    },
  },
);

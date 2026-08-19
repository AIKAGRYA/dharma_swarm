# Review request: authority-scoped remote holon fast path

Review the uncommitted implementation in this worktree for the narrow claim
below. Return the required council JSON and be adversarial.

## Claim under review

This change is merge-ready as a safe *foundation*, not as a production remote
deployment system:

1. Installed `dgc agent talk/run` no longer imports the excluded `scripts`
   package.
2. `dgc agent bootstrap` has a read-only default plan and an explicit,
   idempotent local apply path that creates the existing canonical holon
   identity/onboarding surfaces, refuses conflicting claims, rejects unknown
   providers, round-trips `load_holon`, and reads no secret.
3. Execution-lease v1 consumers now fail closed for requested action/path
   scopes; baseline denials cannot be removed; repeated wake start loads and
   re-validates an exact agent/task/action lease before every spawned-loop
   cycle so expiry/revocation halts an already-running loop.
4. The code explicitly admits that lease v1 is a local checksum receipt, not a
   cryptographic operator signature.
5. Remote SSH support is read-only preflight only: alias/name validation, fixed
   hardened SSH argv, fixed probe, allowlisted output, no values/counts/lengths,
   and authentication is never promoted to deployment authority.
6. Full global-key replication and remote activation remain blocked. The docs
   name the missing non-root runtime, immutable artifact delivery, scoped secret
   grant, signed authority v2, and bounded health proof.
7. The previously host-only `dkeys` tool is now versioned at `scripts/dkeys.py`:
   inline secrets/raw export are refused, writes are locked and atomic, safe
   JSON contains no key metadata, and `exec` injects only named stored provider
   variables into a direct child process. The live installed copy is
   byte-identical to the repository source.

## Do not approve if

- any input can become shell/SSH command injection;
- any secret value, prefix, length, raw environment, or credential count can
  escape through code, status, errors, tests, or docs;
- an SSH success or key-file observation is represented as authorization;
- bootstrap can silently overwrite an existing soul/provider/model claim;
- partial failure or idempotence creates a second registry/runtime/truth store;
- an empty/unscoped lease can authorize requested work;
- a non-empty arbitrary string can still start the repeated wake loop;
- package installation still requires `scripts.*`;
- documentation says remote deployment is ready when evidence says it is not;
- tests merely assert prose instead of exercising the boundaries.

## Expected remaining blockers (not hidden)

- ExecutionLease v2 operator attestation/signature does not exist yet.
- Existing shells/LaunchAgents still receive the broad ambient key environment;
  converting each daemon to scoped injection needs a separate dependency audit.
- Existing VPS logins are root; none is approved for remote mutation in this
  change.
- `grok_build` is not a live Grok holon because xAI is not a supported runtime
  provider yet.
Judge whether the repository diff truthfully and safely establishes the narrow
foundation claim while keeping these blockers closed.

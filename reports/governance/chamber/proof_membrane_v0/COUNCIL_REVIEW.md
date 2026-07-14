# Decorrelated Council Record

Model agreement is review evidence only. It cannot mint runtime authority.

## Round 1 — held

Runner artifact (external cache):
`20260713T161332Z-hyperbolic-chamber-proof-membrane-v0-hold_blockers`

| Lane | Requested route | Actual model | Verdict | Score |
|---|---|---|---|---:|
| glm52 | `ollama:glm-5.2:cloud` | `glm-5.2` | approve | 100 |
| kimi27code | `ollama:kimi-k2.7-code:cloud` | `kimi-k2.5` | pass | 100 |
| qwen3coder | `ollama:qwen3-coder:480b-cloud` | `qwen3-coder:480b-cloud` | pass | 100 |
| deepseekv4pro | `ollama:deepseek-v4-pro:cloud` | `deepseek-v4-pro` | approve | 100 |
| minimaxm3 | `ollama:minimax-m3:cloud` | `minimax-m3` | revise | 45 |
| nemotron3ultra | `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` | `nvidia/nemotron-3-ultra-550b-a55b:free` | pass | 100 |

Conviction gate: `hold_blockers`. Persistent witness `palantir-pilot` was
running and fresh.

The dissent identified missing attached manifest sources, insufficiently rich
per-process receipt evidence, stale counts, and confusion between the AgentOps
custody negative control and semantic negative tests. The five approvals were
not treated as closure.

Subsequent independent reviewers found stronger issues: unmanifested package
initializer execution, a direct-object contract bypass, caller-selected
candidate identity, repeated authorization minting, shallow receipt mutability,
and insufficient registry/effect binding. The final implementation repairs all
of these and narrows its trusted-process claim. Round 2 reviews the repaired
commit and does not inherit Round 1 votes.

## Round 2 — held

Runner artifact (external cache):
`20260713T172249Z-hyperbolic-chamber-proof-membrane-v0-round2-a0509a608-hold_blockers`

| Lane | Requested route | Actual model | Verdict | Score |
|---|---|---|---|---:|
| glm52 | `ollama:glm-5.2:cloud` | `glm-5.2` | pass | 100 |
| kimi27code | `ollama:kimi-k2.7-code:cloud` | `kimi-k2.5` | approve | 100 |
| qwen3coder | `ollama:qwen3-coder:480b-cloud` | `qwen3-coder:480b-cloud` | revise | 85 |
| deepseekv4pro | `ollama:deepseek-v4-pro:cloud` | `deepseek-v4-pro` | approve | 100 |
| minimaxm3 | `ollama:minimax-m3:cloud` | `minimax-m3` | approve | 100 |
| nemotron3ultra | `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` | `nvidia/nemotron-3-ultra-550b-a55b:free` | pass | 100 |

Conviction gate: `hold_blockers`. Persistent witness `palantir-pilot` was
running and fresh.

Qwen requested explicit proof that direct object construction cannot fabricate
provenance or evaluator authority and treated PM0-10 as not yet demonstrated.
The implementation already rejected those paths, but the evidence presentation
was ambiguous. The next revision adds literal constructors for a copied
`FreshProcessVerification`, a copied `Claim`, and the private authorization
shape; all must fail without invoking the effect. PM0-10 is also made
non-circular and aligned with the runner's stricter all-six rule. Round 3 does
not inherit any earlier vote.

## Round 3 — passed at full conviction

Durable runner receipts: `ROUND3_COUNCIL_SUMMARY.json` and
`ROUND3_COUNCIL_SUMMARY.md`.

| Lane | Requested route | Actual model | Verdict | Score |
|---|---|---|---|---:|
| glm52 | `ollama:glm-5.2:cloud` | `glm-5.2` | approve | 100 |
| kimi27code | `ollama:kimi-k2.7-code:cloud` | `kimi-k2.5` | approve | 100 |
| qwen3coder | `ollama:qwen3-coder:480b-cloud` | `qwen3-coder:480b-cloud` | pass | 100 |
| deepseekv4pro | `ollama:deepseek-v4-pro:cloud` | `deepseek-v4-pro` | pass | 100 |
| minimaxm3 | `ollama:minimax-m3:cloud` | `minimax-m3` | approve | 100 |
| nemotron3ultra | `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` | `nvidia/nemotron-3-ultra-550b-a55b:free` | pass | 100 |

Conviction gate: `pass_fullness`; minimum and mean score: 100; blockers:
zero. Persistent witness `palantir-pilot` was running and fresh with a
25-second heartbeat age. The runner reached five requested model identities
exactly; the requested Kimi 2.7 route reported actual model `kimi-k2.5`, which
is retained explicitly rather than silently described as Kimi 2.7.

This satisfies PM0-10 as a review gate only. It does not create provenance,
runtime authority, or a product-readiness claim.

## Round 4 — held

After Round 3, the first governed closeout failed closed for two environment
reasons preserved in `AGENTOPS_CLOSEOUT_ATTEMPT1.json`: the admission runner
disables pytest plugin autoload and supplies only a trusted host PATH, while
two packet gates assumed pytest-asyncio and a nested `python3` with pytest.
The negative-control jail also encountered macOS `sandbox-exec` denial under
the already-sandboxed build process.

The packet now distinguishes dependency-light admission slices from the full
plugin-aware test evidence. Four lanes approved at 100. Qwen returned 30/revise
with four claims contradicted by attached fields: it said the failed report was
not preserved, said V0 asserted `CLOSED_LIVE`, said model agreement created
runtime authority, and treated the explicit two-environment split as hidden.
MiniMax emitted 52,670 characters with extra data instead of one valid JSON
object, so the runner correctly typed that lane blocked. Persistent witness
`palantir-pilot` was fresh at 12 seconds. Conviction remained
`hold_blockers`; no approval carried forward.

## Round 5 — held on response-schema fullness

The revised packet subsequently passed governed closeout with clean scope, all
six positive gates, and the isolated negative control green. GLM, Kimi, Qwen,
DeepSeek, and MiniMax each substantively approved at 100; Qwen explicitly
retracted the Round 4 contradictions after checking the locators. The runner
still held because MiniMax put `"None."` in `explicit_disagreement`, which is
non-empty, and Nemotron's 100/approve response was truncated inside a JSON
string. Persistent witness `palantir-pilot` was fresh at three seconds. The
schema failures are blockers under the council contract even though their
visible content favored approval.

## Round 6 — passed at full conviction

Durable runner receipts: `ROUND6_COUNCIL_SUMMARY.json` and
`ROUND6_COUNCIL_SUMMARY.md`.

| Lane | Requested route | Actual model | Verdict | Score |
|---|---|---|---|---:|
| glm52 | `ollama:glm-5.2:cloud` | `glm-5.2` | approve | 100 |
| kimi27code | `ollama:kimi-k2.7-code:cloud` | `kimi-k2.7-code` | approve | 100 |
| qwen3coder | `ollama:qwen3-coder:480b-cloud` | `qwen3-coder:480b-cloud` | approve | 100 |
| deepseekv4pro | `ollama:deepseek-v4-pro:cloud` | `deepseek-v4-pro` | approve | 100 |
| minimaxm3 | `ollama:minimax-m3:cloud` | `minimax-m3` | approve | 100 |
| nemotron3ultra | `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` | `nvidia/nemotron-3-ultra-550b-a55b:free` | approve | 100 |

Conviction gate: `pass_fullness`; minimum and mean score: 100; blockers:
zero; every disagreement field empty. Persistent witness `palantir-pilot` was
running and fresh with a 27-second heartbeat age. No prior vote was inherited.

This closes the user's independent-model review condition and PM0-10 for the
bounded exact-scope harness claim. It still does not create runtime authority.

## Round 7 — pending final-code review

PR CI later found two owned Semgrep `eval-or-exec` violations in the snapshot
loaders. Commit `f1a15e72ecb641c3f167b9c0f581f0ce6b7492dc` removes those sinks
without suppression and adds direct captured-byte, metadata, cache-disable,
and failure-cleanup tests. The exact bundle and 100-process receipt were
regenerated. Round 6 is not inherited; `ROUND7_COUNCIL_PROMPT.md` asks all six
required lanes to review the repaired code and new scope.

---
title: Branch janitor receipt 2026-07-04
date: 2026-07-04
mode: dry-run
tool: scripts/governance/branch_janitor.py
---

# Branch janitor receipt — dry-run

- Generated: 2026-07-04T12:19:46Z
- Remote: origin (AmitabhainArunachala/dharma_swarm)
- Branches surveyed: 308
- Policy: closed-PR idle > 14d deletable; no-PR idle > 30d candidate-only; deletion requires tip == merged-PR head OID or closed-PR head match + idle window; tag archive/pr<N>--<branch> before every delete
- Registry: docs/governance/BRANCH_REGISTRY.yaml (5 entries)
- Deletable now: 172
- Total candidates (incl. review-only): 218

## Summary

| class | count | deletable |
|---|---|---|
| delete-merged | 43 | yes |
| delete-closed-idle | 129 | yes |
| candidate-tip-moved | 9 | no |
| candidate-no-pr-idle | 37 | no |
| waiting | 30 | no |
| exempt | 3 | no |
| protected | 20 | no |
| active | 37 | no |

## Deletable — merged-PR head evidence (43)

| branch | tip | last commit | evidence | planned tag |
|---|---|---|---|---|
| `audit/merge-2026-03-22` | c641f9bd3373 | 2026-03-22 | tip c641f9bd3373 == head OID of MERGED PR #1; content in main | `archive/pr1--audit/merge-2026-03-22` |
| `chore/commission-agent-runner-telic-chain` | 94d55b859847 | 2026-05-05 | tip 94d55b859847 == head OID of MERGED PR #119; content in main | `archive/pr119--chore/commission-agent-runner-telic-chain` |
| `chore/devin-inbound-11-step-audit` | d0cccf727edd | 2026-05-25 | tip d0cccf727edd == head OID of MERGED PR #345; content in main | `archive/pr345--chore/devin-inbound-11-step-audit` |
| `chore/governance-onboarding-convergence` | 1fc74de465de | 2026-05-20 | tip 1fc74de465de == head OID of MERGED PR #313; content in main | `archive/pr313--chore/governance-onboarding-convergence` |
| `chore/provider-lane-pin-fix` | 79b4aa62ebf3 | 2026-05-06 | tip 79b4aa62ebf3 == head OID of MERGED PR #139; content in main | `archive/pr139--chore/provider-lane-pin-fix` |
| `codex/authority-revenue-loop-clean` | 317d9ad27d7e | 2026-05-05 | tip 317d9ad27d7e == head OID of MERGED PR #98; content in main | `archive/pr98--codex/authority-revenue-loop-clean` |
| `codex/operator-brief-witness-ready` | 471bf599e4da | 2026-05-05 | tip 471bf599e4da == head OID of MERGED PR #96; content in main | `archive/pr96--codex/operator-brief-witness-ready` |
| `codex/pr90-critical-substrates-clean` | e144ba172c27 | 2026-05-05 | tip e144ba172c27 == head OID of MERGED PR #94; content in main | `archive/pr94--codex/pr90-critical-substrates-clean` |
| `codex/provenance-fanout-derivation-clean` | 630b71d2c23d | 2026-05-05 | tip 630b71d2c23d == head OID of MERGED PR #97; content in main | `archive/pr97--codex/provenance-fanout-derivation-clean` |
| `codex/trace-attractor-ledger-spec` | e15960560ec1 | 2026-05-05 | tip e15960560ec1 == head OID of MERGED PR #100; content in main | `archive/pr100--codex/trace-attractor-ledger-spec` |
| `codex/trace-attractor-projection-types` | 70c6303977d1 | 2026-05-05 | tip 70c6303977d1 == head OID of MERGED PR #103; content in main | `archive/pr103--codex/trace-attractor-projection-types` |
| `codex/trace-attractor-store-readers` | e05ab14036d5 | 2026-05-05 | tip e05ab14036d5 == head OID of MERGED PR #109; content in main | `archive/pr109--codex/trace-attractor-store-readers` |
| `devin/1777903781-provenance-wiring-mm17-mm18` | 776f0985e16a | 2026-05-04 | tip 776f0985e16a == head OID of MERGED PR #74; content in main | `archive/pr74--devin/1777903781-provenance-wiring-mm17-mm18` |
| `devin/1777909780-substrate-meta-layer-items-2-3` | 2b6b883496ba | 2026-05-04 | tip 2b6b883496ba == head OID of MERGED PR #83; content in main | `archive/pr83--devin/1777909780-substrate-meta-layer-items-2-3` |
| `devin/1777910581-ledger-watcher-operator-brief` | 03bf37e8e6ae | 2026-05-04 | tip 03bf37e8e6ae == head OID of MERGED PR #84; content in main | `archive/pr84--devin/1777910581-ledger-watcher-operator-brief` |
| `devin/1777938227-value-events-cli` | 8b58ef7166ac | 2026-05-04 | tip 8b58ef7166ac == head OID of MERGED PR #89; content in main | `archive/pr89--devin/1777938227-value-events-cli` |
| `devin/1777941324-test-coverage-phase2-6` | 6d0753860f4d | 2026-05-05 | tip 6d0753860f4d == head OID of MERGED PR #91; content in main | `archive/pr91--devin/1777941324-test-coverage-phase2-6` |
| `devin/1777994193-fractal-room-research` | 9a0cb9a0219e | 2026-05-05 | tip 9a0cb9a0219e == head OID of MERGED PR #123; content in main | `archive/pr123--devin/1777994193-fractal-room-research` |
| `devin/1778035620-wire-fractal-runtime` | 28823aa906da | 2026-05-06 | tip 28823aa906da == head OID of MERGED PR #134; content in main | `archive/pr134--devin/1778035620-wire-fractal-runtime` |
| `devin/1778683993-control-surface-contract-hardening` | b708aa49ee9c | 2026-05-18 | tip b708aa49ee9c == head OID of MERGED PR #307; content in main | `archive/pr307--devin/1778683993-control-surface-contract-hardening` |
| `devin/1779271215-fix-gitnexus-hint` | 1f3ba0ac29c1 | 2026-05-20 | tip 1f3ba0ac29c1 == head OID of MERGED PR #315; content in main | `archive/pr315--devin/1779271215-fix-gitnexus-hint` |
| `devin/1779279100-close-cockpit-track` | b59c9de3d4a8 | 2026-05-20 | tip b59c9de3d4a8 == head OID of MERGED PR #318; content in main | `archive/pr318--devin/1779279100-close-cockpit-track` |
| `devin/1779281950-track-transition-and-seeds` | 8aa9e33ba08d | 2026-05-20 | tip 8aa9e33ba08d == head OID of MERGED PR #319; content in main | `archive/pr319--devin/1779281950-track-transition-and-seeds` |
| `devin/1779946341-a2a-trace-persistence-e2e` | 6a909a6c1a2a | 2026-05-28 | tip 6a909a6c1a2a == head OID of MERGED PR #361; content in main | `archive/pr361--devin/1779946341-a2a-trace-persistence-e2e` |
| `devin/2026-05-30-proof-artifact-pivot` | 81abaeb88fd1 | 2026-05-30 | tip 81abaeb88fd1 == head OID of MERGED PR #382; content in main | `archive/pr382--devin/2026-05-30-proof-artifact-pivot` |
| `devin/runtime-truth-spine-pr-a` | 4e101bbbaf53 | 2026-05-28 | tip 4e101bbbaf53 == head OID of MERGED PR #364; content in main | `archive/pr364--devin/runtime-truth-spine-pr-a` |
| `devin/update-skills-1779976321` | 62d952487a1c | 2026-05-29 | tip 62d952487a1c == head OID of MERGED PR #365; content in main | `archive/pr365--devin/update-skills-1779976321` |
| `feat/auto-evolution` | 66954c2d728c | 2026-03-25 | tip 66954c2d728c == head OID of MERGED PR #5; content in main | `archive/pr5--feat/auto-evolution` |
| `feat/ontology-telos-gate-hardwire` | 592e7af48cfa | 2026-06-01 | tip 592e7af48cfa == head OID of MERGED PR #406; content in main | `archive/pr406--feat/ontology-telos-gate-hardwire` |
| `feat/operating-spine-v2` | e9cf1d54bcf7 | 2026-05-06 | tip e9cf1d54bcf7 == head OID of MERGED PR #140; content in main | `archive/pr140--feat/operating-spine-v2` |
| `feat/recursive-discovery-shadow-2026-05-14` | 3c28ddaeec3d | 2026-05-14 | tip 3c28ddaeec3d == head OID of MERGED PR #310; content in main | `archive/pr310--feat/recursive-discovery-shadow-2026-05-14` |
| `feat/s4-zeitgeist-executive-stage2` | 8b0d25aed137 | 2026-05-04 | tip 8b0d25aed137 == head OID of MERGED PR #63; content in main | `archive/pr63--feat/s4-zeitgeist-executive-stage2` |
| `feat/s4-zeitgeist-llm-scan` | 0d76ae9a3bac | 2026-05-04 | tip 0d76ae9a3bac == head OID of MERGED PR #61; content in main | `archive/pr61--feat/s4-zeitgeist-llm-scan` |
| `feat/world-radar-shakti-safe-convergence-2026-05-13` | 3befc1e9698e | 2026-05-13 | tip 3befc1e9698e == head OID of MERGED PR #296; content in main | `archive/pr296--feat/world-radar-shakti-safe-convergence-2026-05-13` |
| `fix/agent-wiring` | 82bdb12586af | 2026-03-25 | tip 82bdb12586af == head OID of MERGED PR #4; content in main | `archive/pr4--fix/agent-wiring` |
| `fix/ci-green` | c1f6ba2996c1 | 2026-03-25 | tip c1f6ba2996c1 == head OID of MERGED PR #3; content in main | `archive/pr3--fix/ci-green` |
| `fix/ci-tests-yaml` | 13ce17dbf666 | 2026-04-27 | tip 13ce17dbf666 == head OID of MERGED PR #34; content in main | `archive/pr34--fix/ci-tests-yaml` |
| `fix/semantic-index-idempotence` | c70b03e8267b | 2026-03-24 | tip c70b03e8267b == head OID of MERGED PR #2; content in main | `archive/pr2--fix/semantic-index-idempotence` |
| `mmm-a2a-conditional-merge` | 2c1aab8f04d1 | 2026-06-04 | tip 2c1aab8f04d1 == head OID of MERGED PR #477; content in main | `archive/pr477--mmm-a2a-conditional-merge` |
| `perplexity-computer/a2a-activation-1780025504` | feb539dd8c8f | 2026-05-30 | tip feb539dd8c8f == head OID of MERGED PR #376; content in main | `archive/pr376--perplexity-computer/a2a-activation-1780025504` |
| `perplexity-computer/doctrine-amendment-multi-track` | 512c23f74c45 | 2026-05-31 | tip 512c23f74c45 == head OID of MERGED PR #396; content in main | `archive/pr396--perplexity-computer/doctrine-amendment-multi-track` |
| `pr/routing-coherence` | bc4a9b2dcc93 | 2026-05-06 | tip bc4a9b2dcc93 == head OID of MERGED PR #141; content in main | `archive/pr141--pr/routing-coherence` |
| `spec/boardstore-facade` | 8191db251620 | 2026-05-20 | tip 8191db251620 == head OID of MERGED PR #316; content in main | `archive/pr316--spec/boardstore-facade` |

## Deletable — closed-PR idle (129)

| branch | tip | last commit | evidence | planned tag |
|---|---|---|---|---|
| `alignment-experiment-runpod` | 0ba31e2c7299 | 2026-04-16 | tip 0ba31e2c7299 == head OID of CLOSED PR #27; idle 57d > 14d window | `archive/pr27--alignment-experiment-runpod` |
| `chore/auto-spine-adoption-2026-06-11` | 670b23f8b477 | 2026-06-11 | tip 670b23f8b477 == head OID of CLOSED PR #580; idle 22d > 14d window | `archive/pr580--chore/auto-spine-adoption-2026-06-11` |
| `chore/command-plane-nav-trim` | ef2836c7a5fe | 2026-05-21 | tip ef2836c7a5fe == head OID of CLOSED PR #322; idle 34d > 14d window | `archive/pr322--chore/command-plane-nav-trim` |
| `chore/cron-canonical-declaration` | 31b1c42b6c2d | 2026-05-07 | tip 31b1c42b6c2d == head OID of CLOSED PR #161; idle 43d > 14d window | `archive/pr161--chore/cron-canonical-declaration` |
| `chore/cron-daemon-env-wrapper` | d417839179b3 | 2026-05-07 | tip d417839179b3 == head OID of CLOSED PR #158; idle 43d > 14d window | `archive/pr158--chore/cron-daemon-env-wrapper` |
| `chore/docops-authority-registry` | c5835c83e142 | 2026-05-05 | tip c5835c83e142 == head OID of CLOSED PR #147; idle 43d > 14d window | `archive/pr147--chore/docops-authority-registry` |
| `chore/governance-spine-adoption-metric-20260608` | 0fc04c7ffad1 | 2026-06-08 | tip 0fc04c7ffad1 == head OID of CLOSED PR #554; idle 25d > 14d window | `archive/pr554--chore/governance-spine-adoption-metric-20260608` |
| `chore/governance-spine-adoption-metric-refresh` | 7efc3cd8c1ce | 2026-06-07 | tip 7efc3cd8c1ce == head OID of CLOSED PR #552; idle 25d > 14d window | `archive/pr552--chore/governance-spine-adoption-metric-refresh` |
| `chore/governance/spine-adoption-metric-refresh` | b64e55d86baf | 2026-06-10 | tip b64e55d86baf == head OID of CLOSED PR #559; idle 22d > 14d window | `archive/pr559--chore/governance/spine-adoption-metric-refresh` |
| `chore/governance/spine-adoption-refresh-2026-06-07` | 3df9e6749a33 | 2026-06-07 | tip 3df9e6749a33 == head OID of CLOSED PR #519; idle 27d > 14d window | `archive/pr519--chore/governance/spine-adoption-refresh-2026-06-07` |
| `chore/governance/spine-adoption-refresh-20260606` | 598043331f0e | 2026-06-06 | tip 598043331f0e == head OID of CLOSED PR #518; idle 27d > 14d window | `archive/pr518--chore/governance/spine-adoption-refresh-20260606` |
| `chore/kimi-force-response-20260505` | 127e1b98009b | 2026-05-05 | tip 127e1b98009b == head OID of CLOSED PR #148; idle 43d > 14d window | `archive/pr148--chore/kimi-force-response-20260505` |
| `chore/ops-run-report-2026-06-03T1200Z` | 176eada5a8db | 2026-06-03 | tip 176eada5a8db == head OID of CLOSED PR #464; idle 28d > 14d window | `archive/pr464--chore/ops-run-report-2026-06-03T1200Z` |
| `chore/pr69-review-fixes` | c6510eaaad59 | 2026-05-04 | tip c6510eaaad59 == head OID of CLOSED PR #78; idle 60d > 14d window | `archive/pr78--chore/pr69-review-fixes` |
| `chore/refresh-spine-adoption-metric` | 3785209b6302 | 2026-06-14 | tip 3785209b6302 == head OID of CLOSED PR #596; idle 19d > 14d window | `archive/pr596--chore/refresh-spine-adoption-metric` |
| `chore/shakti-feedback-shadow-apply-dogfood` | 71f1064102cd | 2026-05-07 | tip 71f1064102cd == head OID of CLOSED PR #160; idle 57d > 14d window | `archive/pr160--chore/shakti-feedback-shadow-apply-dogfood` |
| `chore/spinal-bridge-clean-20260507` | f55085fb1b47 | 2026-05-07 | tip f55085fb1b47 == head OID of CLOSED PR #164; idle 57d > 14d window | `archive/pr164--chore/spinal-bridge-clean-20260507` |
| `chore/spine-adoption-metric-20260605` | eab8c15f6dca | 2026-06-05 | tip eab8c15f6dca == head OID of CLOSED PR #512; idle 27d > 14d window | `archive/pr512--chore/spine-adoption-metric-20260605` |
| `chore/spine-adoption-metric-20260606` | 2613498b9586 | 2026-06-06 | tip 2613498b9586 == head OID of CLOSED PR #513; idle 27d > 14d window | `archive/pr513--chore/spine-adoption-metric-20260606` |
| `chore/spine-adoption-metric-20260614-1800` | 3688a0e29a68 | 2026-06-14 | tip 3688a0e29a68 == head OID of CLOSED PR #605; idle 19d > 14d window | `archive/pr605--chore/spine-adoption-metric-20260614-1800` |
| `chore/spine-adoption-metric-refresh-20260603` | 160c54c4f009 | 2026-06-03 | tip 160c54c4f009 == head OID of CLOSED PR #463; idle 28d > 14d window | `archive/pr463--chore/spine-adoption-metric-refresh-20260603` |
| `chore/spine-adoption-metric-refresh-20260611` | 9c5a168026c7 | 2026-06-11 | tip 9c5a168026c7 == head OID of CLOSED PR #571; idle 22d > 14d window | `archive/pr571--chore/spine-adoption-metric-refresh-20260611` |
| `chore/telos-hierarchy-doctrine-correction` | 3ed35a857f48 | 2026-05-09 | tip 3ed35a857f48 == head OID of CLOSED PR #181; idle 43d > 14d window | `archive/pr181--chore/telos-hierarchy-doctrine-correction` |
| `claude/confirm-plan-working-3qaaq` | 1432f10e2cf1 | 2026-05-28 | tip 1432f10e2cf1 == head OID of CLOSED PR #359; idle 34d > 14d window | `archive/pr359--claude/confirm-plan-working-3qaaq` |
| `cleanup/docstrings-full-power-probe-20260507` | b007dddddfd5 | 2026-05-06 | tip b007dddddfd5 == head OID of CLOSED PR #144; idle 43d > 14d window | `archive/pr144--cleanup/docstrings-full-power-probe-20260507` |
| `cleanup/route-witness-main-2026-05-13` | 56ec13647c18 | 2026-05-13 | tip 56ec13647c18 == head OID of CLOSED PR #297; idle 43d > 14d window | `archive/pr297--cleanup/route-witness-main-2026-05-13` |
| `codex/hypernode-empty-quadrant` | 25cd4079ce1a | 2026-05-05 | tip 25cd4079ce1a == head OID of CLOSED PR #99; idle 43d > 14d window | `archive/pr99--codex/hypernode-empty-quadrant` |
| `codex/runtime-convergence-hardening` | 4f38296b7d95 | 2026-03-30 | tip 4f38296b7d95 == head OID of CLOSED PR #12; idle 57d > 14d window | `archive/pr12--codex/runtime-convergence-hardening` |
| `copilot/clean-pr-portfolio-map` | 24b1c9a1a5e4 | 2026-06-05 | tip 24b1c9a1a5e4 == head OID of CLOSED PR #476; idle 28d > 14d window | `archive/pr476--copilot/clean-pr-portfolio-map` |
| `copilot/featurecontrol-loop-hardening-chetana-rebase` | 937723bd2c12 | 2026-04-28 | tip 937723bd2c12 == head OID of CLOSED PR #50; idle 66d > 14d window | `archive/pr50--copilot/featurecontrol-loop-hardening-chetana-rebase` |
| `copilot/latest-pull-request` | f792d5fafb61 | 2026-04-04 | tip f792d5fafb61 == head OID of CLOSED PR #19; idle 57d > 14d window | `archive/pr19--copilot/latest-pull-request` |
| `copilot/merge-all-changes` | 9085e1bb1c9c | 2026-06-05 | tip 9085e1bb1c9c == head OID of CLOSED PR #494; idle 28d > 14d window | `archive/pr494--copilot/merge-all-changes` |
| `copilot/triage-open-pr-backlog` | 8a3533b482b7 | 2026-05-13 | tip 8a3533b482b7 == head OID of CLOSED PR #271; idle 43d > 14d window | `archive/pr271--copilot/triage-open-pr-backlog` |
| `design/routing-fusion-spine-pr` | 84dfd7ae4403 | 2026-05-10 | tip 84dfd7ae4403 == head OID of CLOSED PR #190; idle 43d > 14d window | `archive/pr190--design/routing-fusion-spine-pr` |
| `devin/1777890984-authority-revenue-loop-gauntlet` | 50fd7def3473 | 2026-05-05 | tip 50fd7def3473 == head OID of CLOSED PR #66; idle 60d > 14d window | `archive/pr66--devin/1777890984-authority-revenue-loop-gauntlet` |
| `devin/1777901958-repo-reality-gauntlet` | 3329de00eea9 | 2026-05-05 | tip 3329de00eea9 == head OID of CLOSED PR #69; idle 60d > 14d window | `archive/pr69--devin/1777901958-repo-reality-gauntlet` |
| `devin/1777938416-provenance-fanout-derivation` | d6cb6e199f33 | 2026-05-05 | tip d6cb6e199f33 == head OID of CLOSED PR #88; idle 60d > 14d window | `archive/pr88--devin/1777938416-provenance-fanout-derivation` |
| `devin/1777940178-test-coverage-cold-substrates` | fe1ef8f69cf1 | 2026-05-05 | tip fe1ef8f69cf1 == head OID of CLOSED PR #90; idle 60d > 14d window | `archive/pr90--devin/1777940178-test-coverage-cold-substrates` |
| `devin/1777972679-consolidation-alignment` | cfac1b197cc6 | 2026-05-05 | tip cfac1b197cc6 == head OID of CLOSED PR #117; idle 43d > 14d window | `archive/pr117--devin/1777972679-consolidation-alignment` |
| `devin/1777995295-fractal-room-build` | c15da77eb0c4 | 2026-05-05 | tip c15da77eb0c4 == head OID of CLOSED PR #125; idle 59d > 14d window | `archive/pr125--devin/1777995295-fractal-room-build` |
| `devin/1777996370-structural-coherence` | 4f3f7f612f8b | 2026-05-06 | tip 4f3f7f612f8b == head OID of CLOSED PR #131; idle 43d > 14d window | `archive/pr131--devin/1777996370-structural-coherence` |
| `devin/1779703534-11-step-chain-verdict` | d6fb4493d6b4 | 2026-05-25 | tip d6fb4493d6b4 == head OID of CLOSED PR #346; idle 38d > 14d window | `archive/pr346--devin/1779703534-11-step-chain-verdict` |
| `devin/1779707153-11step-build-plan` | 926ba0dccbb0 | 2026-05-25 | tip 926ba0dccbb0 == head OID of CLOSED PR #347; idle 34d > 14d window | `archive/pr347--devin/1779707153-11step-build-plan` |
| `devin/1779721563-11-step-chain-verdict` | b291be8e1c23 | 2026-05-25 | tip b291be8e1c23 == head OID of CLOSED PR #352; idle 34d > 14d window | `archive/pr352--devin/1779721563-11-step-chain-verdict` |
| `devin/1779876416-11-step-chain-verdict-v2` | a5d15e99f511 | 2026-05-27 | tip a5d15e99f511 == head OID of CLOSED PR #354; idle 34d > 14d window | `archive/pr354--devin/1779876416-11-step-chain-verdict-v2` |
| `devin/1779883637-11-step-chain-verdict-v2` | 5fb2c9427d87 | 2026-05-29 | tip 5fb2c9427d87 == head OID of CLOSED PR #355; idle 34d > 14d window | `archive/pr355--devin/1779883637-11-step-chain-verdict-v2` |
| `devin/1779890777-11-step-verdict-v3` | 0a67102eb6d7 | 2026-05-29 | tip 0a67102eb6d7 == head OID of CLOSED PR #356; idle 34d > 14d window | `archive/pr356--devin/1779890777-11-step-verdict-v3` |
| `devin/1779905139-11-step-chain-verdict-v2` | a732dfbbcfba | 2026-05-29 | tip a732dfbbcfba == head OID of CLOSED PR #357; idle 36d > 14d window | `archive/pr357--devin/1779905139-11-step-chain-verdict-v2` |
| `devin/1779919577-11step-chain-verdict-v4` | 89b5f43d0051 | 2026-05-29 | tip 89b5f43d0051 == head OID of CLOSED PR #358; idle 34d > 14d window | `archive/pr358--devin/1779919577-11step-chain-verdict-v4` |
| `devin/1779943311-devin-a2a-fleet-plan` | 190f7a4c44ad | 2026-05-30 | tip 190f7a4c44ad == head OID of CLOSED PR #360; idle 34d > 14d window | `archive/pr360--devin/1779943311-devin-a2a-fleet-plan` |
| `devin/1779962811-11step-chain-verdict-v5` | 3b781cd396a9 | 2026-05-29 | tip 3b781cd396a9 == head OID of CLOSED PR #363; idle 34d > 14d window | `archive/pr363--devin/1779962811-11step-chain-verdict-v5` |
| `devin/1779977141-11step-chain-verdict` | 49e634a7c335 | 2026-05-29 | tip 49e634a7c335 == head OID of CLOSED PR #366; idle 34d > 14d window | `archive/pr366--devin/1779977141-11step-chain-verdict` |
| `devin/1779978250-spine-governance-registration` | 67cf9b40ca02 | 2026-05-28 | tip 67cf9b40ca02 == head OID of CLOSED PR #367; idle 36d > 14d window | `archive/pr367--devin/1779978250-spine-governance-registration` |
| `devin/1779991547-11step-chain-verdict-v6` | 5043be08160d | 2026-05-31 | tip 5043be08160d == head OID of CLOSED PR #371; idle 34d > 14d window | `archive/pr371--devin/1779991547-11step-chain-verdict-v6` |
| `devin/1780022557-11-step-verdict-v3` | 725a12b5f313 | 2026-05-31 | tip 725a12b5f313 == head OID of CLOSED PR #374; idle 34d > 14d window | `archive/pr374--devin/1780022557-11-step-verdict-v3` |
| `devin/1780038474-11step-chain-verdict-fresh` | 4b176c57f511 | 2026-05-30 | tip 4b176c57f511 == head OID of CLOSED PR #377; idle 34d > 14d window | `archive/pr377--devin/1780038474-11step-chain-verdict-fresh` |
| `devin/1780042107-11step-chain-verdict` | 672ba40db4b5 | 2026-05-30 | tip 672ba40db4b5 == head OID of CLOSED PR #378; idle 34d > 14d window | `archive/pr378--devin/1780042107-11step-chain-verdict` |
| `devin/1780059954-inbound-check-status` | 9c85e1703d55 | 2026-05-30 | tip 9c85e1703d55 == head OID of CLOSED PR #379; idle 34d > 14d window | `archive/pr379--devin/1780059954-inbound-check-status` |
| `devin/1780095832-inbound-check-status` | b408bb6ba768 | 2026-05-30 | tip b408bb6ba768 == head OID of CLOSED PR #380; idle 34d > 14d window | `archive/pr380--devin/1780095832-inbound-check-status` |
| `devin/1780103068-inbound-check-response` | 9a4dde11b159 | 2026-05-30 | tip 9a4dde11b159 == head OID of CLOSED PR #381; idle 34d > 14d window | `archive/pr381--devin/1780103068-inbound-check-response` |
| `devin/1780128383-inbound-check-response` | 67145a8ea2d3 | 2026-05-30 | tip 67145a8ea2d3 == head OID of CLOSED PR #385; idle 34d > 14d window | `archive/pr385--devin/1780128383-inbound-check-response` |
| `devin/1780131969-inbound-check-response` | 52509a47f132 | 2026-05-31 | tip 52509a47f132 == head OID of CLOSED PR #386; idle 34d > 14d window | `archive/pr386--devin/1780131969-inbound-check-response` |
| `devin/1780298217-andon-verdict-D-E` | db17ffd63150 | 2026-06-01 | tip db17ffd63150 == head OID of CLOSED PR #418; idle 32d > 14d window | `archive/pr418--devin/1780298217-andon-verdict-D-E` |
| `devin/1780324280-andon-verdict-D-E-restack` | 25f1ac6bc484 | 2026-06-01 | tip 25f1ac6bc484 == head OID of CLOSED PR #429; idle 32d > 14d window | `archive/pr429--devin/1780324280-andon-verdict-D-E-restack` |
| `devin/1780328602-andon-verdict-restack2` | dc8b27f5c4a9 | 2026-06-01 | tip dc8b27f5c4a9 == head OID of CLOSED PR #433; idle 32d > 14d window | `archive/pr433--devin/1780328602-andon-verdict-restack2` |
| `devin/1780339778-andon-restack3` | 440dd4e5e8ea | 2026-06-01 | tip 440dd4e5e8ea == head OID of CLOSED PR #437; idle 32d > 14d window | `archive/pr437--devin/1780339778-andon-restack3` |
| `devin/1780340193-andon-restack4` | af200c33062d | 2026-06-01 | tip af200c33062d == head OID of CLOSED PR #438; idle 32d > 14d window | `archive/pr438--devin/1780340193-andon-restack4` |
| `devin/1780340889-andon-restack5` | 68b17cfc562d | 2026-06-01 | tip 68b17cfc562d == head OID of CLOSED PR #440; idle 32d > 14d window | `archive/pr440--devin/1780340889-andon-restack5` |
| `devin/1780342618-andon-restack6` | 8ef75c54a6bd | 2026-06-01 | tip 8ef75c54a6bd == head OID of CLOSED PR #441; idle 32d > 14d window | `archive/pr441--devin/1780342618-andon-restack6` |
| `devin/1780373801-andon-restack7` | 19cb6c5afd13 | 2026-06-02 | tip 19cb6c5afd13 == head OID of CLOSED PR #447; idle 32d > 14d window | `archive/pr447--devin/1780373801-andon-restack7` |
| `devin/1780410762-pr-janitor-session` | 0fdac59cf7cd | 2026-06-04 | tip 0fdac59cf7cd == head OID of CLOSED PR #451; idle 29d > 14d window | `archive/pr451--devin/1780410762-pr-janitor-session` |
| `devin/1780411107-pr-janitor-session` | 0bb3bb080576 | 2026-06-04 | tip 0bb3bb080576 == head OID of CLOSED PR #452; idle 29d > 14d window | `archive/pr452--devin/1780411107-pr-janitor-session` |
| `devin/1780414839-pr-janitor-session` | a18002a4d93b | 2026-06-04 | tip a18002a4d93b == head OID of CLOSED PR #454; idle 29d > 14d window | `archive/pr454--devin/1780414839-pr-janitor-session` |
| `devin/1780416467-pr-janitor-session` | 1a4e8a2703b1 | 2026-06-04 | tip 1a4e8a2703b1 == head OID of CLOSED PR #455; idle 29d > 14d window | `archive/pr455--devin/1780416467-pr-janitor-session` |
| `devin/1780418181-pr-janitor-session` | d125c4398000 | 2026-06-04 | tip d125c4398000 == head OID of CLOSED PR #456; idle 29d > 14d window | `archive/pr456--devin/1780418181-pr-janitor-session` |
| `devin/1780420386-pr-janitor-session` | 96526b9c9310 | 2026-06-04 | tip 96526b9c9310 == head OID of CLOSED PR #457; idle 29d > 14d window | `archive/pr457--devin/1780420386-pr-janitor-session` |
| `devin/1780422058-pr-janitor-session` | 999381326565 | 2026-06-04 | tip 999381326565 == head OID of CLOSED PR #458; idle 29d > 14d window | `archive/pr458--devin/1780422058-pr-janitor-session` |
| `devin/1780424084-pr-janitor-session` | ae4171fe5081 | 2026-06-04 | tip ae4171fe5081 == head OID of CLOSED PR #459; idle 29d > 14d window | `archive/pr459--devin/1780424084-pr-janitor-session` |
| `devin/1780548631-spine-a2a-adoption` | dfb5495fed1d | 2026-06-04 | tip dfb5495fed1d == head OID of CLOSED PR #469; idle 30d > 14d window | `archive/pr469--devin/1780548631-spine-a2a-adoption` |
| `devin/1780554948-vel-equivalence-matrix` | 1020aaa4db3f | 2026-06-04 | tip 1020aaa4db3f == head OID of CLOSED PR #472; idle 30d > 14d window | `archive/pr472--devin/1780554948-vel-equivalence-matrix` |
| `devin/2026-05-28-autonomous-expansion-audit` | 36787c071703 | 2026-05-28 | tip 36787c071703 == head OID of CLOSED PR #369; idle 34d > 14d window | `archive/pr369--devin/2026-05-28-autonomous-expansion-audit` |
| `devin/2026-05-29-research-organ-pivot` | 9a8ea0a6db97 | 2026-05-29 | tip 9a8ea0a6db97 == head OID of CLOSED PR #372; idle 34d > 14d window | `archive/pr372--devin/2026-05-29-research-organ-pivot` |
| `docs/canonical-drift-cleanup` | d802b07c061c | 2026-04-27 | tip d802b07c061c == head OID of CLOSED PR #44; idle 43d > 14d window | `archive/pr44--docs/canonical-drift-cleanup` |
| `feat/agent-chat-panel` | fcf7ecdb679d | 2026-04-04 | tip fcf7ecdb679d == head OID of CLOSED PR #17; idle 57d > 14d window | `archive/pr17--feat/agent-chat-panel` |
| `feat/brief-to-spec-seam-2026-05-07` | 76df0adfd1e7 | 2026-05-07 | tip 76df0adfd1e7 == head OID of CLOSED PR #159; idle 56d > 14d window | `archive/pr159--feat/brief-to-spec-seam-2026-05-07` |
| `feat/chetana-restoration-from-4c70456e` | a41149c2c555 | 2026-05-28 | tip a41149c2c555 == head OID of CLOSED PR #331; idle 34d > 14d window | `archive/pr331--feat/chetana-restoration-from-4c70456e` |
| `feat/go-evidence-sense-organ-v0` | a2741bef0810 | 2026-05-09 | tip a2741bef0810 == head OID of CLOSED PR #171; idle 56d > 14d window | `archive/pr171--feat/go-evidence-sense-organ-v0` |
| `feat/knowledge-ops-organ-seed` | 975eed5fd622 | 2026-05-11 | tip 975eed5fd622 == head OID of CLOSED PR #191; idle 43d > 14d window | `archive/pr191--feat/knowledge-ops-organ-seed` |
| `feat/memory-census` | 12b2e476fd60 | 2026-05-03 | tip 12b2e476fd60 == head OID of CLOSED PR #151; idle 43d > 14d window | `archive/pr151--feat/memory-census` |
| `feat/per-agent-chat-config-endpoints` | 12e2345068bf | 2026-04-04 | tip 12e2345068bf == head OID of CLOSED PR #16; idle 57d > 14d window | `archive/pr16--feat/per-agent-chat-config-endpoints` |
| `feat/persist-evidence-receipts` | f07018f17dca | 2026-06-11 | tip f07018f17dca == head OID of CLOSED PR #560; idle 23d > 14d window | `archive/pr560--feat/persist-evidence-receipts` |
| `feat/slop-verification-system` | bfdc3f822b1b | 2026-05-13 | tip bfdc3f822b1b == head OID of CLOSED PR #182; idle 43d > 14d window | `archive/pr182--feat/slop-verification-system` |
| `feature/agent-work-os-v0` | e6349f563921 | 2026-04-29 | tip e6349f563921 == head OID of CLOSED PR #55; idle 43d > 14d window | `archive/pr55--feature/agent-work-os-v0` |
| `feature/control-loop-hardening-chetana-rebase-needed` | ba90b5fa4913 | 2026-04-28 | tip ba90b5fa4913 == head OID of CLOSED PR #51; idle 66d > 14d window | `archive/pr51--feature/control-loop-hardening-chetana-rebase-needed` |
| `feature/operator-brief-first-tick-witness` | c186616072ca | 2026-05-05 | tip c186616072ca == head OID of CLOSED PR #92; idle 60d > 14d window | `archive/pr92--feature/operator-brief-first-tick-witness` |
| `fix-sql-injection-guardian-checks-7663364361950920885` | 646b7f7aa1a2 | 2026-05-21 | tip 646b7f7aa1a2 == head OID of CLOSED PR #329; idle 41d > 14d window | `archive/pr329--fix-sql-injection-guardian-checks-7663364361950920885` |
| `fix/false-affordance-purge` | 1108f63eb5a1 | 2026-04-04 | tip 1108f63eb5a1 == head OID of CLOSED PR #13; idle 57d > 14d window | `archive/pr13--fix/false-affordance-purge` |
| `fix/packaged-build-hardening` | 684bc3a887ee | 2026-04-04 | tip 684bc3a887ee == head OID of CLOSED PR #15; idle 57d > 14d window | `archive/pr15--fix/packaged-build-hardening` |
| `governance/inquiry-chain-phase1` | a79116314cd8 | 2026-05-06 | tip a79116314cd8 == head OID of CLOSED PR #58; idle 43d > 14d window | `archive/pr58--governance/inquiry-chain-phase1` |
| `governance/pr-lifecycle-2026-06-13` | fae835521d1f | 2026-06-13 | tip fae835521d1f == head OID of CLOSED PR #593; idle 19d > 14d window | `archive/pr593--governance/pr-lifecycle-2026-06-13` |
| `governance/spine-adoption-refresh-2026-06-13` | 6be533051394 | 2026-06-13 | tip 6be533051394 == head OID of CLOSED PR #591; idle 20d > 14d window | `archive/pr591--governance/spine-adoption-refresh-2026-06-13` |
| `integrate/chetana-grand-memory-2026-05-02` | 4c70456efa01 | 2026-05-07 | tip 4c70456efa01 == head OID of CLOSED PR #59; idle 43d > 14d window | `archive/pr59--integrate/chetana-grand-memory-2026-05-02` |
| `intel/decepticon-phase1` | 21e6698aa9b5 | 2026-04-28 | tip 21e6698aa9b5 == head OID of CLOSED PR #53; idle 57d > 14d window | `archive/pr53--intel/decepticon-phase1` |
| `ops/2026-06-03-run` | 7c2073a4b967 | 2026-06-03 | tip 7c2073a4b967 == head OID of CLOSED PR #460; idle 28d > 14d window | `archive/pr460--ops/2026-06-03-run` |
| `ops/governance-report-2026-06-14` | cb2b8dcc079a | 2026-06-14 | tip cb2b8dcc079a == head OID of CLOSED PR #595; idle 19d > 14d window | `archive/pr595--ops/governance-report-2026-06-14` |
| `ops/governance-spine-metric-refresh` | 98d0ed485948 | 2026-06-03 | tip 98d0ed485948 == head OID of CLOSED PR #466; idle 28d > 14d window | `archive/pr466--ops/governance-spine-metric-refresh` |
| `ops/pr-lifecycle-spine-2026-06-15T0000Z` | 339d23f823c5 | 2026-06-15 | tip 339d23f823c5 == head OID of CLOSED PR #606; idle 19d > 14d window | `archive/pr606--ops/pr-lifecycle-spine-2026-06-15T0000Z` |
| `ops/pr-lifecycle-spine-adoption-2026-06-14T1200Z` | 490fcbb3718d | 2026-06-14 | tip 490fcbb3718d == head OID of CLOSED PR #604; idle 19d > 14d window | `archive/pr604--ops/pr-lifecycle-spine-adoption-2026-06-14T1200Z` |
| `ops/run-report-2026-06-05T00Z` | 162907447942 | 2026-06-05 | tip 162907447942 == head OID of CLOSED PR #483; idle 28d > 14d window | `archive/pr483--ops/run-report-2026-06-05T00Z` |
| `ops/run-report-2026-06-05T06Z` | c6eb2a059d01 | 2026-06-05 | tip c6eb2a059d01 == head OID of CLOSED PR #485; idle 28d > 14d window | `archive/pr485--ops/run-report-2026-06-05T06Z` |
| `ops/run-report-2026-06-05T1200Z` | 98fd441b66cb | 2026-06-05 | tip 98fd441b66cb == head OID of CLOSED PR #491; idle 28d > 14d window | `archive/pr491--ops/run-report-2026-06-05T1200Z` |
| `ops/spine-adoption-2026-06-13` | ee5511d5e008 | 2026-06-13 | tip ee5511d5e008 == head OID of CLOSED PR #594; idle 19d > 14d window | `archive/pr594--ops/spine-adoption-2026-06-13` |
| `ops/spine-adoption-metric-2026-06-03` | dd80f76f5e1d | 2026-06-03 | tip dd80f76f5e1d == head OID of CLOSED PR #462; idle 28d > 14d window | `archive/pr462--ops/spine-adoption-metric-2026-06-03` |
| `ops/spine-adoption-metric-refresh-20260606` | 7a2d1216e569 | 2026-06-06 | tip 7a2d1216e569 == head OID of CLOSED PR #517; idle 27d > 14d window | `archive/pr517--ops/spine-adoption-metric-refresh-20260606` |
| `ops/spine-adoption-metric-refresh-20260606-060209` | 9068b99a9278 | 2026-06-06 | tip 9068b99a9278 == head OID of CLOSED PR #515; idle 27d > 14d window | `archive/pr515--ops/spine-adoption-metric-refresh-20260606-060209` |
| `ops/spine-adoption-refresh-2026-06-04T12` | 9443290a9a8e | 2026-06-04 | tip 9443290a9a8e == head OID of CLOSED PR #475; idle 28d > 14d window | `archive/pr475--ops/spine-adoption-refresh-2026-06-04T12` |
| `ops/spine-metric-refresh-2026-06-04` | ac52cc88c17a | 2026-06-04 | tip ac52cc88c17a == head OID of CLOSED PR #467; idle 28d > 14d window | `archive/pr467--ops/spine-metric-refresh-2026-06-04` |
| `oz/route-truth-audit-2026-04-04` | b9d52601f7d5 | 2026-04-04 | tip b9d52601f7d5 == head OID of CLOSED PR #14; idle 57d > 14d window | `archive/pr14--oz/route-truth-audit-2026-04-04` |
| `perf-async-roaming-daemon-7469302374074110265` | b921f226e2a1 | 2026-05-08 | tip b921f226e2a1 == head OID of CLOSED PR #168; idle 43d > 14d window | `archive/pr168--perf-async-roaming-daemon-7469302374074110265` |
| `perplexity-computer/mailbox-ack-to-claude-20260531` | fc0a2fe6239d | 2026-05-31 | tip fc0a2fe6239d == head OID of CLOSED PR #397; idle 34d > 14d window | `archive/pr397--perplexity-computer/mailbox-ack-to-claude-20260531` |
| `perplexity-computer/nest-1780023498` | 1f97dbf22dc9 | 2026-05-29 | tip 1f97dbf22dc9 == head OID of CLOSED PR #375; idle 34d > 14d window | `archive/pr375--perplexity-computer/nest-1780023498` |
| `pr91-review` | 6d0753860f4d | 2026-05-05 | tip 6d0753860f4d == head OID of CLOSED PR #152; idle 43d > 14d window | `archive/pr152--pr91-review` |
| `spine-grounding/slice-1-adoption-gate` | b8990c4bfc04 | 2026-06-01 | tip b8990c4bfc04 == head OID of CLOSED PR #443; idle 32d > 14d window | `archive/pr443--spine-grounding/slice-1-adoption-gate` |
| `spine-grounding/slice-2-runtime-recovery` | 6564af509686 | 2026-06-02 | tip 6564af509686 == head OID of CLOSED PR #444; idle 32d > 14d window | `archive/pr444--spine-grounding/slice-2-runtime-recovery` |
| `spine-grounding/slice-3-tollbooth-gateway` | e558ac92c49d | 2026-06-02 | tip e558ac92c49d == head OID of CLOSED PR #445; idle 32d > 14d window | `archive/pr445--spine-grounding/slice-3-tollbooth-gateway` |
| `tests/spine-persistence-invariant` | a8292ba6e42a | 2026-06-04 | tip a8292ba6e42a == head OID of CLOSED PR #473; idle 30d > 14d window | `archive/pr473--tests/spine-persistence-invariant` |
| `wiring/archive-build-loop-2026-05-07` | 3dabc6225ad3 | 2026-05-06 | tip 3dabc6225ad3 == head OID of CLOSED PR #142; idle 43d > 14d window | `archive/pr142--wiring/archive-build-loop-2026-05-07` |
| `wiring/triage-cron-job-runtime-2026-05-07` | 19fc8ce76630 | 2026-05-06 | tip 19fc8ce76630 == head OID of CLOSED PR #145; idle 43d > 14d window | `archive/pr145--wiring/triage-cron-job-runtime-2026-05-07` |
| `wiring/triage-roaming-dispatch-2026-05-07` | 9133360edd9e | 2026-05-06 | tip 9133360edd9e == head OID of CLOSED PR #143; idle 43d > 14d window | `archive/pr143--wiring/triage-roaming-dispatch-2026-05-07` |

## Operator review — tip moved after PR (9)

| branch | tip | last commit | evidence |
|---|---|---|---|
| `chore/governance/hygiene-lifecycle-v2` | 144a7df80e90 | 2026-06-11 | PR history #551(MERGED) but tip 144a7df80e90 matches no PR head OID (re-pushed after close/merge) — operator review |
| `chore/phase2-governance-isolation` | f1ad783f2fc6 | 2026-05-05 | PR history #75(CLOSED) but tip f1ad783f2fc6 matches no PR head OID (re-pushed after close/merge) — operator review |
| `claude/a2a-nats-review-test-ncol7c` | 6fc007994f30 | 2026-07-01 | PR history #729(MERGED) but tip 6fc007994f30 matches no PR head OID (re-pushed after close/merge) — operator review |
| `claude/todo-implementation-JXjD1` | 5565375cbb93 | 2026-05-31 | PR history #339(MERGED) but tip 5565375cbb93 matches no PR head OID (re-pushed after close/merge) — operator review |
| `codex/kaizen-exec-loop-20260601` | 4d66682e1d11 | 2026-06-01 | PR history #431(MERGED) but tip 4d66682e1d11 matches no PR head OID (re-pushed after close/merge) — operator review |
| `codex/local-risk-final-boss-20260702` | 41b5dc6bd259 | 2026-07-04 | PR history #750(MERGED) but tip 41b5dc6bd259 matches no PR head OID (re-pushed after close/merge) — operator review |
| `devin/1778385929-revenue-cell-v0` | 825021d8b6d6 | 2026-05-11 | PR history #184(CLOSED) but tip 825021d8b6d6 matches no PR head OID (re-pushed after close/merge) — operator review |
| `devin/1782374246-reconcile-693-pudgala` | e3cdef10e663 | 2026-06-25 | PR history #696(CLOSED) but tip e3cdef10e663 matches no PR head OID (re-pushed after close/merge) — operator review |
| `feat/board-feedback-edge` | 8fa7b1fe061c | 2026-05-09 | PR history #166(CLOSED) but tip 8fa7b1fe061c matches no PR head OID (re-pushed after close/merge) — operator review |

## Operator review — never PR'd, idle (37)

| branch | tip | last commit | evidence |
|---|---|---|---|
| `archive/tcs-heartbeat-main-diverged-20260511` | c74e7d24aea9 | 2026-04-22 | no PR ever; tip idle 73d > 30d window; no hard evidence — operator review |
| `backup/pr-48-pre-rebase-ba90b5f` | ba90b5fa4913 | 2026-04-28 | no PR ever; tip idle 67d > 30d window; no hard evidence — operator review |
| `base/brief-to-spec-seam-018ef60` | 018ef604a354 | 2026-05-06 | no PR ever; tip idle 58d > 30d window; no hard evidence — operator review |
| `chore/agent-truth-spine` | fdd97f4bf545 | 2026-05-05 | no PR ever; tip idle 60d > 30d window; no hard evidence — operator review |
| `chore/governance-canon-refresh` | b65d7639df08 | 2026-05-05 | no PR ever; tip idle 60d > 30d window; no hard evidence — operator review |
| `chore/phase2-governance-rollup` | 2f988e09cc60 | 2026-05-04 | no PR ever; tip idle 60d > 30d window; no hard evidence — operator review |
| `chore/semgrep-hardening` | d2df71b5254d | 2026-05-04 | no PR ever; tip idle 60d > 30d window; no hard evidence — operator review |
| `claude/structure-prompts-I4uPi` | e1257b42f730 | 2026-03-18 | no PR ever; tip idle 107d > 30d window; no hard evidence — operator review |
| `cleanup/identity-onboarding-2026-05-12` | e7c7535fc7c4 | 2026-05-12 | no PR ever; tip idle 52d > 30d window; no hard evidence — operator review |
| `cleanup/mixed-quality-recovery-2026-05-10` | d031f6ee39bc | 2026-05-10 | no PR ever; tip idle 54d > 30d window; no hard evidence — operator review |
| `cleanup/route-witness-2026-05-12` | 252beccd8442 | 2026-05-12 | no PR ever; tip idle 52d > 30d window; no hard evidence — operator review |
| `codex/module-metabolism-strategy` | bf180444fab9 | 2026-05-05 | no PR ever; tip idle 59d > 30d window; no hard evidence — operator review |
| `codex/slop-verification-main` | 056b01f0330b | 2026-05-10 | no PR ever; tip idle 54d > 30d window; no hard evidence — operator review |
| `converge/kimi-claw-registration-20260428` | 8d872b52eed8 | 2026-05-05 | no PR ever; tip idle 60d > 30d window; no hard evidence — operator review |
| `copilot/build-three-connectors` | ad4d8de7641a | 2026-05-20 | no PR ever; tip idle 44d > 30d window; no hard evidence — operator review |
| `cutover/lf5-runtime-on-main-20260510` | 4a31d0e7849d | 2026-05-10 | no PR ever; tip idle 54d > 30d window; no hard evidence — operator review |
| `design/routing-fusion-spine` | 5781c0f12fad | 2026-05-10 | no PR ever; tip idle 54d > 30d window; no hard evidence — operator review |
| `devin/1780023669-verdict-clean` | 166bb7b92e4c | 2026-05-29 | no PR ever; tip idle 36d > 30d window; no hard evidence — operator review |
| `experiments/mask-rv-whitebox-prereg` | a47574e3a512 | 2026-05-14 | no PR ever; tip idle 50d > 30d window; no hard evidence — operator review |
| `feat/a2a-correlation-spine-phase2a` | 98d9cf41656c | 2026-05-28 | no PR ever; tip idle 36d > 30d window; no hard evidence — operator review |
| `feat/chetana-grand-memory` | 690020c3fc3b | 2026-05-06 | no PR ever; tip idle 59d > 30d window; no hard evidence — operator review |
| `feat/gauntlet-external-outcome-rewire` | b14e125d45f3 | 2026-05-12 | no PR ever; tip idle 53d > 30d window; no hard evidence — operator review |
| `feat/governed-recursive-proof-v0` | 37424404db65 | 2026-05-17 | no PR ever; tip idle 48d > 30d window; no hard evidence — operator review |
| `feat/gplot-lodestone-seed` | 776a01fc12b1 | 2026-05-12 | no PR ever; tip idle 52d > 30d window; no hard evidence — operator review |
| `feature/ontology-native-command-brief-v0` | d34790ffa1a7 | 2026-04-30 | no PR ever; tip idle 65d > 30d window; no hard evidence — operator review |
| `governance/tier-1-install` | 43f62a33d824 | 2026-05-02 | no PR ever; tip idle 63d > 30d window; no hard evidence — operator review |
| `lf5-live-fire-clean` | 9d6a34500480 | 2026-04-10 | no PR ever; tip idle 84d > 30d window; no hard evidence — operator review |
| `research/encapsulation-language-strategy-room` | 86b4c433dac2 | 2026-04-30 | no PR ever; tip idle 65d > 30d window; no hard evidence — operator review |
| `research/persistent-agents-2026-05` | aa48a1f762c4 | 2026-05-20 | no PR ever; tip idle 45d > 30d window; no hard evidence — operator review |
| `review/proof-artifacts-2026-05-12` | 6f6603c043a5 | 2026-05-12 | no PR ever; tip idle 52d > 30d window; no hard evidence — operator review |
| `roaming-bridge-20260326` | 221ba6a0fc7e | 2026-03-26 | no PR ever; tip idle 99d > 30d window; no hard evidence — operator review |
| `roaming-daemon-20260326` | 3330dc86cd67 | 2026-03-26 | no PR ever; tip idle 99d > 30d window; no hard evidence — operator review |
| `roaming-fixall-20260326` | 5f64f51e33fa | 2026-03-26 | no PR ever; tip idle 99d > 30d window; no hard evidence — operator review |
| `roaming-mailbox-live-20260326` | 27b29f66a3a3 | 2026-03-26 | no PR ever; tip idle 99d > 30d window; no hard evidence — operator review |
| `stabilize/dharma-safe-clean` | 1fc6f5d43f55 | 2026-03-19 | no PR ever; tip idle 107d > 30d window; no hard evidence — operator review |
| `worker4/pr323-codeql` | b286943111e9 | 2026-05-24 | no PR ever; tip idle 41d > 30d window; no hard evidence — operator review |
| `worker4/pr332-codeql` | e8ab4bed0d0c | 2026-05-24 | no PR ever; tip idle 41d > 30d window; no hard evidence — operator review |

## Waiting — inside idle window (30)

| branch | tip | last commit | evidence |
|---|---|---|---|
| `chore/governance-spine-adoption-2026-06-22T0600Z` | 5a64d63c87b8 | 2026-06-22 | tip 5a64d63c87b8 == head OID of CLOSED PR #666; idle 11d <= 14d window |
| `chore/governance/ops-report-20260622T1804Z` | 3d62d933027a | 2026-06-22 | tip 3d62d933027a == head OID of CLOSED PR #669; idle 10d <= 14d window |
| `chore/governance/spine-adoption-metric-20260622T1802Z` | dbb9371f0b88 | 2026-06-22 | tip dbb9371f0b88 == head OID of CLOSED PR #668; idle 10d <= 14d window |
| `chore/refresh-spine-adoption-metric-20260622` | db638bde071a | 2026-06-22 | tip db638bde071a == head OID of CLOSED PR #665; idle 11d <= 14d window |
| `claude/refine-local-plan-ae8dw1` | 612562da9780 | 2026-06-25 | tip 612562da9780 == head OID of CLOSED PR #690; idle 8d <= 14d window |
| `claude/seeing-organ-2je1gw` | 3f04d6a4549b | 2026-06-22 | tip 3f04d6a4549b == head OID of CLOSED PR #662; idle 11d <= 14d window |
| `claude/slack-session-99qb83` | d0977371dbb2 | 2026-06-25 | tip d0977371dbb2 == head OID of CLOSED PR #694; idle 9d <= 14d window |
| `devin/1781340172-bug-corral` | 07d84f0943c4 | 2026-06-18 | tip 07d84f0943c4 == head OID of CLOSED PR #592; idle 14d <= 14d window |
| `devin/full-swarm-e2e-test-20260621` | e4adb3b00281 | 2026-06-21 | tip e4adb3b00281 == head OID of CLOSED PR #661; idle 9d <= 14d window |
| `gpt55/module-diet-census-20260619` | a5672f85be34 | 2026-06-19 | tip a5672f85be34 == head OID of CLOSED PR #643; idle 9d <= 14d window |
| `ops/governance-report-2026-06-18` | c4f5fc49e7e1 | 2026-06-18 | tip c4f5fc49e7e1 == head OID of CLOSED PR #642; idle 10d <= 14d window |
| `ops/ops-report-2026-06-29T0600Z` | 49ad57aa489b | 2026-06-29 | tip 49ad57aa489b == head OID of CLOSED PR #722; idle 4d <= 14d window |
| `ops/report-2026-06-19T1800Z` | d1a19bc1392c | 2026-06-19 | tip d1a19bc1392c == head OID of CLOSED PR #645; idle 11d <= 14d window |
| `ops/report-2026-06-21T1200Z` | 4ba721644bcf | 2026-06-21 | tip 4ba721644bcf == head OID of CLOSED PR #659; idle 11d <= 14d window |
| `ops/report-2026-06-21T1800Z` | daa29b2dcb6b | 2026-06-21 | tip daa29b2dcb6b == head OID of CLOSED PR #664; idle 11d <= 14d window |
| `ops/report-2026-06-22T1200Z` | fdd2cbaaff75 | 2026-06-22 | tip fdd2cbaaff75 == head OID of CLOSED PR #667; idle 11d <= 14d window |
| `ops/report-2026-06-23T0600Z` | 2be905b6bf03 | 2026-06-23 | tip 2be905b6bf03 == head OID of CLOSED PR #676; idle 9d <= 14d window |
| `ops/report-2026-06-23T1800Z` | 88a059e6b2a7 | 2026-06-23 | tip 88a059e6b2a7 == head OID of CLOSED PR #681; idle 9d <= 14d window |
| `ops/report-2026-06-24T1800Z` | f5da9f4bd3bf | 2026-06-24 | tip f5da9f4bd3bf == head OID of CLOSED PR #686; idle 9d <= 14d window |
| `ops/report-2026-06-25T0000Z` | ec067c98eab9 | 2026-06-25 | tip ec067c98eab9 == head OID of CLOSED PR #687; idle 8d <= 14d window |
| `ops/report-2026-06-26T0000Z` | a375b417c922 | 2026-06-26 | tip a375b417c922 == head OID of CLOSED PR #706; idle 4d <= 14d window |
| `ops/report-2026-06-26T1800Z` | f75b7c263e3b | 2026-06-26 | tip f75b7c263e3b == head OID of CLOSED PR #714; idle 4d <= 14d window |
| `ops/report-2026-06-27T0000Z` | f23e3f110773 | 2026-06-27 | tip f23e3f110773 == head OID of CLOSED PR #715; idle 4d <= 14d window |
| `ops/report-2026-06-27T1800Z` | 025241df4c97 | 2026-06-27 | tip 025241df4c97 == head OID of CLOSED PR #717; idle 4d <= 14d window |
| `ops/report-2026-06-28T1800Z` | 17e87b363c6b | 2026-06-28 | tip 17e87b363c6b == head OID of CLOSED PR #720; idle 4d <= 14d window |
| `ops/spine-adoption-2026-06-20T0600Z` | 95ac669dfe70 | 2026-06-20 | tip 95ac669dfe70 == head OID of CLOSED PR #649; idle 11d <= 14d window |
| `ops/spine-adoption-2026-06-21T0600Z` | 038b2390b410 | 2026-06-21 | tip 038b2390b410 == head OID of CLOSED PR #653; idle 11d <= 14d window |
| `oz/spine-metric-refresh-2026-06-26` | ae7c0c798f92 | 2026-06-26 | tip ae7c0c798f92 == head OID of CLOSED PR #708; idle 4d <= 14d window |
| `preserve/forge-v1-tokenbroker-scoreboard-20260623` | d8bca7aab20a | 2026-06-20 | tip d8bca7aab20a == head OID of CLOSED PR #680; idle 10d <= 14d window |
| `preserve/loop-closure-supplychain-bronze-20260623` | 11de04fb743f | 2026-06-20 | tip 11de04fb743f == head OID of CLOSED PR #679; idle 10d <= 14d window |

## Exempt — branch registry (3)

| branch | tip | last commit | evidence |
|---|---|---|---|
| `agent/magpie-seed` | f9ae3ae63471 | 2026-07-02 | registry branch `agent/magpie-seed`: Live daemon lineage; operator primary checkout and dw-worktrees/mem branch off it (dive section 2) |
| `feat/rsi-lab` | 569187fac07a | 2026-07-04 | registry branch `feat/rsi-lab`: Active research lane, 58 ahead, live worktree ds_forge_spine_v0 (dive section 4 KEEP) |
| `telos_titanium/dharma_lane_research` | 738b463160f6 | 2026-07-04 | registry pattern `telos_titanium/*`: Titanium research lane: PR 773 naga_ir plus dharma_lane_research feed (dive section 3) |

## Protected (20)

| branch | tip | last commit | evidence |
|---|---|---|---|
| `chore/docops-autorefresh` | b65dafa185e9 | 2026-07-04 | head of OPEN PR #776 |
| `ci/automerge-honesty` | 86caffba6ae8 | 2026-07-04 | head of OPEN PR #782 |
| `ci/coherence-delta-teeth` | 7b8f8729c08a | 2026-07-04 | head of OPEN PR #780 |
| `ci/nightly-full-suite` | c65829b3351d | 2026-07-04 | head of OPEN PR #778 |
| `fix/council-loop-aware-completion` | 04a42f095e7d | 2026-07-04 | head of OPEN PR #775 |
| `fix/vector-store-rule10-embedders` | 782794618f8e | 2026-07-04 | head of OPEN PR #774 |
| `governance/evict-derived-status` | 0c73b874ae33 | 2026-07-04 | head of OPEN PR #783 |
| `governance/pramana-gates-fix` | b2d2fcdb0a90 | 2026-07-04 | head of OPEN PR #779 |
| `governance/pudgala-p0-p1` | 2f5805fd568b | 2026-07-04 | head of OPEN PR #781 |
| `governance/ratchet-code-moves` | c71084573af4 | 2026-07-04 | head of OPEN PR #777 |
| `main` | e28b253050b0 | 2026-07-04 | default branch — never touched |
| `telos_titanium/naga_ir` | a1d45269b687 | 2026-07-04 | head of OPEN PR #773 |
| `titanium/phase-0-kernel-skeleton` | eaed7adc1566 | 2026-07-04 | head of OPEN PR #763 |
| `titanium/phase-1a-signing-path` | c78d5f6082ec | 2026-07-03 | head of OPEN PR #764 |
| `titanium/phase-1b-result-type` | 8b3a76147acb | 2026-07-03 | head of OPEN PR #765 |
| `titanium/phase-1c-io-rim` | 0d3129a8e2c7 | 2026-07-03 | head of OPEN PR #766 |
| `titanium/phase-1d-titanium-verify` | f9aead240784 | 2026-07-03 | head of OPEN PR #767 |
| `titanium/phase-1e-ci-wiring` | 47194c39d541 | 2026-07-03 | head of OPEN PR #768 |
| `weaver/br003-orgcode-ratchet-spec` | 724fbcb9dee4 | 2026-07-03 | head of OPEN PR #769 |
| `weaver/waste-recycling` | 500d26076b4e | 2026-07-03 | head of OPEN PR #770 |

## Active (37)

Recent branches with no PR history; listed by name only to keep the receipt bounded.

- `archive/ratchet-loop-phases-1-3-dirty-20260702` (tip idle 2d — in use)
- `archive/supplychain-bronze-dirty-20260702` (tip idle 2d — in use)
- `capital-lab/build` (tip idle 23d — in use)
- `cashclaw/revenue-hydra-v1` (tip idle 20d — in use)
- `claude/debug-corral` (tip idle 6d — in use)
- `claude/learned-auditable-orchestrator` (tip idle 11d — in use)
- `claude/ontology-lattice-reconciliation` (tip idle 9d — in use)
- `claude/tracks-consolidation-grading-nb67lq` (tip idle 11d — in use)
- `cleanup/memory-kernel-preflight-lane-2026-05-16` (tip idle 23d — in use)
- `cleanup/recursive-evolution-lane-2026-05-16` (tip idle 23d — in use)
- `codex/a2a-active-track-20260613` (tip idle 21d — in use)
- `codex/live-ops-cockpit-v2-slice-d` (tip idle 29d — in use)
- `codex/pr570-orientation-fixes` (tip idle 22d — in use)
- `codex/runtime-truth-spine-v1` (tip idle 23d — in use)
- `codex/verifier-ranker-v0-closeout-20260701T150440Z` (tip idle 2d — in use)
- `docs/swarm-substrate-spec-2026-05-20` (tip idle 23d — in use)
- `feat/governed-recursive-proof-tightening` (tip idle 22d — in use)
- `feat/operator-idea-spark-ingest` (tip idle 3d — in use)
- `fix/chetana-wiki-multiroot` (tip idle 26d — in use)
- `forge-v1/tokenbroker-scoreboard-20260620` (tip idle 14d — in use)
- `generated/status` (tip idle 0d — in use)
- `gpt55/high-roi-spine-mcp-orchestrator-20260620` (tip idle 13d — in use)
- `helm/worldclass-20260612` (tip idle 17d — in use)
- `honest-spine-v2` (tip idle 23d — in use)
- `lak-e2e` (tip idle 27d — in use)
- `opus-identity-levelup` (tip idle 23d — in use)
- `opus/traverse-fix-20260605` (tip idle 22d — in use)
- `organ/03-seat` (tip idle 23d — in use)
- `perplexity/bug-corral-arbiter-packet` (tip idle 20d — in use)
- `preserve/runtime-truth-nats-rebuild-preflight-20260623` (tip idle 15d — in use)
- `preserve/sandbox-uniques-2026-06-24` (tip idle 9d — in use)
- `recover/dharma-capital-2026-06-24` (tip idle 10d — in use)
- `repair/pr-323-dkeys` (tip idle 23d — in use)
- `rescue/provenance-sentinel-go-track-20260612` (tip idle 22d — in use)
- `telos-ai-seed-v0-from-sandbox` (tip idle 17d — in use)
- `vps/kimi-routing-restore-2026-07-03` (tip idle 0d — in use)
- `worktree-holon-agent` (tip idle 26d — in use)


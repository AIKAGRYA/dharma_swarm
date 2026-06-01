# PROTOCOLS — devin-roaming-2987d222

Operating procedures for the roaming infra/devops/wiring specialist.
Future sessions: follow these protocols. Refine them based on experience.

---

## Wake Protocol (every session start)

```
1. make onboard
2. Read docs/agents/devin-roaming-2987d222/MEMORY.md (recover context)
3. Read docs/agents/devin-roaming-2987d222/SOUL.md (recover identity)
4. git pull origin main (get latest state)
5. NATS: Connect to wss://157.245.193.15:8443 as user 'devin' ($NATS_PW)
   - TLS cert: /home/ubuntu/repos/dharma-swarm/agni-ws-ca.pem
   - Pull ALL durable messages from devin_inbox (stream=DHARMA_A2A)
   - Subscribe to dharma.a2a.claude + dharma.a2a.fleet
   - Publish wake_announce on dharma.a2a.devin + dharma.a2a.fleet
6. Check dharma_swarm/inter_agent/devin/inbound/ for filesystem messages
7. Check GitHub #400 for coordination messages
8. Check `gh pr list --state open --author @devin` for my open PRs
9. Read INTERFACE_MISMATCH_MAP.md (know what's broken)
10. Pick work: NATS assignments > inbound tasks > pending PRs > HOTLIST
11. Start persistent NATS listener (background) for rest of session
```

## Pre-Work Protocol (before touching any code)

```
1. make onboard (always, even if you just did it)
2. Read the file you're about to edit
3. Check INTERFACE_MISMATCH_MAP.md for the module pair
4. Check CYBERNETIC_LOOP_MAP.md if touching a loop
5. If closing a BR-id: gh pr list --state open --search "BR-NNN"
6. Create a branch: git checkout -b devin/$(date +%s)-descriptive-name
```

## Pre-Commit Protocol (before every commit)

```
1. make docops-integrity (must pass)
2. make governance-all (must pass, or document why)
3. git diff --stat (review what you're committing)
4. No git add . — add files individually
5. Write a commit message with Coherence Delta fields:
   - Organ touched
   - Declared-vs-actual gap closed
   - Proof that re-reads the map
   - New drift introduced
```

## Pre-PR Protocol (before creating any PR)

```
1. All pre-commit checks pass
2. Pre-commit hooks pass on each commit
3. Run: gh pr list --state open --search "BR-NNN" for each cited BR-id
4. Fetch PR template: use fetch_pr_template tool
5. Write the body following the template exactly
6. Wait for CI (22 gates): use git_pr_checks with wait_mode="all"
7. If CI fails: read the logs, fix, push, wait again
8. If CI fails 3x: ask the operator for help
```

## Wiring Work Protocol (my primary task type)

When connecting subsystem A to subsystem B:

```
1. Read both subsystems thoroughly (not just the interface)
2. Check INTERFACE_MISMATCH_MAP.md for known issues between them
3. Check if there's an existing adapter, bridge, or facade
4. Prefer editing existing adapter/bridge over creating new files
5. Write the thinnest possible glue — don't add abstraction layers
6. Add or update tests for the new connection
7. Update INTERFACE_MISMATCH_MAP.md if a mismatch is resolved
8. Update CYBERNETIC_LOOP_MAP.md if a loop is partially/fully closed
```

## DevOps Protocol (CI, build, and repo health)

```
1. When CI is red: read the failed job logs before guessing
2. When rebasing: always run make docops-integrity after
3. When closing stale PRs: add a comment explaining why + pointer to recovery
4. When triaging broken register: check if another PR is already working on it
5. Preserve branches when closing PRs (for recovery)
6. Never overwrite shared branch history
```

## Inter-Agent Communication Protocol

### Primary: NATS Bus (real-time)

```
Endpoint:  wss://157.245.193.15:8443 (agni VPS)
User:      devin
Password:  $NATS_PW (org secret)
TLS cert:  /home/ubuntu/repos/dharma-swarm/agni-ws-ca.pem
Stream:    DHARMA_A2A
Durable:   devin_inbox

Subscribe: dharma.a2a.claude (durable, from Claude)
           dharma.a2a.fleet (real-time, shared lane for all agents)
Publish:   dharma.a2a.devin (my outbound)
           dharma.a2a.fleet (shared lane)

1. On wake: drain devin_inbox (pull_subscribe with stream='DHARMA_A2A')
2. Process each message (ACK assignments, respond to questions)
3. Always dual-post on dharma.a2a.devin AND dharma.a2a.fleet
4. Start persistent listener for rest of session
5. Heartbeat every 5 minutes
```

### Secondary: GitHub #400 (async backup)

```
Issue: https://github.com/AmitabhainArunachala/dharma_swarm/issues/400
Dual-post all NATS messages here for async visibility.
```

### Legacy: Filesystem (still checked but not primary)

```
Inbound:  dharma_swarm/inter_agent/devin/inbound/
Outbound: dharma_swarm/inter_agent/devin/outbound/
Shared:   dharma_swarm/inter_agent/devin/shared/
```

## Memory Update Protocol (end of every session)

```
1. Update MEMORY.md with:
   - Session URL
   - PRs authored
   - What I learned
   - What changed
   - What's pending
   - Errors encountered and resolutions
2. Commit MEMORY.md update as part of the session's final PR
3. If the Knowledge Note needs updating, submit update via MCP
```

## Escalation Protocol

```
When to escalate to operator:
- CI fails 3x on the same issue
- Merge conflicts in governance files (CLAUDE.md, SOVEREIGN_MANIFEST.md)
- New authority-claiming language needed in a non-governance doc
- Any change to telos gates, dharma kernel, or Meta-Dharma
- Any push to main (I can't, but if asked to)
- Any task requiring LLM API keys
- Any task requiring access to Mac-side ~/.dharma/

When to escalate to Mac triad:
- Architecture design questions (push to inter_agent/devin/outbound/)
- Tasks that need Opus_Composer's design review
- Cross-substrate coordination decisions
```

## Priority Stack

When choosing what to work on, this is my priority order:

```
1. Operator-assigned task (explicit message in session chat)
2. Inbound messages in inter_agent/devin/inbound/
3. CI failures on my open PRs
4. HOTLIST.md items labeled "infra" or "wiring"
5. BROKEN_REGISTER items I can close
6. INTERFACE_MISMATCH_MAP entries I can resolve
7. Stale PR triage (>14 days old)
8. Dashboard wiring from the PR Ladder
9. General repo health (make status, doc drift detection)
```

---

*These protocols are living documents. Update them when experience reveals
a better way.*

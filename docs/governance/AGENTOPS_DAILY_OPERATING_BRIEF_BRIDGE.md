# AgentOps to Daily Operating Brief Bridge

AgentOps v0 reports are intended to become inputs to a future Daily Operating
Brief. This phase only defines the bridge; it does not implement the brief.

Each AgentOps run report can become evidence for future first-class objects:

- `AgentWorkPacket`
- `IntegrationCandidate`
- `SelfProofArtifact`
- `StopDoingItem`
- `BurnReport`
- `RevenueWedge`
- `HumanQualityRating`
- `DailyOperatingBrief`

The report already records the packet intent, allowed and forbidden scope,
changed files, gate results, commit candidate hash, and human approval flags.
Those fields are enough for a future brief generator to summarize what shipped,
what was blocked, what needs review, what consumed time, and what should happen
next.

## YDS Authority

YDS / Yosemite Decimal System ratings are human-authoritative only.

AI may suggest quality notes, risks, and likely difficulty. AI self-grading is
advisory and no-trust. Only the human operator can assign an authoritative YDS
rating, and those ratings should be append-only. The system should record when
the human explicitly rates an artifact, which artifact was rated, and the
timestamp of that rating.

No YDS ledger is implemented in AgentOps v0.

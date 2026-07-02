package main

// Beat is a named research topic swept via the existing query-source
// machinery (SourcesForQueries) rather than a new fetch mechanism. Each beat
// expands into real hn_algolia/github_repos/arxiv/reddit sources -- no new
// source *kind* is introduced here, only a curated grouping of *what to ask*.
type Beat struct {
	ID      string
	Name    string
	Queries []string
}

const MaxDeepSweepBeatSources = 16

// DefaultBeats returns a DELIBERATELY CAPPED set of curated research beats
// for the (separate, lower-cadence) deep sweep -- roughly ten, not the ~28
// angles a one-off manual research run used. "Capped for now": widen only
// after the cadence and downstream verification cost are proven out in
// practice, rather than growing this literal list first.
func DefaultBeats() []Beat {
	return []Beat{
		{ID: "multi_agent_debate_correlation", Name: "Multi-agent debate & correlated-error theory", Queries: []string{"multi-agent debate correlated errors LLM 2026"}},
		{ID: "judge_panel_bias", Name: "LLM judge panel bias and independence", Queries: []string{"LLM judge panel bias correlated errors 2026"}},
		{ID: "ringelmann_team_scaling", Name: "Multi-agent team-size scaling laws", Queries: []string{"multi-agent LLM scaling law team size 2026"}},
		{ID: "heterogeneous_ensemble_diversity", Name: "Heterogeneous ensemble diversity gains", Queries: []string{"heterogeneous LLM ensemble diversity benchmark 2026"}},
		{ID: "self_improving_agents", Name: "Self-improving / self-modifying agent systems", Queries: []string{"self-improving agent system Darwin Godel machine 2026"}},
		{ID: "agent_memory_context", Name: "Agent memory, sleep-time compute, context engineering", Queries: []string{"agent memory context engineering compaction 2026"}},
		{ID: "agentic_engineering_design_patterns", Name: "Agentic engineering and design patterns", Queries: []string{"agentic engineering design patterns agents 2026"}},
		{ID: "agent_protocols_orchestration", Name: "Agent protocols and orchestration infrastructure", Queries: []string{"agent orchestration protocol MCP A2A 2026"}},
		{ID: "production_incidents_safety", Name: "Autonomous agent production incidents", Queries: []string{"autonomous agent production incident safety 2026"}},
		{ID: "benchmark_trust_crisis", Name: "Agent benchmark trust and reward hacking", Queries: []string{"agent benchmark reward hacking trust crisis 2026"}},
		{ID: "agentic_rl_training", Name: "Agentic RL training (RLVR/GRPO)", Queries: []string{"agentic reinforcement learning RLVR GRPO 2026"}},
	}
}

// BeatSources expands every beat's queries into real Source entries via the
// existing SourcesForQueries helper (the same one cascade queries already
// use -- no new fetch-kind logic). Each generated source's CascadeFor is set
// to the beat ID, so downstream analysis can attribute a signal back to the
// beat that found it without a new field.
func BeatSources(beats []Beat) []Source {
	var out []Source
	for _, beat := range beats {
		out = append(out, SourcesForQueries(beat.Queries, beat.ID)...)
	}
	return out
}

// sourceKindsPerQuery mirrors SourcesForQueries: every query always expands
// to exactly 4 sources in this fixed order (hn, github, arxiv, reddit).
const sourceKindsPerQuery = 4

func DeepSweepBeatSources(beats []Beat, maxSources int) []Source {
	if maxSources <= 0 {
		return []Source{}
	}
	// Round-robin across beats (one source per beat per round) rather than
	// truncating BeatSources' beat-by-beat concatenation: each beat expands
	// into 4 sources (SourcesForQueries: hn/github/arxiv/reddit), so a flat
	// sources[:maxSources] only ever covers the first maxSources/4 beats and
	// silently starves the rest of DefaultBeats() forever (Copilot review
	// finding, beats.go:57).
	perBeat := make([][]Source, len(beats))
	for i, beat := range beats {
		sources := SourcesForQueries(beat.Queries, beat.ID)
		// Every beat's sources start in the same fixed kind order
		// (hn/github/arxiv/reddit), so round 0 of the round-robin below would
		// take EVERY beat's hn source before any beat's github/arxiv/reddit
		// source is ever reached -- under a tight cap (e.g. 16 for 10 beats),
		// arxiv/reddit get zero representation across the whole beat set
		// (Codex review finding, beats.go:13). Stagger each beat's starting
		// kind by its index so a single round already mixes kinds.
		if n := len(sources); n > 0 {
			rotation := i % sourceKindsPerQuery
			rotated := make([]Source, n)
			for j := range sources {
				rotated[j] = sources[(j+rotation)%n]
			}
			sources = rotated
		}
		perBeat[i] = sources
	}
	out := make([]Source, 0, maxSources)
	for round := 0; len(out) < maxSources; round++ {
		addedThisRound := false
		for _, sources := range perBeat {
			if round >= len(sources) {
				continue
			}
			out = append(out, sources[round])
			addedThisRound = true
			if len(out) == maxSources {
				return out
			}
		}
		if !addedThisRound {
			break
		}
	}
	return out
}

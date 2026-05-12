package main

import "strings"

func FirstPrinciplesQuestions() []string {
	return []string{
		"What new constraint, capability, or demand does this signal reveal?",
		"What underlying pattern makes this possible now?",
		"Which part of our current substrate becomes more valuable or more obsolete?",
		"What would we build if we treated this as a law of the market, not a news item?",
		"Which customer, operator, or agent pain does this signal resolve more directly than current approaches?",
		"What hidden cost curve, latency curve, capability curve, or trust curve is moving?",
		"What can we verify independently within one day?",
		"What adjacent signals would confirm this is a movement rather than an isolated launch?",
		"What would make this dangerous, noisy, or strategically irrelevant?",
		"What small compounding artifact should exist tomorrow because we noticed this?",
	}
}

func IterationSteps() []string {
	return []string{
		"Capture the source, source date, claims, and provenance as a durable world signal.",
		"Verify primary claims against official docs, benchmarks, papers, repos, and third-party commentary.",
		"Extract the first-principles shift: cost, context, trust, distribution, UX, workflow, or substrate.",
		"Map adjacent companies, repos, papers, products, and practitioner discussions.",
		"Cluster the signal into a pattern family and compare it to prior related signals.",
		"Identify how the pattern helps or threatens current architecture, revenue, research, and operator leverage.",
		"Reverse-engineer the reusable mechanisms: technical architecture, product wedge, pricing, and distribution.",
		"Choose one bounded response: adopt, integrate, imitate, prototype, compete, partner, or ignore.",
		"Generate a small artifact or frontier task that advances the chosen response.",
		"Record the outcome and update future scout weighting based on whether the signal produced value.",
	}
}

func StrategicMoves() []string {
	return []string{
		"teardown",
		"claim_verification",
		"adjacent_landscape",
		"pattern_cluster",
		"reverse_engineering",
		"internal_prototype",
		"routing_or_substrate_update",
		"growth_fit_decision",
	}
}

func AdjacentSearchQueries(title string, keywords []string) []string {
	compact := strings.Join(keywords, " ")
	if compact == "" {
		compact = title
	}
	return []string{
		title + " competitors alternatives",
		compact + " funding product launch AI",
		compact + " open source GitHub papers",
		compact + " practitioner discussion benchmark",
	}
}

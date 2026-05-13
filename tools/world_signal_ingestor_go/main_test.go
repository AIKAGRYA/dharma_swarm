package main

import "testing"

func TestSignalFromObservationScoresStrategicSignal(t *testing.T) {
	signal := SignalFromObservation(Observation{
		ID:          "obs-1",
		Source:      "operator_drop",
		Title:       "SubQ agent infrastructure startup",
		Description: "Agentic coding runtime benchmark and GitHub ecosystem signal",
		URL:         "https://example.com/subq",
		Keywords:    []string{"agentic", "startup"},
	})
	if signal.RelevanceScore < 0.7 {
		t.Fatalf("expected high score, got %f", signal.RelevanceScore)
	}
	if signal.Category != "benchmark" {
		t.Fatalf("expected benchmark category, got %s", signal.Category)
	}
	if len(signal.Metadata["iteration_steps"].([]string)) != 10 {
		t.Fatal("expected 10 iteration steps")
	}
}

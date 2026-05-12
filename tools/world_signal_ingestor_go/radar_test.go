package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestBuildSignalsElevatesBreakthrough(t *testing.T) {
	rows := []RawObservation{
		{
			ID:          "world_subq_test",
			Source:      "unit_test_feed",
			SourceURL:   "https://subq.ai/",
			Title:       "SubQ claims subquadratic long-context LLM for coding agents",
			Description: "SubQ announces a model release with million token context, SWE-Bench claims, API access, and coding-agent positioning.",
			Keywords:    []string{"SubQ"},
		},
	}

	signals := BuildSignals(rows, "2026-05-11T00:00:00Z", 0.45)

	if len(signals) != 1 {
		t.Fatalf("len(signals) = %d, want 1", len(signals))
	}
	got := signals[0]
	if got.Category != "model_release" {
		t.Fatalf("category = %q, want model_release", got.Category)
	}
	if got.RelevanceScore < 0.8 {
		t.Fatalf("relevance = %.2f, want >= 0.80", got.RelevanceScore)
	}
	if got.Metadata["radar_version"] != RadarVersion {
		t.Fatalf("radar_version = %v", got.Metadata["radar_version"])
	}
	questions, ok := got.Metadata["first_principles_questions"].([]string)
	if !ok || len(questions) != 10 {
		t.Fatalf("questions = %#v", got.Metadata["first_principles_questions"])
	}
	steps, ok := got.Metadata["iteration_steps"].([]string)
	if !ok || len(steps) != 10 {
		t.Fatalf("steps = %#v", got.Metadata["iteration_steps"])
	}
}

func TestReadObservationsJSONLAndWriteSignals(t *testing.T) {
	dir := t.TempDir()
	input := filepath.Join(dir, "observations.jsonl")
	output := filepath.Join(dir, "world_radar.jsonl")
	raw := `{"source":"unit","source_url":"https://example.com/model","title":"New coding agent API launch","description":"A startup launched an API and CLI for agent workflows with benchmark claims."}` + "\n"
	if err := os.WriteFile(input, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}

	rows, err := ReadObservations(input)
	if err != nil {
		t.Fatal(err)
	}
	signals := BuildSignals(rows, "2026-05-11T00:00:00Z", 0.45)
	if err := WriteSignals(output, signals, true); err != nil {
		t.Fatal(err)
	}

	data, err := os.ReadFile(output)
	if err != nil {
		t.Fatal(err)
	}
	var signal WorldSignal
	if err := json.Unmarshal(data, &signal); err != nil {
		t.Fatal(err)
	}
	if signal.Source != "unit" || signal.SourceURL != "https://example.com/model" {
		t.Fatalf("unexpected signal: %+v", signal)
	}
}

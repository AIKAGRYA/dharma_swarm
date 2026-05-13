package main

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestRunNormalizesStrategicSignal(t *testing.T) {
	dir := t.TempDir()
	input := filepath.Join(dir, "raw.jsonl")
	output := filepath.Join(dir, "signals.jsonl")
	raw := RawObservation{Source: "Unit Source", SourceID: "unit_source", SourceURL: "https://example.test/feed", URL: "https://example.test/subq", Publisher: "Example", Title: "SubQ long context coding agent startup launches", Description: "Subquadratic inference workflow for AI agents.", Family: "agent_infra", Keywords: []string{"long context"}}
	line, _ := json.Marshal(raw)
	if err := os.WriteFile(input, append(line, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := run(input, output, 0.45); err != nil {
		t.Fatal(err)
	}
	file, err := os.Open(output)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	if !scanner.Scan() {
		t.Fatal("no signal written")
	}
	var signal Signal
	if err := json.Unmarshal(scanner.Bytes(), &signal); err != nil {
		t.Fatal(err)
	}
	if signal.Category != "agent_infra" {
		t.Fatalf("unexpected category: %s", signal.Category)
	}
	if signal.RelevanceScore < 0.7 {
		t.Fatalf("score too low: %f", signal.RelevanceScore)
	}
	if len(signal.Metadata["first_principles_questions"].([]interface{})) != 10 {
		t.Fatalf("missing first-principles questions: %#v", signal.Metadata)
	}
}

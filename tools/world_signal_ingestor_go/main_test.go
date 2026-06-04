package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

func TestSignalFromObservationScoresStrategicSignal(t *testing.T) {
	signal := SignalFromObservation(Observation{
		ID:          "obs-1",
		Source:      "operator_drop",
		SourceType:  "operator_drop",
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

func TestReadObservationsAcceptsLargeJSONLRows(t *testing.T) {
	path := filepath.Join(t.TempDir(), "large.jsonl")
	largeDescription := strings.Repeat("agent benchmark ", 7000)
	raw := map[string]any{
		"id":          "large-row",
		"source":      "operator_drop",
		"source_type": "operator_drop",
		"title":       "Large agent benchmark observation",
		"description": largeDescription,
		"url":         "https://example.com/large",
	}
	data, err := json.Marshal(raw)
	if err != nil {
		t.Fatal(err)
	}
	if len(data) <= 64*1024 {
		t.Fatalf("test fixture must exceed default scanner token size, got %d bytes", len(data))
	}
	if err := os.WriteFile(path, append(data, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}

	observations, err := readObservations(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(observations) != 1 || observations[0].ID != "large-row" {
		t.Fatalf("large row was not read correctly: %+v", observations)
	}
}

func TestWriteSignalReceiptsEmitsAcceptedReceipts(t *testing.T) {
	dir := t.TempDir()
	signals := []Signal{{
		ID:             "sig-fixture",
		Source:         "world_scout",
		RawSource:      "operator_drop",
		SourceType:     "operator_drop",
		Category:       "benchmark",
		Title:          "Agent benchmark",
		Description:    "Evidence for an agent benchmark.",
		RelevanceScore: 0.82,
		URL:            "https://example.com/agent-benchmark",
		Keywords:       []string{"agent", "benchmark"},
		ObservedAt:     "2026-05-09T00:00:00Z",
		Metadata:       map[string]any{"raw_source": "operator_drop"},
	}}

	if err := writeSignalReceipts(dir, signals, "corr_world_receipts", ""); err != nil {
		t.Fatal(err)
	}

	files, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil {
		t.Fatal(err)
	}
	if len(files) != 1 {
		t.Fatalf("expected one receipt, got %d", len(files))
	}
	raw, err := os.ReadFile(files[0])
	if err != nil {
		t.Fatal(err)
	}
	var r receipt.Receipt
	if err := json.Unmarshal(raw, &r); err != nil {
		t.Fatal(err)
	}
	if r.Status != receipt.StatusAccepted || r.Source != string(EventWorldSignal) {
		t.Fatalf("unexpected receipt: %+v", r)
	}
	var payload map[string]any
	if err := json.Unmarshal(r.Payload, &payload); err != nil {
		t.Fatal(err)
	}
	if payload["title"] != "Agent benchmark" || payload["relevance_score"] == nil {
		t.Fatalf("unexpected receipt payload: %+v", payload)
	}
}

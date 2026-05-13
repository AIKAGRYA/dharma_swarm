package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

type SourceHealth struct {
	SourceID     string `json:"source_id"`
	Family       string `json:"family"`
	Title        string `json:"title"`
	URL          string `json:"url"`
	Kind         string `json:"kind"`
	Publisher    string `json:"publisher,omitempty"`
	FetchEnabled bool   `json:"fetch_enabled"`
	Reachable    bool   `json:"reachable"`
	ItemCount    int    `json:"item_count"`
	LatencyMS    int64  `json:"latency_ms"`
	Error        string `json:"error,omitempty"`
	ObservedAt   string `json:"observed_at"`
}

type ScoutResult struct {
	ObservedAt     string           `json:"observed_at"`
	FetchEnabled   bool             `json:"fetch_enabled"`
	SourceCount    int              `json:"source_count"`
	ReachableCount int              `json:"reachable_count"`
	ItemCount      int              `json:"item_count"`
	Sources        []SourceHealth   `json:"sources"`
	Observations   []RawObservation `json:"-"`
}

func WriteHealth(path string, result ScoutResult) error {
	if path == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(raw, '\n'), 0o644)
}

func newHealth(source Source, fetch bool, observedAt time.Time) SourceHealth {
	return SourceHealth{
		SourceID:     source.ID,
		Family:       source.Family,
		Title:        source.Title,
		URL:          source.URL,
		Kind:         source.Kind,
		Publisher:    source.Publisher,
		FetchEnabled: fetch,
		ObservedAt:   observedAt.UTC().Format(time.RFC3339),
	}
}

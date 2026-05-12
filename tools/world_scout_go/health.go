package main

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"time"
)

type SourceHealth struct {
	ID           string `json:"id"`
	Family       string `json:"family"`
	Title        string `json:"title"`
	URL          string `json:"url"`
	Kind         string `json:"kind"`
	Publisher    string `json:"publisher"`
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

func CollectWorld(opts Options, sources []SourceDefinition) (ScoutResult, error) {
	opts = withDefaults(opts)
	observedAt := opts.ObservedAt
	if observedAt == "" {
		observedAt = time.Now().UTC().Format(time.RFC3339)
	}

	client := &http.Client{Timeout: time.Duration(opts.TimeoutMS) * time.Millisecond}
	result := ScoutResult{
		ObservedAt:   observedAt,
		FetchEnabled: opts.Fetch,
		SourceCount:  len(sources),
		Sources:      make([]SourceHealth, 0, len(sources)),
		Observations: []RawObservation{},
	}

	for _, source := range sources {
		start := time.Now()
		rows, err := collectSource(context.Background(), client, source, opts)
		latencyMS := time.Since(start).Milliseconds()
		errorText := ""
		reachable := true
		if err != nil {
			errorText = err.Error()
			reachable = false
			rows = []RawObservation{catalogObservation(source, observedAt, "fetch_error:"+errorText)}
		}
		if len(rows) == 0 {
			rows = []RawObservation{catalogObservation(source, observedAt, "")}
		}
		if !opts.Fetch {
			reachable = false
		}
		result.Observations = append(result.Observations, rows...)
		result.ItemCount += len(rows)
		if reachable {
			result.ReachableCount++
		}
		result.Sources = append(result.Sources, SourceHealth{
			ID:           source.ID,
			Family:       source.Family,
			Title:        source.Title,
			URL:          source.URL,
			Kind:         source.Kind,
			Publisher:    source.Publisher,
			FetchEnabled: opts.Fetch,
			Reachable:    reachable,
			ItemCount:    len(rows),
			LatencyMS:    latencyMS,
			Error:        errorText,
			ObservedAt:   observedAt,
		})
	}

	sort.SliceStable(result.Observations, func(i, j int) bool {
		if result.Observations[i].Source == result.Observations[j].Source {
			return result.Observations[i].Title < result.Observations[j].Title
		}
		return result.Observations[i].Source < result.Observations[j].Source
	})
	return result, nil
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

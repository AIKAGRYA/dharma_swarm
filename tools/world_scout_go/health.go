package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

type ScoutResult struct {
	FetchEnabled        bool     `json:"fetch_enabled"`
	ObservationCount    int      `json:"observation_count"`
	SourceCount         int      `json:"source_count"`
	SuccessfulSources   int      `json:"successful_sources"`
	FailedSources       int      `json:"failed_sources"`
	ConsecutiveFailures int      `json:"consecutive_failures"`
	Errors              []string `json:"errors"`
	CheckedAt           string   `json:"checked_at"`
}

func writeHealth(path string, result ScoutResult) error {
	if result.CheckedAt == "" {
		result.CheckedAt = time.Now().UTC().Format(time.RFC3339)
	}
	if result.FailedSources > 0 && result.SuccessfulSources == 0 {
		result.ConsecutiveFailures = result.FailedSources
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(payload, '\n'), 0o644)
}

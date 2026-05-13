package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
)

func main() {
	stateDir := flag.String("state-dir", filepath.Join(os.Getenv("HOME"), ".dharma"), "Dharma state directory")
	output := flag.String("output", "", "JSONL output path")
	health := flag.String("health", "", "health JSON output path")
	fetch := flag.Bool("fetch", false, "perform public network fetches")
	flag.Parse()

	outPath := *output
	if outPath == "" {
		outPath = filepath.Join(*stateDir, "meta", "world_radar", "world_scout_observations.jsonl")
	}
	healthPath := *health
	if healthPath == "" {
		healthPath = filepath.Join(*stateDir, "meta", "world_radar", "world_scout_health.json")
	}

	result := ScoutResult{FetchEnabled: *fetch}
	var observations []Observation
	var err error
	if *fetch {
		observations, result, err = FetchSources(DefaultSources())
		if err != nil {
			result.Errors = append(result.Errors, err.Error())
		}
	} else {
		result.Errors = append(result.Errors, "fetch disabled; set --fetch to scan public sources")
	}

	if err := writeJSONL(outPath, observations); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	result.ObservationCount = len(observations)
	if err := writeHealth(healthPath, result); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if len(result.Errors) > 0 && *fetch {
		fmt.Fprintf(os.Stderr, "world scout completed with errors: %v\n", result.Errors)
	}
}

func writeJSONL(path string, observations []Observation) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	enc := json.NewEncoder(file)
	for _, obs := range observations {
		if err := enc.Encode(obs); err != nil {
			return err
		}
	}
	return nil
}

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
)

type multiFlag []string

func (m *multiFlag) String() string { return fmt.Sprint([]string(*m)) }
func (m *multiFlag) Set(value string) error {
	*m = append(*m, value)
	return nil
}

func main() {
	stateDir := flag.String("state-dir", filepath.Join(os.Getenv("HOME"), ".dharma"), "Dharma state directory")
	output := flag.String("output", "", "JSONL output path")
	health := flag.String("health", "", "health JSON output path")
	fetch := flag.Bool("fetch", false, "perform public network fetches")
	cascadeFor := flag.String("cascade-for", "", "movement id for cascade observations")
	beats := flag.Bool("beats", false, "additionally sweep DefaultBeats() -- the capped, curated research-beat set used by the (separate, lower-cadence) deep sweep")
	maxBeatSources := flag.Int("max-beat-sources", MaxDeepSweepBeatSources, "maximum beat-derived query sources when --beats is set; 0 disables beat fanout")
	var queries multiFlag
	flag.Var(&queries, "query", "cascade query to scan; repeatable")
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
		sources := LoadSources(*stateDir)
		if len(queries) > 0 {
			sources = SourcesForQueries([]string(queries), *cascadeFor)
		}
		if *beats {
			// Additive, not a replacement: the deep sweep still wants the
			// normal curated source list plus the capped beat set, not one
			// instead of the other. Existing --fetch/--query behavior is
			// unchanged when --beats is not passed.
			sources = append(sources, DeepSweepBeatSources(DefaultBeats(), *maxBeatSources)...)
		}
		observations, result, err = FetchSources(sources)
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
	file, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".*.tmp")
	if err != nil {
		return err
	}
	tmpName := file.Name()
	defer os.Remove(tmpName)
	enc := json.NewEncoder(file)
	for _, obs := range observations {
		if err := enc.Encode(obs); err != nil {
			file.Close()
			return err
		}
	}
	if err := file.Sync(); err != nil {
		file.Close()
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	return os.Rename(tmpName, path)
}

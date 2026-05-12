// Command world_signal_ingestor_go converts externally gathered observations
// into Dharma world-feed JSONL rows consumed by dharma_swarm.zeitgeist.
//
// Boundary: this Go mouth does deterministic triage only. It does not decide,
// dispatch, call Python policy, write runtime DBs, or mutate ontology. It emits
// raw strategic pressure for Shakti to digest.
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
)

type Options struct {
	InputPath  string
	OutputPath string
	ObservedAt string
	MinScore   float64
	Replace    bool
}

func main() {
	opts := parseFlags()
	if err := run(opts); err != nil {
		fmt.Fprintf(os.Stderr, "world_signal_ingestor_go: %v\n", err)
		os.Exit(1)
	}
}

func parseFlags() Options {
	var opts Options
	flag.StringVar(&opts.InputPath, "input", "", "JSON or JSONL observations to scan")
	flag.StringVar(&opts.OutputPath, "output", "", "world-feed JSONL output path")
	flag.StringVar(&opts.ObservedAt, "observed-at", "", "RFC3339 timestamp; defaults to now UTC")
	flag.Float64Var(&opts.MinScore, "min-score", 0.45, "minimum relevance score to emit")
	flag.BoolVar(&opts.Replace, "replace", false, "replace output file instead of appending")
	flag.Parse()
	return opts
}

func run(opts Options) error {
	if opts.InputPath == "" {
		return errors.New("--input is required")
	}
	if opts.OutputPath == "" {
		return errors.New("--output is required")
	}
	rows, err := ReadObservations(opts.InputPath)
	if err != nil {
		return err
	}
	signals := BuildSignals(rows, opts.ObservedAt, opts.MinScore)
	if len(signals) == 0 {
		return errors.New("no observations crossed min-score")
	}
	return WriteSignals(opts.OutputPath, signals, opts.Replace)
}

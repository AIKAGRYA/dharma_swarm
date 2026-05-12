// Command world_scout_go gathers bounded outside-world observations.
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
)

type Options struct {
	OutputPath       string
	HealthOutputPath string
	ObservedAt       string
	Fetch            bool
	Replace          bool
	TimeoutMS        int
	MaxBodyBytes     int64
	MaxItems         int
}

func main() {
	opts := parseFlags()
	if err := run(opts); err != nil {
		fmt.Fprintf(os.Stderr, "world_scout_go: %v\n", err)
		os.Exit(1)
	}
}

func parseFlags() Options {
	var opts Options
	flag.StringVar(&opts.OutputPath, "output", "", "raw world observations JSONL output path")
	flag.StringVar(&opts.HealthOutputPath, "health-output", "", "world scout health JSON output path")
	flag.StringVar(&opts.ObservedAt, "observed-at", "", "RFC3339 timestamp; defaults to now UTC")
	flag.BoolVar(&opts.Fetch, "fetch", false, "fetch public source bodies")
	flag.BoolVar(&opts.Replace, "replace", false, "replace output file instead of appending")
	flag.IntVar(&opts.TimeoutMS, "timeout-ms", DefaultTimeoutMS, "per-source fetch timeout in milliseconds")
	flag.Int64Var(&opts.MaxBodyBytes, "max-body-bytes", DefaultMaxBodyBytes, "maximum bytes read per source")
	flag.IntVar(&opts.MaxItems, "max-items", DefaultMaxItemsPerSource, "maximum observations emitted per source")
	flag.Parse()
	return opts
}

func run(opts Options) error {
	if opts.OutputPath == "" {
		return errors.New("--output is required")
	}
	result, err := CollectWorld(opts, DefaultSources())
	if err != nil {
		return err
	}
	if len(result.Observations) == 0 {
		return errors.New("no world scout observations emitted")
	}
	if err := WriteObservations(opts.OutputPath, result.Observations, opts.Replace); err != nil {
		return err
	}
	if opts.HealthOutputPath != "" {
		return WriteHealth(opts.HealthOutputPath, result)
	}
	return nil
}

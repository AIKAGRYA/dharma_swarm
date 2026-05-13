package main

import (
	"flag"
	"fmt"
	"os"
)

type Options struct {
	OutputPath        string
	HealthOutputPath  string
	SourcesPath       string
	Fetch             bool
	TimeoutMS         int
	MaxItemsPerSource int
	MaxBodyBytes      int64
}

func main() {
	opts := Options{}
	flag.StringVar(&opts.OutputPath, "output", "world_scout_observations.jsonl", "JSONL output path")
	flag.StringVar(&opts.HealthOutputPath, "health-output", "", "source health JSON output path")
	flag.StringVar(&opts.SourcesPath, "sources", "", "optional sources JSON path")
	flag.BoolVar(&opts.Fetch, "fetch", false, "enable live public-source fetches")
	flag.IntVar(&opts.TimeoutMS, "timeout-ms", DefaultTimeoutMS, "per-source timeout in milliseconds")
	flag.IntVar(&opts.MaxItemsPerSource, "max-items", DefaultMaxItemsPerSource, "max observations per source")
	flag.Int64Var(&opts.MaxBodyBytes, "max-body-bytes", DefaultMaxBodyBytes, "max bytes read per source")
	flag.Parse()

	if err := run(opts); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(opts Options) error {
	sources, err := LoadSources(opts.SourcesPath)
	if err != nil {
		return err
	}
	result, err := CollectWorld(opts, sources)
	if err != nil {
		return err
	}
	if err := WriteObservations(opts.OutputPath, result.Observations); err != nil {
		return err
	}
	return WriteHealth(opts.HealthOutputPath, result)
}

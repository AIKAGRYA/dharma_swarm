// Command practitioner_signal_ingestor_go inventories practitioner, social,
// and high-signal community sources as raw/hash-only receipts.
//
// Boundary: this mouth fetches bounded metadata and body hashes only. Social
// and commentary feeds are marked human_only; this tool never summarizes them
// into routing facts or executes linked code.
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/sourceprobe"
)

type Options struct {
	OutputPath    string
	CorrelationID string
	ObservedAt    string
	TimeoutMS     int
	MaxBodyBytes  int64
	NoFetch       bool
}

func main() {
	opts := parseFlags()
	if err := run(opts); err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", SourceName, err)
		os.Exit(1)
	}
}

func parseFlags() Options {
	var opts Options
	flag.StringVar(&opts.OutputPath, "output", "", "path for aggregate practitioner signal receipt")
	flag.StringVar(&opts.CorrelationID, "correlation-id", "", "mandatory closure correlation id")
	flag.StringVar(&opts.ObservedAt, "observed-at", "", "RFC3339 timestamp; defaults to now UTC")
	flag.IntVar(&opts.TimeoutMS, "timeout-ms", sourceprobe.DefaultTimeoutMS, "per-source fetch timeout in milliseconds")
	flag.Int64Var(&opts.MaxBodyBytes, "max-body-bytes", sourceprobe.DefaultMaxBodyBytes, "maximum bytes hashed per source body")
	flag.BoolVar(&opts.NoFetch, "no-fetch", false, "emit static source catalog without external network fetches")
	flag.Parse()
	return opts
}

func run(opts Options) error {
	if opts.OutputPath == "" {
		return errors.New("--output is required")
	}
	if opts.CorrelationID == "" {
		return errors.New("--correlation-id is required")
	}
	r, err := BuildReceipt(opts)
	if err != nil {
		var rejectErr sourceprobe.RejectError
		if !errors.As(err, &rejectErr) {
			return err
		}
		if writeErr := receipt.Write(opts.OutputPath, r); writeErr != nil {
			return writeErr
		}
		fmt.Fprintf(os.Stderr, "%s: rejected: %s\n", SourceName, rejectErr.Reason)
		return nil
	}
	return receipt.Write(opts.OutputPath, r)
}

func BuildReceipt(opts Options) (receipt.Receipt, error) {
	return sourceprobe.BuildAggregateReceipt(SourceName, SourceURL, IngestSchema, TrustEnvelope(), sourceprobe.Options{
		CorrelationID: opts.CorrelationID,
		ObservedAt:    opts.ObservedAt,
		TimeoutMS:     opts.TimeoutMS,
		MaxBodyBytes:  opts.MaxBodyBytes,
		Fetch:         !opts.NoFetch,
		Sources:       DefaultSources(),
	})
}

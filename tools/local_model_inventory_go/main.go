// Command local_model_inventory_go probes loopback-only local model runtime
// endpoints and emits one aggregate evidence receipt.
//
// Boundary: this tool observes local model runtime availability only. It does
// not execute discovered binaries, scan processes, write runtime DB, write
// ontology DB, dispatch agents, or make routing decisions.
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

// Options is the CLI surface for this binary.
type Options struct {
	OutputPath    string
	CorrelationID string
	ObservedAt    string
	TimeoutMS     int
}

func main() {
	opts := parseFlags()
	if err := run(opts); err != nil {
		fmt.Fprintf(os.Stderr, "local_model_inventory_go: %v\n", err)
		os.Exit(1)
	}
}

func parseFlags() Options {
	var opts Options
	flag.StringVar(&opts.OutputPath, "output", "", "path for aggregate model inventory receipt")
	flag.StringVar(&opts.CorrelationID, "correlation-id", "", "mandatory closure correlation id")
	flag.StringVar(&opts.ObservedAt, "observed-at", "", "RFC3339 timestamp; defaults to now UTC")
	flag.IntVar(&opts.TimeoutMS, "timeout-ms", DefaultTimeoutMS, "per-endpoint probe timeout in milliseconds")
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

	r, err := BuildInventoryReceipt(InventoryOptions{
		CorrelationID: opts.CorrelationID,
		ObservedAt:    opts.ObservedAt,
		TimeoutMS:     opts.TimeoutMS,
	})
	if err != nil {
		var rejectErr RejectError
		if !errors.As(err, &rejectErr) {
			return err
		}
		if writeErr := receipt.Write(opts.OutputPath, r); writeErr != nil {
			return writeErr
		}
		fmt.Fprintf(os.Stderr, "local_model_inventory_go: rejected: %s\n", rejectErr.Reason)
		return nil
	}

	return receipt.Write(opts.OutputPath, r)
}

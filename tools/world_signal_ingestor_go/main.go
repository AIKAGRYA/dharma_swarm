// Command world_signal_ingestor_go converts world observation/signal payloads
// into normalized evidence receipts.
//
// Boundary: this binary emits receipts only. It does not fetch live sources,
// decide, dispatch, write runtime DB, write ontology DB, or call Python policy.
// Tests are fixture-driven; live network belongs to a later gated scout packet.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/adaptercontract"
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

// Options is the CLI surface for this binary.
type Options struct {
	InputPath     string
	OutputPath    string
	EventType     string
	SourceURL     string
	CorrelationID string
	ObservedAt    string
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
	flag.StringVar(&opts.InputPath, "input", "", "path to world observation/signal payload JSON")
	flag.StringVar(&opts.OutputPath, "output", "", "path for normalized evidence receipt")
	flag.StringVar(&opts.EventType, "event-type", "",
		"world event type: "+joinEventTypes())
	flag.StringVar(&opts.SourceURL, "source-url", "", "stable source URL or file URI")
	flag.StringVar(&opts.CorrelationID, "correlation-id", "", "mandatory closure correlation id")
	flag.StringVar(&opts.ObservedAt, "observed-at", "", "RFC3339 timestamp; defaults to now UTC")
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
	if opts.EventType == "" {
		return errors.New("--event-type is required")
	}
	if opts.CorrelationID == "" {
		return errors.New("--correlation-id is required")
	}

	payload, err := os.ReadFile(opts.InputPath)
	if err != nil {
		return err
	}

	sourceURL := opts.SourceURL
	if sourceURL == "" {
		abs, err := filepath.Abs(opts.InputPath)
		if err != nil {
			return err
		}
		sourceURL = "file://" + filepath.ToSlash(abs)
	}

	observedAt := opts.ObservedAt
	if observedAt == "" {
		observedAt = time.Now().UTC().Format(time.RFC3339)
	}

	fixture := adaptercontract.Fixture{
		CorrelationID: opts.CorrelationID,
		Source:        opts.EventType,
		SourceURL:     sourceURL,
		ObservedAt:    observedAt,
		Payload:       json.RawMessage(payload),
	}

	r, adaptErr := Adapter{}.Adapt(context.Background(), fixture)
	if adaptErr != nil {
		var rejectErr adaptercontract.RejectError
		if !errors.As(adaptErr, &rejectErr) {
			return adaptErr
		}
		if writeErr := receipt.Write(opts.OutputPath, r); writeErr != nil {
			return writeErr
		}
		fmt.Fprintf(os.Stderr, "world_signal_ingestor_go: rejected: %s\n", rejectErr.Reason)
		return nil
	}

	return receipt.Write(opts.OutputPath, r)
}

func joinEventTypes() string {
	types := SupportedEventTypes()
	parts := make([]string, len(types))
	for i, t := range types {
		parts[i] = string(t)
	}
	return strings.Join(parts, ", ")
}

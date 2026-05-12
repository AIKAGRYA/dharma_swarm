// Command github_ingestor_go converts a GitHub event payload file into a
// normalized closure-v0 evidence receipt on disk. The receipt-building
// primitives live in the canonical Go SDK at tools/go_sdk/receipt; the
// adapter-contract glue lives in tools/go_sdk/adaptercontract. This binary is
// a thin CLI wrapper around the GitHub Adapter.
//
// Boundary: this tool emits receipts only. It does not call the live GitHub
// API; it never decides, dispatches, writes runtime DB, writes ontology DB,
// or calls Python policy. Tests are fixture-driven.
//
// The supported event types are the source values returned by
// SupportedEventTypes(): github_pull_request, github_commit,
// github_check_run, github_release.
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
		fmt.Fprintf(os.Stderr, "github_ingestor_go: %v\n", err)
		os.Exit(1)
	}
}

func parseFlags() Options {
	var opts Options
	flag.StringVar(&opts.InputPath, "input", "", "path to GitHub event payload JSON")
	flag.StringVar(&opts.OutputPath, "output", "", "path for normalized evidence receipt")
	flag.StringVar(&opts.EventType, "event-type", "",
		"GitHub event type: "+joinEventTypes())
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
	// The adapter returns (rejectedReceipt, RejectError) on rejection so we
	// can still write the receipt to disk and surface the reason on stderr.
	// Non-RejectError errors (e.g. SDK build failure) are fatal.
	if adaptErr != nil {
		var rejectErr adaptercontract.RejectError
		if !errors.As(adaptErr, &rejectErr) {
			return adaptErr
		}
		if writeErr := receipt.Write(opts.OutputPath, r); writeErr != nil {
			return writeErr
		}
		fmt.Fprintf(os.Stderr, "github_ingestor_go: rejected: %s\n", rejectErr.Reason)
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

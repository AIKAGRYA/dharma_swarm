// Command evidence_ingestor_go converts a payload file into a normalized
// closure-v0 evidence receipt on disk. The receipt-building primitives live in
// the canonical Go SDK at tools/go_sdk/receipt; this binary is a thin CLI
// wrapper around that SDK so future sense-organ adapters share the same
// validation, hashing, normalization, and atomic-write contract.
//
// Boundary: this tool emits receipts only. It does not decide, dispatch, write
// runtime DB, write ontology DB, or call Python policy.
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

const defaultSchemaVersion = receipt.DefaultSchemaVersion

// EvidenceReceipt is the on-the-wire receipt shape. It is a type alias for the
// SDK Receipt so existing Python bridge code and existing tests in this
// package keep working unchanged.
type EvidenceReceipt = receipt.Receipt

// Options carries the CLI surface for the evidence_ingestor_go binary.
type Options struct {
	InputPath     string
	OutputPath    string
	Source        string
	SourceURL     string
	CorrelationID string
	ObservedAt    string
	SchemaVersion string
}

func main() {
	opts := parseFlags()
	if err := run(opts); err != nil {
		fmt.Fprintf(os.Stderr, "evidence_ingestor_go: %v\n", err)
		os.Exit(1)
	}
}

func parseFlags() Options {
	var opts Options
	flag.StringVar(&opts.InputPath, "input", "", "path to source payload")
	flag.StringVar(&opts.OutputPath, "output", "", "path for normalized evidence receipt")
	flag.StringVar(&opts.Source, "source", "local_file", "source adapter name")
	flag.StringVar(&opts.SourceURL, "source-url", "", "stable source URL or file URI")
	flag.StringVar(&opts.CorrelationID, "correlation-id", "", "mandatory closure correlation id")
	flag.StringVar(&opts.ObservedAt, "observed-at", "", "RFC3339 timestamp; defaults to now UTC")
	flag.StringVar(&opts.SchemaVersion, "schema-version", defaultSchemaVersion, "receipt schema version")
	flag.Parse()
	return opts
}

func run(opts Options) error {
	r, err := BuildReceipt(opts)
	if err != nil {
		return err
	}
	return WriteReceipt(opts.OutputPath, r)
}

// BuildReceipt is a thin wrapper around receipt.Build that preserves the CLI's
// historical contract: input/output paths required, source_url defaults to a
// file:// URI of the input path, payload is read from disk by this CLI.
func BuildReceipt(opts Options) (EvidenceReceipt, error) {
	if opts.InputPath == "" {
		return EvidenceReceipt{}, errors.New("--input is required")
	}
	if opts.OutputPath == "" {
		return EvidenceReceipt{}, errors.New("--output is required")
	}

	payload, err := os.ReadFile(opts.InputPath)
	if err != nil {
		return EvidenceReceipt{}, err
	}

	sourceURL := opts.SourceURL
	if sourceURL == "" {
		abs, err := filepath.Abs(opts.InputPath)
		if err != nil {
			return EvidenceReceipt{}, err
		}
		sourceURL = "file://" + filepath.ToSlash(abs)
	}

	return receipt.Build(receipt.BuildSpec{
		Source:        opts.Source,
		SourceURL:     sourceURL,
		CorrelationID: opts.CorrelationID,
		ObservedAt:    opts.ObservedAt,
		SchemaVersion: opts.SchemaVersion,
	}, payload)
}

// WriteReceipt is a thin wrapper around receipt.Write so existing tests in
// this package, and any downstream callers, keep their import surface stable.
func WriteReceipt(path string, r EvidenceReceipt) error {
	return receipt.Write(path, r)
}

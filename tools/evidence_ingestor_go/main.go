package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

const defaultSchemaVersion = "go_evidence_receipt.v0"

type EvidenceReceipt struct {
	ReceiptID      string          `json:"receipt_id"`
	CorrelationID  string          `json:"correlation_id"`
	Source         string          `json:"source"`
	SourceURL      string          `json:"source_url"`
	ObservedAt     string          `json:"observed_at"`
	ContentHash    string          `json:"content_hash"`
	EventUID       string          `json:"event_uid"`
	SchemaVersion  string          `json:"schema_version"`
	Status         string          `json:"status"`
	RejectedReason string          `json:"rejected_reason,omitempty"`
	Payload        json.RawMessage `json:"payload"`
}

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
	receipt, err := BuildReceipt(opts)
	if err != nil {
		return err
	}
	return WriteReceipt(opts.OutputPath, receipt)
}

func BuildReceipt(opts Options) (EvidenceReceipt, error) {
	if opts.InputPath == "" {
		return EvidenceReceipt{}, errors.New("--input is required")
	}
	if opts.OutputPath == "" {
		return EvidenceReceipt{}, errors.New("--output is required")
	}
	if opts.CorrelationID == "" {
		return EvidenceReceipt{}, errors.New("--correlation-id is required")
	}
	if opts.Source == "" {
		return EvidenceReceipt{}, errors.New("--source is required")
	}
	if opts.SchemaVersion == "" {
		return EvidenceReceipt{}, errors.New("--schema-version is required")
	}

	payload, err := os.ReadFile(opts.InputPath)
	if err != nil {
		return EvidenceReceipt{}, err
	}
	normalized, err := normalizePayload(payload)
	if err != nil {
		return EvidenceReceipt{}, err
	}

	observedAt := opts.ObservedAt
	if observedAt == "" {
		observedAt = time.Now().UTC().Format(time.RFC3339)
	}
	if _, err := time.Parse(time.RFC3339, observedAt); err != nil {
		return EvidenceReceipt{}, fmt.Errorf("--observed-at must be RFC3339: %w", err)
	}

	sourceURL := opts.SourceURL
	if sourceURL == "" {
		abs, err := filepath.Abs(opts.InputPath)
		if err != nil {
			return EvidenceReceipt{}, err
		}
		sourceURL = "file://" + filepath.ToSlash(abs)
	}

	contentHash := "sha256:" + sha256Hex(payload)
	eventUID := "evt_" + shortDigest(opts.Source, sourceURL, contentHash)
	receiptID := "goev_" + shortDigest(opts.CorrelationID, eventUID)

	return EvidenceReceipt{
		ReceiptID:     receiptID,
		CorrelationID: opts.CorrelationID,
		Source:        opts.Source,
		SourceURL:     sourceURL,
		ObservedAt:    observedAt,
		ContentHash:   contentHash,
		EventUID:      eventUID,
		SchemaVersion: opts.SchemaVersion,
		Status:        "accepted",
		Payload:       normalized,
	}, nil
}

func normalizePayload(raw []byte) (json.RawMessage, error) {
	trimmed := bytes.TrimSpace(raw)
	if len(trimmed) == 0 {
		return nil, errors.New("input payload is empty")
	}
	if json.Valid(trimmed) {
		return append(json.RawMessage(nil), trimmed...), nil
	}
	wrapped, err := json.Marshal(map[string]string{"raw_text": string(raw)})
	if err != nil {
		return nil, err
	}
	return wrapped, nil
}

func WriteReceipt(path string, receipt EvidenceReceipt) error {
	data, err := json.MarshalIndent(receipt, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')

	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), filepath.Base(path)+".")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)

	if _, err := tmp.Write(data); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(tmpName, path)
}

func sha256Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func shortDigest(parts ...string) string {
	var buf bytes.Buffer
	for i, part := range parts {
		if i > 0 {
			buf.WriteByte(0)
		}
		buf.WriteString(part)
	}
	sum := sha256.Sum256(buf.Bytes())
	return hex.EncodeToString(sum[:12])
}

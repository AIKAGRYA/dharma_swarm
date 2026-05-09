// Package receipt is the canonical Go SDK for evidence sense-organ receipts.
//
// Boundary: this SDK emits receipts only. It does not decide, dispatch, write
// runtime DB, write ontology DB, or call Python policy. Decisions belong to
// dharma_swarm/operator_core/closure_v0; this package only validates inputs,
// normalizes payloads, computes deterministic identity hashes, serializes, and
// atomically writes JSON receipts to disk.
//
// All hashing matches the original tools/evidence_ingestor_go/main.go byte-for-byte:
//
//	content_hash = "sha256:" + hex(sha256(raw_payload_bytes))
//	event_uid    = "evt_"    + hex12(sha256(source NUL source_url NUL content_hash))
//	receipt_id   = "goev_"   + hex12(sha256(correlation_id NUL event_uid))
//
// Behavior change between G0 and G2 is forbidden. Determinism for fixed inputs
// is enforced by tests in this package.
package receipt

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// DefaultSchemaVersion is the canonical schema tag for the v0 receipt shape.
const DefaultSchemaVersion = "go_evidence_receipt.v0"

// Status constants for the lifecycle field.
const (
	StatusAccepted = "accepted"
	StatusRejected = "rejected"
)

// Receipt is the on-the-wire receipt shape. Field tags MUST match the prior
// EvidenceReceipt struct on tools/evidence_ingestor_go/main.go so existing
// Python bridge consumers (dharma_swarm/operator_core/go_evidence_bridge.py)
// continue to parse it without change.
type Receipt struct {
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

// BuildSpec carries the metadata needed to build a Receipt. It is pure data;
// callers (CLI, test harnesses, future adapters) construct it from their own
// surfaces. The SDK never reads the filesystem on behalf of the caller —
// callers pass payload bytes in directly.
type BuildSpec struct {
	Source        string
	SourceURL     string
	CorrelationID string
	ObservedAt    string // RFC3339; if empty, Build defaults to time.Now().UTC()
	SchemaVersion string // if empty, Build uses DefaultSchemaVersion
}

// Build validates spec, normalizes payload, computes identity hashes, and
// returns an accepted Receipt. Callers wanting an explicit reject path should
// use Reject instead.
func Build(spec BuildSpec, payload []byte) (Receipt, error) {
	if err := validateSpec(spec); err != nil {
		return Receipt{}, err
	}
	if spec.SourceURL == "" {
		return Receipt{}, errors.New("source_url is required")
	}

	normalized, err := Normalize(payload)
	if err != nil {
		return Receipt{}, err
	}

	observedAt, err := resolveObservedAt(spec.ObservedAt)
	if err != nil {
		return Receipt{}, err
	}

	schemaVersion := spec.SchemaVersion
	if schemaVersion == "" {
		schemaVersion = DefaultSchemaVersion
	}

	contentHash := "sha256:" + sha256Hex(payload)
	eventUID := "evt_" + shortDigest(spec.Source, spec.SourceURL, contentHash)
	receiptID := "goev_" + shortDigest(spec.CorrelationID, eventUID)

	return Receipt{
		ReceiptID:     receiptID,
		CorrelationID: spec.CorrelationID,
		Source:        spec.Source,
		SourceURL:     spec.SourceURL,
		ObservedAt:    observedAt,
		ContentHash:   contentHash,
		EventUID:      eventUID,
		SchemaVersion: schemaVersion,
		Status:        StatusAccepted,
		Payload:       normalized,
	}, nil
}

// Reject returns a Receipt with status=rejected and a non-empty reason.
// Reject still requires a valid spec and SourceURL so the rejected receipt is
// still discoverable. Payload is normalized when possible; if normalization
// fails (e.g. empty), the payload field is left as a JSON null literal.
//
// The reason MUST be non-empty; an empty reason is itself a programmer error.
func Reject(spec BuildSpec, payload []byte, reason string) (Receipt, error) {
	if reason == "" {
		return Receipt{}, errors.New("reject reason is required")
	}
	if err := validateSpec(spec); err != nil {
		return Receipt{}, err
	}
	if spec.SourceURL == "" {
		return Receipt{}, errors.New("source_url is required")
	}

	observedAt, err := resolveObservedAt(spec.ObservedAt)
	if err != nil {
		return Receipt{}, err
	}

	schemaVersion := spec.SchemaVersion
	if schemaVersion == "" {
		schemaVersion = DefaultSchemaVersion
	}

	normalized, normErr := Normalize(payload)
	if normErr != nil {
		normalized = json.RawMessage("null")
	}

	contentHash := "sha256:" + sha256Hex(payload)
	eventUID := "evt_" + shortDigest(spec.Source, spec.SourceURL, contentHash)
	receiptID := "goev_" + shortDigest(spec.CorrelationID, eventUID)

	return Receipt{
		ReceiptID:      receiptID,
		CorrelationID:  spec.CorrelationID,
		Source:         spec.Source,
		SourceURL:      spec.SourceURL,
		ObservedAt:     observedAt,
		ContentHash:    contentHash,
		EventUID:       eventUID,
		SchemaVersion:  schemaVersion,
		Status:         StatusRejected,
		RejectedReason: reason,
		Payload:        normalized,
	}, nil
}

// Normalize returns the canonical JSON form of a payload:
//   - if raw (after trim) is valid JSON, returns the trimmed bytes
//   - if raw is non-empty but not JSON, returns {"raw_text": <original raw>}
//   - if raw is empty (after trim), returns an error
//
// Behavior matches tools/evidence_ingestor_go/main.go normalizePayload exactly.
func Normalize(raw []byte) (json.RawMessage, error) {
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

// Write serializes receipt to indented JSON with a trailing newline and writes
// it atomically to path: it creates the parent directory (mode 0755), writes a
// temp file in the same directory, then renames over path. On any error, the
// temp file is removed.
func Write(path string, r Receipt) error {
	data, err := json.MarshalIndent(r, "", "  ")
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

// ContentHash exposes the canonical content-hash form for the SDK's identity
// derivation. Callers comparing receipts byte-for-byte may use this directly.
func ContentHash(payload []byte) string {
	return "sha256:" + sha256Hex(payload)
}

// EventUID derives the canonical evt_<hex12> identifier from source, sourceURL
// and the already-formed contentHash string.
func EventUID(source, sourceURL, contentHash string) string {
	return "evt_" + shortDigest(source, sourceURL, contentHash)
}

// ReceiptID derives the canonical goev_<hex12> identifier from a correlation
// ID and an already-formed eventUID string.
func ReceiptID(correlationID, eventUID string) string {
	return "goev_" + shortDigest(correlationID, eventUID)
}

func validateSpec(spec BuildSpec) error {
	if spec.CorrelationID == "" {
		return errors.New("correlation_id is required")
	}
	if spec.Source == "" {
		return errors.New("source is required")
	}
	return nil
}

func resolveObservedAt(observedAt string) (string, error) {
	if observedAt == "" {
		return time.Now().UTC().Format(time.RFC3339), nil
	}
	if _, err := time.Parse(time.RFC3339, observedAt); err != nil {
		return "", fmt.Errorf("observed_at must be RFC3339: %w", err)
	}
	return observedAt, nil
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

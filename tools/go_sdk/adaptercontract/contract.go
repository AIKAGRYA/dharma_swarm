package adaptercontract

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

const (
	DefaultSchemaVersion = receipt.DefaultSchemaVersion
	StatusAccepted       = receipt.StatusAccepted
	StatusRejected       = receipt.StatusRejected
)

type Fixture struct {
	CorrelationID string          `json:"correlation_id"`
	Source        string          `json:"source"`
	SourceURL     string          `json:"source_url"`
	ObservedAt    string          `json:"observed_at"`
	Payload       json.RawMessage `json:"payload"`
}

type Receipt = receipt.Receipt

type SourceAdapter interface {
	Adapt(context.Context, Fixture) (Receipt, error)
}

type RejectError struct {
	Reason string
}

func (e RejectError) Error() string {
	if e.Reason == "" {
		return "adapter rejected input"
	}
	return "adapter rejected input: " + e.Reason
}

func LoadFixture(path string) (Fixture, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Fixture{}, err
	}
	var fixture Fixture
	if err := json.Unmarshal(raw, &fixture); err != nil {
		return Fixture{}, err
	}
	return fixture, nil
}

func BuildSpec(fixture Fixture) receipt.BuildSpec {
	return receipt.BuildSpec{
		Source:        fixture.Source,
		SourceURL:     fixture.SourceURL,
		CorrelationID: fixture.CorrelationID,
		ObservedAt:    fixture.ObservedAt,
		SchemaVersion: DefaultSchemaVersion,
	}
}

func ValidateAccepted(fixture Fixture, got Receipt) error {
	if got.Status != StatusAccepted {
		return fmt.Errorf("status = %q, want %q", got.Status, StatusAccepted)
	}
	if err := validateSharedFields(fixture, got); err != nil {
		return err
	}
	want, err := receipt.Build(BuildSpec(fixture), []byte(fixture.Payload))
	if err != nil {
		return fmt.Errorf("canonical receipt.Build failed: %w", err)
	}
	return validateCanonicalReceipt(got, want)
}

func ValidateRejected(fixture Fixture, got Receipt, err error) error {
	if err == nil {
		return errors.New("malformed input must return an explicit error")
	}
	var rejectErr RejectError
	if !errors.As(err, &rejectErr) || rejectErr.Reason == "" {
		return fmt.Errorf("error must be RejectError with explicit reason: %v", err)
	}
	if got.Status != StatusRejected {
		return fmt.Errorf("status = %q, want %q", got.Status, StatusRejected)
	}
	if err := validateSharedFields(fixture, got); err != nil {
		return err
	}
	if got.RejectedReason == "" {
		return errors.New("rejected receipt must include rejected_reason")
	}
	if got.RejectedReason != rejectErr.Reason {
		return fmt.Errorf("rejected_reason = %q, want %q", got.RejectedReason, rejectErr.Reason)
	}
	want, err := receipt.Reject(BuildSpec(fixture), []byte(fixture.Payload), rejectErr.Reason)
	if err != nil {
		return fmt.Errorf("canonical receipt.Reject failed: %w", err)
	}
	return validateCanonicalReceipt(got, want)
}

func validateSharedFields(fixture Fixture, receipt Receipt) error {
	if fixture.CorrelationID == "" {
		return errors.New("fixture correlation_id is required")
	}
	if receipt.CorrelationID != fixture.CorrelationID {
		return fmt.Errorf("correlation_id = %q, want %q", receipt.CorrelationID, fixture.CorrelationID)
	}
	if receipt.Source != fixture.Source {
		return fmt.Errorf("source = %q, want %q", receipt.Source, fixture.Source)
	}
	if receipt.SourceURL != fixture.SourceURL {
		return fmt.Errorf("source_url = %q, want %q", receipt.SourceURL, fixture.SourceURL)
	}
	if fixture.ObservedAt != "" && receipt.ObservedAt != fixture.ObservedAt {
		return fmt.Errorf("observed_at = %q, want %q", receipt.ObservedAt, fixture.ObservedAt)
	}
	return nil
}

func validateCanonicalReceipt(got, want Receipt) error {
	if got.ReceiptID != want.ReceiptID {
		return fmt.Errorf("receipt_id = %q, want %q", got.ReceiptID, want.ReceiptID)
	}
	if got.ContentHash != want.ContentHash {
		return fmt.Errorf("content_hash = %q, want %q", got.ContentHash, want.ContentHash)
	}
	if got.EventUID != want.EventUID {
		return fmt.Errorf("event_uid = %q, want %q", got.EventUID, want.EventUID)
	}
	if got.SchemaVersion != want.SchemaVersion {
		return fmt.Errorf("schema_version = %q, want %q", got.SchemaVersion, want.SchemaVersion)
	}
	if got.RejectedReason != want.RejectedReason {
		return fmt.Errorf("rejected_reason = %q, want %q", got.RejectedReason, want.RejectedReason)
	}
	if string(got.Payload) != string(want.Payload) {
		return fmt.Errorf("payload = %s, want %s", got.Payload, want.Payload)
	}
	return nil
}

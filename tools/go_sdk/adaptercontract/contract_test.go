package adaptercontract

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

type fixtureAdapter struct{}

func (fixtureAdapter) Adapt(_ context.Context, fixture Fixture) (Receipt, error) {
	if !json.Valid(bytes.TrimSpace(fixture.Payload)) {
		reason := "malformed_json"
		rejected, err := receipt.Reject(BuildSpec(fixture), []byte(fixture.Payload), reason)
		if err != nil {
			return Receipt{}, err
		}
		return rejected, RejectError{Reason: reason}
	}
	return receipt.Build(BuildSpec(fixture), []byte(fixture.Payload))
}

func fixturePath(name string) string {
	return filepath.Join("..", "..", "..", "tests", "fixtures", "go_adapters", name)
}

func TestFixtureAdapterAcceptanceMatchesGolden(t *testing.T) {
	fixture, err := LoadFixture(fixturePath("valid_input.json"))
	if err != nil {
		t.Fatal(err)
	}
	receipt, err := fixtureAdapter{}.Adapt(context.Background(), fixture)
	if err != nil {
		t.Fatal(err)
	}
	if err := ValidateAccepted(fixture, receipt); err != nil {
		t.Fatal(err)
	}

	wantRaw, err := os.ReadFile(fixturePath("expected_receipt.json"))
	if err != nil {
		t.Fatal(err)
	}
	var want Receipt
	if err := json.Unmarshal(wantRaw, &want); err != nil {
		t.Fatal(err)
	}
	if !receiptsEqual(receipt, want) {
		got, _ := json.MarshalIndent(receipt, "", "  ")
		expected, _ := json.MarshalIndent(want, "", "  ")
		t.Fatalf("receipt drifted\n got: %s\nwant: %s", got, expected)
	}
}

func receiptsEqual(a, b Receipt) bool {
	if a.ReceiptID != b.ReceiptID ||
		a.CorrelationID != b.CorrelationID ||
		a.Source != b.Source ||
		a.SourceURL != b.SourceURL ||
		a.ObservedAt != b.ObservedAt ||
		a.ContentHash != b.ContentHash ||
		a.EventUID != b.EventUID ||
		a.SchemaVersion != b.SchemaVersion ||
		a.Status != b.Status ||
		a.RejectedReason != b.RejectedReason {
		return false
	}
	var aPayload, bPayload any
	if err := json.Unmarshal(a.Payload, &aPayload); err != nil {
		return false
	}
	if err := json.Unmarshal(b.Payload, &bPayload); err != nil {
		return false
	}
	return reflect.DeepEqual(aPayload, bPayload)
}

func TestFixtureAdapterIsDeterministic(t *testing.T) {
	fixture, err := LoadFixture(fixturePath("valid_input.json"))
	if err != nil {
		t.Fatal(err)
	}
	first, err := fixtureAdapter{}.Adapt(context.Background(), fixture)
	if err != nil {
		t.Fatal(err)
	}
	second, err := fixtureAdapter{}.Adapt(context.Background(), fixture)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(first, second) {
		t.Fatalf("adapter receipt must be deterministic:\n%+v\n%+v", first, second)
	}
}

func TestFixtureAdapterRejectsMalformedInputWithReason(t *testing.T) {
	fixture, err := loadMalformedFixture(fixturePath("malformed_input.json"))
	if err != nil {
		t.Fatal(err)
	}
	receipt, err := fixtureAdapter{}.Adapt(context.Background(), fixture)
	if err := ValidateRejected(fixture, receipt, err); err != nil {
		t.Fatal(err)
	}
	var rejectErr RejectError
	if !errors.As(err, &rejectErr) || rejectErr.Reason != "malformed_json" {
		t.Fatalf("unexpected rejection error: %v", err)
	}
}

func loadMalformedFixture(path string) (Fixture, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Fixture{}, err
	}
	var file struct {
		CorrelationID string `json:"correlation_id"`
		Source        string `json:"source"`
		SourceURL     string `json:"source_url"`
		ObservedAt    string `json:"observed_at"`
		PayloadText   string `json:"payload_text"`
	}
	if err := json.Unmarshal(raw, &file); err != nil {
		return Fixture{}, err
	}
	return Fixture{
		CorrelationID: file.CorrelationID,
		Source:        file.Source,
		SourceURL:     file.SourceURL,
		ObservedAt:    file.ObservedAt,
		Payload:       json.RawMessage(file.PayloadText),
	}, nil
}

func TestValidateAcceptedCatchesCorrelationDrift(t *testing.T) {
	fixture, err := LoadFixture(fixturePath("valid_input.json"))
	if err != nil {
		t.Fatal(err)
	}
	receipt, err := fixtureAdapter{}.Adapt(context.Background(), fixture)
	if err != nil {
		t.Fatal(err)
	}
	receipt.CorrelationID = "corr_wrong"
	if err := ValidateAccepted(fixture, receipt); err == nil {
		t.Fatal("expected correlation_id drift to fail validation")
	}
}

func TestValidateAcceptedCatchesUnstableIdentityFields(t *testing.T) {
	fixture, err := LoadFixture(fixturePath("valid_input.json"))
	if err != nil {
		t.Fatal(err)
	}
	receipt, err := fixtureAdapter{}.Adapt(context.Background(), fixture)
	if err != nil {
		t.Fatal(err)
	}
	receipt.EventUID = "evt_unstable"
	if err := ValidateAccepted(fixture, receipt); err == nil {
		t.Fatal("expected event_uid drift to fail validation")
	}
}

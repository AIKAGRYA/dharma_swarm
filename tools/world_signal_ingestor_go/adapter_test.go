package main

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/adaptercontract"
)

// fixturePath resolves a fixture file in the shared tests/fixtures tree.
func fixturePath(name string) string {
	return filepath.Join("..", "..", "tests", "fixtures", "go_world_signal_ingestor", name)
}

func loadFixture(t *testing.T, name string) adaptercontract.Fixture {
	t.Helper()
	f, err := adaptercontract.LoadFixture(fixturePath(name))
	if err != nil {
		t.Fatalf("load fixture %s: %v", name, err)
	}
	return f
}

func loadMalformedFixture(t *testing.T, name string) adaptercontract.Fixture {
	t.Helper()
	raw, err := os.ReadFile(fixturePath(name))
	if err != nil {
		t.Fatalf("read malformed fixture %s: %v", name, err)
	}
	var file struct {
		CorrelationID string `json:"correlation_id"`
		Source        string `json:"source"`
		SourceURL     string `json:"source_url"`
		ObservedAt    string `json:"observed_at"`
		PayloadText   string `json:"payload_text"`
	}
	if err := json.Unmarshal(raw, &file); err != nil {
		t.Fatalf("decode malformed fixture %s: %v", name, err)
	}
	return adaptercontract.Fixture{
		CorrelationID: file.CorrelationID,
		Source:        file.Source,
		SourceURL:     file.SourceURL,
		ObservedAt:    file.ObservedAt,
		Payload:       json.RawMessage(file.PayloadText),
	}
}

func TestAdapterAcceptsSupportedWorldEvents(t *testing.T) {
	cases := []struct {
		name    string
		fixture string
	}{
		{"raw_observation", "raw_observation.json"},
		{"world_signal", "world_signal.json"},
		{"scout_health", "scout_health.json"},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			fixture := loadFixture(t, tc.fixture)
			r, err := Adapter{}.Adapt(context.Background(), fixture)
			if err != nil {
				t.Fatalf("Adapt returned error for valid %s fixture: %v", tc.name, err)
			}
			if err := adaptercontract.ValidateAccepted(fixture, r); err != nil {
				t.Fatalf("ValidateAccepted failed for %s: %v", tc.name, err)
			}
		})
	}
}

func TestAdapterIsDeterministic(t *testing.T) {
	fixture := loadFixture(t, "world_signal.json")
	first, err := Adapter{}.Adapt(context.Background(), fixture)
	if err != nil {
		t.Fatal(err)
	}
	second, err := Adapter{}.Adapt(context.Background(), fixture)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(first, second) {
		t.Fatalf("adapter must be deterministic; got %+v vs %+v", first, second)
	}
}

func TestAdapterRejectsMalformedJSON(t *testing.T) {
	fixture := loadMalformedFixture(t, "malformed_payload.json")
	r, err := Adapter{}.Adapt(context.Background(), fixture)
	if err := adaptercontract.ValidateRejected(fixture, r, err); err != nil {
		t.Fatalf("ValidateRejected failed: %v", err)
	}
	var rejectErr adaptercontract.RejectError
	if !errors.As(err, &rejectErr) {
		t.Fatalf("expected RejectError, got %T: %v", err, err)
	}
	if rejectErr.Reason != "malformed_json" {
		t.Fatalf("reason = %q, want malformed_json", rejectErr.Reason)
	}
}

func TestAdapterRejectsMissingRequiredFields(t *testing.T) {
	fixture := loadFixture(t, "missing_title.json")
	r, err := Adapter{}.Adapt(context.Background(), fixture)
	if err := adaptercontract.ValidateRejected(fixture, r, err); err != nil {
		t.Fatalf("ValidateRejected failed: %v", err)
	}
	var rejectErr adaptercontract.RejectError
	if !errors.As(err, &rejectErr) {
		t.Fatalf("expected RejectError, got %T: %v", err, err)
	}
	if rejectErr.Reason != "missing_required_fields:title" {
		t.Fatalf("reason = %q, want missing_required_fields:title", rejectErr.Reason)
	}
}

func TestAdapterRejectsInvalidScoreType(t *testing.T) {
	fixture := loadFixture(t, "bad_score.json")
	r, err := Adapter{}.Adapt(context.Background(), fixture)
	if err := adaptercontract.ValidateRejected(fixture, r, err); err != nil {
		t.Fatalf("ValidateRejected failed: %v", err)
	}
	var rejectErr adaptercontract.RejectError
	if !errors.As(err, &rejectErr) {
		t.Fatalf("expected RejectError, got %T: %v", err, err)
	}
	if rejectErr.Reason != "invalid_field_type:relevance_score" {
		t.Fatalf("reason = %q, want invalid_field_type:relevance_score", rejectErr.Reason)
	}
}

func TestAdapterRejectsUnsupportedEventType(t *testing.T) {
	fixture := loadFixture(t, "unsupported_event.json")
	r, err := Adapter{}.Adapt(context.Background(), fixture)
	if err := adaptercontract.ValidateRejected(fixture, r, err); err != nil {
		t.Fatalf("ValidateRejected failed: %v", err)
	}
	var rejectErr adaptercontract.RejectError
	if !errors.As(err, &rejectErr) {
		t.Fatalf("expected RejectError, got %T: %v", err, err)
	}
	if !strings.HasPrefix(rejectErr.Reason, "unsupported_event_type:") {
		t.Fatalf("reason = %q, want prefix unsupported_event_type:", rejectErr.Reason)
	}
}

func TestSupportedEventTypesIsCanonicalSorted(t *testing.T) {
	got := SupportedEventTypes()
	gotStrs := make([]string, len(got))
	for i, v := range got {
		gotStrs[i] = string(v)
	}
	sortedCopy := append([]string(nil), gotStrs...)
	sort.Strings(sortedCopy)
	if !reflect.DeepEqual(gotStrs, sortedCopy) {
		t.Fatalf("SupportedEventTypes must be sorted: %v", gotStrs)
	}
	wantSet := map[string]struct{}{
		"world_raw_observation": {},
		"world_signal":          {},
		"world_scout_health":    {},
	}
	if len(got) != len(wantSet) {
		t.Fatalf("event type count = %d, want %d", len(got), len(wantSet))
	}
	for _, v := range got {
		if _, ok := wantSet[string(v)]; !ok {
			t.Fatalf("unexpected event type %q", v)
		}
	}
}

func TestRequiredFieldsReturnsCopy(t *testing.T) {
	a, ok := RequiredFields(EventWorldSignal)
	if !ok {
		t.Fatal("EventWorldSignal must be supported")
	}
	if len(a) == 0 {
		t.Fatal("required fields must be non-empty")
	}
	a[0] = "TAMPERED"
	b, _ := RequiredFields(EventWorldSignal)
	if b[0] == "TAMPERED" {
		t.Fatal("RequiredFields must return a defensive copy")
	}
}

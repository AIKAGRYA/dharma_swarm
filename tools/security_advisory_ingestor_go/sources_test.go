package main

import (
	"encoding/json"
	"testing"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/sourceprobe"
)

func TestSecurityAdvisoryReceiptNoFetch(t *testing.T) {
	r, err := BuildReceipt(Options{
		CorrelationID: "corr_security_advisory_test",
		ObservedAt:    "2026-05-10T00:00:00Z",
		NoFetch:       true,
	})
	if err != nil {
		t.Fatal(err)
	}
	if r.Status != receipt.StatusAccepted || r.Source != SourceName {
		t.Fatalf("unexpected receipt: %+v", r)
	}
	if r.TrustEnvelope == nil || !r.TrustEnvelope.HumanReviewRequired {
		t.Fatalf("expected review trust envelope: %+v", r.TrustEnvelope)
	}
	var payload sourceprobe.AggregatePayload
	if err := json.Unmarshal(r.Payload, &payload); err != nil {
		t.Fatal(err)
	}
	if payload.IngestSchema != IngestSchema {
		t.Fatalf("schema = %s", payload.IngestSchema)
	}
	if payload.Summary.SourceCount != len(DefaultSources()) || payload.Summary.FetchedCount != 0 {
		t.Fatalf("unexpected summary: %+v", payload.Summary)
	}
}

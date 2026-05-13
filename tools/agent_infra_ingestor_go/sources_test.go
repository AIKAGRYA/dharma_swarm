package main

import (
	"encoding/json"
	"testing"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/sourceprobe"
)

func TestAgentInfraReceiptNoFetch(t *testing.T) {
	r, err := BuildReceipt(Options{
		CorrelationID: "corr_agent_infra_test",
		ObservedAt:    "2026-05-10T00:00:00Z",
		NoFetch:       true,
	})
	if err != nil {
		t.Fatal(err)
	}
	if r.Status != receipt.StatusAccepted || r.Source != SourceName {
		t.Fatalf("unexpected receipt: %+v", r)
	}
	if r.TrustEnvelope == nil || r.TrustEnvelope.RoutingClass != "human_only" {
		t.Fatalf("expected human-only trust envelope: %+v", r.TrustEnvelope)
	}
	var payload sourceprobe.AggregatePayload
	if err := json.Unmarshal(r.Payload, &payload); err != nil {
		t.Fatal(err)
	}
	if payload.Summary.SourceCount != len(DefaultSources()) {
		t.Fatalf("unexpected summary: %+v", payload.Summary)
	}
}

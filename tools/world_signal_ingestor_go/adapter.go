// Package world_signal_ingestor_go adapts outside-world observations into
// canonical Go evidence receipts.
//
// Boundary: this adapter validates and receipts world-signal payloads only.
// It does not fetch live sources, decide strategy, dispatch agents, write
// runtime DB, write ontology DB, or call Python policy. Python consumers may
// project accepted receipts into Zeitgeist/Shakti surfaces.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"sort"
	"strings"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/adaptercontract"
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

// WorldEventType is the discriminator carried in the fixture source field.
type WorldEventType string

const (
	EventWorldRawObservation WorldEventType = "world_raw_observation"
	EventWorldSignal         WorldEventType = "world_signal"
	EventWorldScoutHealth    WorldEventType = "world_scout_health"
)

// requiredFields maps each supported world event to JSON fields that must be
// present in the fixture payload. Order is canonical for deterministic reject
// reasons.
var requiredFields = map[WorldEventType][]string{
	EventWorldRawObservation: {"title"},
	EventWorldSignal:         {"title", "category", "relevance_score"},
	EventWorldScoutHealth:    {"source_count", "reachable_count", "item_count"},
}

// Adapter validates world-signal fixtures and emits accepted/rejected receipts.
// The zero value is usable.
type Adapter struct{}

// Adapt routes a fixture through per-event-type validation and returns either
// an accepted Receipt or a rejected Receipt plus RejectError.
func (Adapter) Adapt(_ context.Context, fixture adaptercontract.Fixture) (adaptercontract.Receipt, error) {
	eventType := WorldEventType(fixture.Source)
	required, ok := requiredFields[eventType]
	if !ok {
		reason := fmt.Sprintf("unsupported_event_type:%s", fixture.Source)
		return rejectedReceipt(fixture, reason)
	}

	payload, err := decodePayload(fixture.Payload)
	if err != nil {
		return rejectedReceipt(fixture, "malformed_json")
	}

	if missing := missingRequiredFields(payload, required); len(missing) > 0 {
		reason := "missing_required_fields:" + strings.Join(missing, ",")
		return rejectedReceipt(fixture, reason)
	}

	if eventType == EventWorldSignal && !isNumber(payload["relevance_score"]) {
		return rejectedReceipt(fixture, "invalid_field_type:relevance_score")
	}

	return receipt.Build(adaptercontract.BuildSpec(fixture), []byte(fixture.Payload))
}

// SupportedEventTypes returns the canonical sorted list of source strings the
// adapter accepts.
func SupportedEventTypes() []WorldEventType {
	out := make([]WorldEventType, 0, len(requiredFields))
	for k := range requiredFields {
		out = append(out, k)
	}
	sort.Slice(out, func(i, j int) bool { return string(out[i]) < string(out[j]) })
	return out
}

// RequiredFields returns a defensive copy of required fields for an event type.
func RequiredFields(eventType WorldEventType) ([]string, bool) {
	required, ok := requiredFields[eventType]
	if !ok {
		return nil, false
	}
	out := make([]string, len(required))
	copy(out, required)
	return out, true
}

func decodePayload(raw json.RawMessage) (map[string]any, error) {
	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	if out == nil {
		return nil, fmt.Errorf("payload is null")
	}
	return out, nil
}

func missingRequiredFields(payload map[string]any, required []string) []string {
	var missing []string
	for _, field := range required {
		value, ok := payload[field]
		if !ok || isBlankString(value) {
			missing = append(missing, field)
		}
	}
	return missing
}

func isBlankString(value any) bool {
	text, ok := value.(string)
	return ok && strings.TrimSpace(text) == ""
}

func isNumber(value any) bool {
	switch value.(type) {
	case float64, float32, int, int64, int32:
		return true
	default:
		return false
	}
}

func rejectedReceipt(fixture adaptercontract.Fixture, reason string) (adaptercontract.Receipt, error) {
	rejected, err := receipt.Reject(adaptercontract.BuildSpec(fixture), []byte(fixture.Payload), reason)
	if err != nil {
		return adaptercontract.Receipt{}, err
	}
	return rejected, adaptercontract.RejectError{Reason: reason}
}

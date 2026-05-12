// Package github_ingestor_go is the GitHub repository-event source-adapter.
// It implements adaptercontract.SourceAdapter for four event types
// (pull_request, commit, check_run, release) and emits canonical evidence
// receipts via tools/go_sdk/receipt.
//
// Boundary: this binary emits receipts only. It does not call the live GitHub
// API in CI (all tests are fixture-driven), it does not decide, dispatch,
// write runtime DB, write ontology DB, or call Python policy.
//
// The "source" field on the fixture / receipt encodes which GitHub event type
// the adapter is processing. Accepted source values:
//
//	github_pull_request
//	github_commit
//	github_check_run
//	github_release
//
// Each event type has a required-field set that must be present in the
// payload. Missing fields produce an explicit RejectError so the rejection is
// observable downstream and ValidateRejected in adaptercontract passes.
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

// GitHubEventType is the discriminator carried in the fixture's source field.
type GitHubEventType string

const (
	EventPullRequest GitHubEventType = "github_pull_request"
	EventCommit      GitHubEventType = "github_commit"
	EventCheckRun    GitHubEventType = "github_check_run"
	EventRelease     GitHubEventType = "github_release"
)

// requiredFields maps each accepted event type to the JSON keys that must be
// present in the payload. Order is canonical for deterministic error messages.
var requiredFields = map[GitHubEventType][]string{
	EventPullRequest: {"number", "state", "head_sha", "base_sha", "title"},
	EventCommit:      {"sha", "author", "message"},
	EventCheckRun:    {"id", "name", "status"},
	EventRelease:     {"tag_name", "name", "draft", "prerelease"},
}

// Adapter is the GitHub source-adapter. The zero value is usable.
type Adapter struct{}

// Adapt routes a fixture by source field through per-event-type validation
// and returns either an accepted Receipt or a (rejected Receipt, RejectError)
// pair. The error is always a RejectError on rejection so downstream tests
// can use errors.As to extract the reason.
func (Adapter) Adapt(_ context.Context, fixture adaptercontract.Fixture) (adaptercontract.Receipt, error) {
	eventType := GitHubEventType(fixture.Source)
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

	return receipt.Build(adaptercontract.BuildSpec(fixture), []byte(fixture.Payload))
}

// SupportedEventTypes returns the canonical sorted list of source strings the
// adapter accepts. Useful for CLI help and for tests that want to enumerate
// event types without duplicating the const list.
func SupportedEventTypes() []GitHubEventType {
	out := make([]GitHubEventType, 0, len(requiredFields))
	for k := range requiredFields {
		out = append(out, k)
	}
	sort.Slice(out, func(i, j int) bool { return string(out[i]) < string(out[j]) })
	return out
}

// RequiredFields returns the required JSON keys for an event type, or
// (nil, false) if the event type is not supported.
func RequiredFields(eventType GitHubEventType) ([]string, bool) {
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
		if _, ok := payload[field]; !ok {
			missing = append(missing, field)
		}
	}
	return missing
}

func rejectedReceipt(fixture adaptercontract.Fixture, reason string) (adaptercontract.Receipt, error) {
	rejected, err := receipt.Reject(adaptercontract.BuildSpec(fixture), []byte(fixture.Payload), reason)
	if err != nil {
		return adaptercontract.Receipt{}, err
	}
	return rejected, adaptercontract.RejectError{Reason: reason}
}

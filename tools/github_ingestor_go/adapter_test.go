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

const (
	testCorrelationID = "corr_v0_test_001"
	testObservedAt    = "2026-05-09T00:00:00Z"
)

// fixturePath resolves a fixture file in the shared tests/fixtures tree.
// The tree lives at <repo>/tests/fixtures/go_github_ingestor.
func fixturePath(name string) string {
	return filepath.Join("..", "..", "tests", "fixtures", "go_github_ingestor", name)
}

// loadFixture reads a canonical adaptercontract.Fixture from JSON.
func loadFixture(t *testing.T, name string) adaptercontract.Fixture {
	t.Helper()
	f, err := adaptercontract.LoadFixture(fixturePath(name))
	if err != nil {
		t.Fatalf("load fixture %s: %v", name, err)
	}
	return f
}

// loadMalformedFixture reads a fixture whose payload is intentionally not
// valid JSON. The on-disk shape stores the bad payload as a string in
// payload_text so the file itself stays parseable.
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

// ---------------------------------------------------------------------------
// Acceptance: every supported event type
// ---------------------------------------------------------------------------

func TestAdapterAcceptsAllSupportedEventTypes(t *testing.T) {
	cases := []struct {
		name    string
		fixture string
	}{
		{"pull_request", "pr_opened.json"},
		{"commit", "commit_pushed.json"},
		{"check_run", "check_run_completed.json"},
		{"release", "release_published.json"},
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

// ---------------------------------------------------------------------------
// Determinism: identical inputs produce identical receipts
// ---------------------------------------------------------------------------

func TestAdapterIsDeterministic(t *testing.T) {
	fixture := loadFixture(t, "pr_opened.json")
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

// ---------------------------------------------------------------------------
// Reject: malformed JSON
// ---------------------------------------------------------------------------

func TestAdapterRejectsMalformedJSON(t *testing.T) {
	fixture := loadMalformedFixture(t, "pr_malformed.json")
	r, err := Adapter{}.Adapt(context.Background(), fixture)
	if err := adaptercontract.ValidateRejected(fixture, r, err); err != nil {
		t.Fatalf("ValidateRejected failed: %v", err)
	}
	var rejectErr adaptercontract.RejectError
	if !errors.As(err, &rejectErr) {
		t.Fatalf("expected RejectError, got %T: %v", err, err)
	}
	if rejectErr.Reason != "malformed_json" {
		t.Fatalf("reason = %q, want %q", rejectErr.Reason, "malformed_json")
	}
}

// ---------------------------------------------------------------------------
// Reject: missing required field
// ---------------------------------------------------------------------------

func TestAdapterRejectsMissingRequiredFields(t *testing.T) {
	fixture := loadFixture(t, "pr_missing_fields.json")
	r, err := Adapter{}.Adapt(context.Background(), fixture)
	if err := adaptercontract.ValidateRejected(fixture, r, err); err != nil {
		t.Fatalf("ValidateRejected failed: %v", err)
	}
	var rejectErr adaptercontract.RejectError
	if !errors.As(err, &rejectErr) {
		t.Fatalf("expected RejectError, got %T: %v", err, err)
	}
	if !strings.HasPrefix(rejectErr.Reason, "missing_required_fields:") {
		t.Fatalf("reason = %q, want prefix missing_required_fields:", rejectErr.Reason)
	}
	// pr_missing_fields.json drops "title" and "base_sha"; the reject reason
	// must list both, in the canonical order from requiredFields.
	wantContains := []string{"title", "base_sha"}
	for _, sub := range wantContains {
		if !strings.Contains(rejectErr.Reason, sub) {
			t.Fatalf("reason = %q, missing expected substring %q", rejectErr.Reason, sub)
		}
	}
}

// ---------------------------------------------------------------------------
// Reject: unsupported event type
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Frozen golden receipt for the PR fixture (regression lock)
//
// On first run the golden file does not exist; the test writes it and skips
// the comparison that turn. On every subsequent run it compares against the
// committed bytes. Set GOLDEN_REWRITE=1 to force a rewrite when the canonical
// receipt shape changes intentionally.
// ---------------------------------------------------------------------------

func TestPullRequestGoldenReceipt(t *testing.T) {
	fixture := loadFixture(t, "pr_opened.json")
	got, err := Adapter{}.Adapt(context.Background(), fixture)
	if err != nil {
		t.Fatal(err)
	}
	goldenPath := fixturePath("expected_pr_opened.json")
	if _, err := os.Stat(goldenPath); errors.Is(err, os.ErrNotExist) || os.Getenv("GOLDEN_REWRITE") == "1" {
		gotJSON, _ := json.MarshalIndent(got, "", "  ")
		gotJSON = append(gotJSON, '\n')
		if err := os.WriteFile(goldenPath, gotJSON, 0o644); err != nil {
			t.Fatalf("write golden: %v", err)
		}
		t.Logf("wrote golden receipt to %s; rerun to verify", goldenPath)
		return
	}
	wantRaw, err := os.ReadFile(goldenPath)
	if err != nil {
		t.Fatal(err)
	}
	var want adaptercontract.Receipt
	if err := json.Unmarshal(wantRaw, &want); err != nil {
		t.Fatal(err)
	}
	if got.ReceiptID != want.ReceiptID || got.EventUID != want.EventUID || got.ContentHash != want.ContentHash {
		gotJSON, _ := json.MarshalIndent(got, "", "  ")
		wantJSON, _ := json.MarshalIndent(want, "", "  ")
		t.Fatalf("PR receipt drifted from golden\n got:  %s\n want: %s", gotJSON, wantJSON)
	}
}

// ---------------------------------------------------------------------------
// Inventory: SupportedEventTypes / RequiredFields stay stable
// ---------------------------------------------------------------------------

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
		"github_pull_request": {},
		"github_commit":       {},
		"github_check_run":    {},
		"github_release":      {},
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
	a, ok := RequiredFields(EventPullRequest)
	if !ok {
		t.Fatal("EventPullRequest must be supported")
	}
	if len(a) == 0 {
		t.Fatal("required fields must be non-empty")
	}
	a[0] = "TAMPERED"
	b, _ := RequiredFields(EventPullRequest)
	if b[0] == "TAMPERED" {
		t.Fatal("RequiredFields must return a defensive copy, not the underlying slice")
	}
}

func TestRequiredFieldsReturnsFalseForUnknown(t *testing.T) {
	if _, ok := RequiredFields(GitHubEventType("unknown")); ok {
		t.Fatal("RequiredFields must return false for unsupported types")
	}
}

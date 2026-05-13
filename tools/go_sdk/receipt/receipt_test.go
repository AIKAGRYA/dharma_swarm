package receipt

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"sync"
	"testing"
)

const (
	fixedObservedAt = "2026-05-09T00:00:00Z"
	fixedSource     = "agentops_fixture"
	fixedSourceURL  = "fixture://agentops/success"
	fixedCorrID     = "corr_v0_test_001"
)

func okSpec() BuildSpec {
	return BuildSpec{
		Source:        fixedSource,
		SourceURL:     fixedSourceURL,
		CorrelationID: fixedCorrID,
		ObservedAt:    fixedObservedAt,
		SchemaVersion: DefaultSchemaVersion,
	}
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

func TestBuildRejectsMissingCorrelationID(t *testing.T) {
	spec := okSpec()
	spec.CorrelationID = ""
	if _, err := Build(spec, []byte(`{"ok":true}`)); err == nil {
		t.Fatal("expected error when correlation_id is empty")
	}
}

func TestBuildRejectsMissingSource(t *testing.T) {
	spec := okSpec()
	spec.Source = ""
	if _, err := Build(spec, []byte(`{"ok":true}`)); err == nil {
		t.Fatal("expected error when source is empty")
	}
}

func TestBuildRejectsMissingSourceURL(t *testing.T) {
	spec := okSpec()
	spec.SourceURL = ""
	if _, err := Build(spec, []byte(`{"ok":true}`)); err == nil {
		t.Fatal("expected error when source_url is empty")
	}
}

func TestBuildRejectsMalformedObservedAt(t *testing.T) {
	spec := okSpec()
	spec.ObservedAt = "yesterday"
	if _, err := Build(spec, []byte(`{"ok":true}`)); err == nil {
		t.Fatal("expected error when observed_at is not RFC3339")
	}
}

func TestBuildDefaultsSchemaVersion(t *testing.T) {
	spec := okSpec()
	spec.SchemaVersion = ""
	r, err := Build(spec, []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	if r.SchemaVersion != DefaultSchemaVersion {
		t.Fatalf("schema_version default got %q want %q", r.SchemaVersion, DefaultSchemaVersion)
	}
}

func TestBuildDefaultsObservedAtToNow(t *testing.T) {
	spec := okSpec()
	spec.ObservedAt = ""
	r, err := Build(spec, []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	if r.ObservedAt == "" {
		t.Fatal("observed_at must default to now when empty")
	}
}

func TestBuildCarriesTrustEnvelope(t *testing.T) {
	spec := okSpec()
	spec.TrustEnvelope = &TrustEnvelope{
		OriginAttestation:      "signed",
		CorroborationCount:     2,
		FreshnessWindow:        "24h",
		LicenseCompatibility:   "review_required",
		HallucinationRiskClass: "raw_data",
		RoutingClass:           "review",
		HumanReviewRequired:    true,
	}
	r, err := Build(spec, []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	if r.TrustEnvelope == nil {
		t.Fatal("trust envelope was not carried on receipt")
	}
	if r.TrustEnvelope.CorroborationCount != 2 || r.TrustEnvelope.RoutingClass != "review" {
		t.Fatalf("unexpected trust envelope: %+v", r.TrustEnvelope)
	}

	spec.TrustEnvelope.RoutingClass = "auto"
	if r.TrustEnvelope.RoutingClass != "review" {
		t.Fatal("receipt must copy trust envelope instead of aliasing caller data")
	}
}

func TestTrustEnvelopeDoesNotChangeReceiptIdentity(t *testing.T) {
	payload := []byte(`{"ok":true}`)
	plain, err := Build(okSpec(), payload)
	if err != nil {
		t.Fatal(err)
	}
	spec := okSpec()
	spec.TrustEnvelope = &TrustEnvelope{
		OriginAttestation:      "unsigned",
		CorroborationCount:     1,
		FreshnessWindow:        "24h",
		LicenseCompatibility:   "unknown",
		HallucinationRiskClass: "raw_data",
		RoutingClass:           "human_only",
	}
	withTrust, err := Build(spec, payload)
	if err != nil {
		t.Fatal(err)
	}
	if plain.ContentHash != withTrust.ContentHash || plain.EventUID != withTrust.EventUID || plain.ReceiptID != withTrust.ReceiptID {
		t.Fatalf("trust envelope must not alter receipt identity: plain=%+v trusted=%+v", plain, withTrust)
	}
}

func TestBuildRejectsInvalidTrustEnvelope(t *testing.T) {
	spec := okSpec()
	spec.TrustEnvelope = &TrustEnvelope{
		OriginAttestation:      "unsigned",
		CorroborationCount:     -1,
		FreshnessWindow:        "24h",
		LicenseCompatibility:   "unknown",
		HallucinationRiskClass: "raw_data",
		RoutingClass:           "review",
	}
	if _, err := Build(spec, []byte(`{"ok":true}`)); err == nil {
		t.Fatal("expected invalid trust envelope to be rejected")
	}
}

// ---------------------------------------------------------------------------
// Hashing / determinism
// ---------------------------------------------------------------------------

func TestBuildIsDeterministic(t *testing.T) {
	payload := []byte(`{"gate_state":"all_green","scope_state":"scope_clean"}`)
	a, err := Build(okSpec(), payload)
	if err != nil {
		t.Fatal(err)
	}
	b, err := Build(okSpec(), payload)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(a, b) {
		t.Fatalf("Build must be deterministic for fixed inputs:\n%+v\n%+v", a, b)
	}
	if a.ContentHash == "" || a.EventUID == "" || a.ReceiptID == "" {
		t.Fatalf("identity fields must be populated: %+v", a)
	}
}

func TestContentChangeChangesEventUID(t *testing.T) {
	a, err := Build(okSpec(), []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	b, err := Build(okSpec(), []byte(`{"ok":false}`))
	if err != nil {
		t.Fatal(err)
	}
	if a.EventUID == b.EventUID {
		t.Fatalf("event_uid must change when payload bytes change: %s", a.EventUID)
	}
	if a.ContentHash == b.ContentHash {
		t.Fatalf("content_hash must change when payload bytes change: %s", a.ContentHash)
	}
	if a.ReceiptID == b.ReceiptID {
		t.Fatalf("receipt_id must change when event_uid changes: %s", a.ReceiptID)
	}
}

func TestSourceChangeChangesEventUID(t *testing.T) {
	specA := okSpec()
	specB := okSpec()
	specB.Source = "different_source"
	a, err := Build(specA, []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	b, err := Build(specB, []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	if a.EventUID == b.EventUID {
		t.Fatal("event_uid must change when source changes")
	}
}

func TestCorrelationChangeChangesReceiptIDOnly(t *testing.T) {
	specA := okSpec()
	specB := okSpec()
	specB.CorrelationID = "corr_other_002"
	a, err := Build(specA, []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	b, err := Build(specB, []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	if a.ContentHash != b.ContentHash {
		t.Fatal("content_hash must NOT depend on correlation_id")
	}
	if a.EventUID != b.EventUID {
		t.Fatal("event_uid must NOT depend on correlation_id")
	}
	if a.ReceiptID == b.ReceiptID {
		t.Fatal("receipt_id MUST change when correlation_id changes")
	}
}

func TestHashHelpersMatchBuild(t *testing.T) {
	payload := []byte(`{"ok":true}`)
	r, err := Build(okSpec(), payload)
	if err != nil {
		t.Fatal(err)
	}
	if got := ContentHash(payload); got != r.ContentHash {
		t.Fatalf("ContentHash mismatch: %s vs %s", got, r.ContentHash)
	}
	if got := EventUID(fixedSource, fixedSourceURL, r.ContentHash); got != r.EventUID {
		t.Fatalf("EventUID mismatch: %s vs %s", got, r.EventUID)
	}
	if got := ReceiptID(fixedCorrID, r.EventUID); got != r.ReceiptID {
		t.Fatalf("ReceiptID mismatch: %s vs %s", got, r.ReceiptID)
	}
}

// ---------------------------------------------------------------------------
// Reject semantics
// ---------------------------------------------------------------------------

func TestRejectRequiresReason(t *testing.T) {
	_, err := Reject(okSpec(), []byte(`{"ok":true}`), "")
	if err == nil {
		t.Fatal("Reject must require a non-empty reason")
	}
}

func TestRejectStillValidatesSpec(t *testing.T) {
	spec := okSpec()
	spec.CorrelationID = ""
	if _, err := Reject(spec, []byte(`{"ok":true}`), "schema_invalid"); err == nil {
		t.Fatal("Reject must validate spec like Build does")
	}
}

func TestRejectProducesRejectedStatus(t *testing.T) {
	r, err := Reject(okSpec(), []byte(`{"ok":true}`), "schema_invalid")
	if err != nil {
		t.Fatal(err)
	}
	if r.Status != StatusRejected {
		t.Fatalf("status got %q want %q", r.Status, StatusRejected)
	}
	if r.RejectedReason != "schema_invalid" {
		t.Fatalf("rejected_reason got %q want %q", r.RejectedReason, "schema_invalid")
	}
	if r.ReceiptID == "" || r.EventUID == "" || r.ContentHash == "" {
		t.Fatalf("rejected receipts must still carry identity fields: %+v", r)
	}
}

func TestRejectAllowsEmptyPayload(t *testing.T) {
	r, err := Reject(okSpec(), []byte(""), "empty_payload")
	if err != nil {
		t.Fatal(err)
	}
	// Empty payload normalization fails; reject must still produce a usable record
	// with payload set to JSON null.
	if string(r.Payload) != "null" {
		t.Fatalf("rejected receipt payload for empty input got %q want \"null\"", string(r.Payload))
	}
}

func TestBuildAndRejectShareIdentityForSameInputs(t *testing.T) {
	payload := []byte(`{"ok":true}`)
	accepted, err := Build(okSpec(), payload)
	if err != nil {
		t.Fatal(err)
	}
	rejected, err := Reject(okSpec(), payload, "demoted")
	if err != nil {
		t.Fatal(err)
	}
	if accepted.ContentHash != rejected.ContentHash {
		t.Fatal("content_hash must be identical for same payload regardless of status")
	}
	if accepted.EventUID != rejected.EventUID {
		t.Fatal("event_uid must be identical for same (source,url,content) regardless of status")
	}
	if accepted.ReceiptID != rejected.ReceiptID {
		t.Fatal("receipt_id must be identical for same (correlation,event) regardless of status")
	}
}

// ---------------------------------------------------------------------------
// JSON normalization
// ---------------------------------------------------------------------------

func TestNormalizePassesThroughValidJSONObject(t *testing.T) {
	raw, err := Normalize([]byte(`{"a":1,"b":[2,3]}`))
	if err != nil {
		t.Fatal(err)
	}
	var got map[string]any
	if err := json.Unmarshal(raw, &got); err != nil {
		t.Fatal(err)
	}
	if got["a"].(float64) != 1 {
		t.Fatalf("normalize lost data: %s", string(raw))
	}
}

func TestNormalizePassesThroughValidJSONArray(t *testing.T) {
	raw, err := Normalize([]byte(`[1,2,3]`))
	if err != nil {
		t.Fatal(err)
	}
	if !json.Valid(raw) {
		t.Fatal("normalized array is not valid JSON")
	}
}

func TestNormalizeWrapsNonJSON(t *testing.T) {
	raw, err := Normalize([]byte("hello world"))
	if err != nil {
		t.Fatal(err)
	}
	var wrapped map[string]string
	if err := json.Unmarshal(raw, &wrapped); err != nil {
		t.Fatal(err)
	}
	if wrapped["raw_text"] != "hello world" {
		t.Fatalf("wrap shape changed: %+v", wrapped)
	}
}

func TestNormalizeRejectsEmpty(t *testing.T) {
	if _, err := Normalize([]byte("")); err == nil {
		t.Fatal("Normalize must reject empty input")
	}
	if _, err := Normalize([]byte("   \n\t")); err == nil {
		t.Fatal("Normalize must reject whitespace-only input")
	}
}

func TestNormalizeTrimsWhitespaceForJSONDetection(t *testing.T) {
	raw, err := Normalize([]byte(`  {"ok":true}  `))
	if err != nil {
		t.Fatal(err)
	}
	if !json.Valid(raw) {
		t.Fatalf("trimmed JSON should validate: %s", string(raw))
	}
}

// ---------------------------------------------------------------------------
// Atomic writes
// ---------------------------------------------------------------------------

func TestWriteCreatesParentDirectory(t *testing.T) {
	dir := t.TempDir()
	target := filepath.Join(dir, "nested", "deep", "receipt.json")
	r, err := Build(okSpec(), []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	if err := Write(target, r); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(target); err != nil {
		t.Fatalf("expected receipt at %s: %v", target, err)
	}
}

func TestWriteRoundTrip(t *testing.T) {
	dir := t.TempDir()
	target := filepath.Join(dir, "receipt.json")
	r, err := Build(okSpec(), []byte(`{"ok":true,"n":42}`))
	if err != nil {
		t.Fatal(err)
	}
	if err := Write(target, r); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(target)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasSuffix(string(raw), "\n") {
		t.Fatal("Write output must end in a newline")
	}
	var decoded Receipt
	if err := json.Unmarshal(raw, &decoded); err != nil {
		t.Fatal(err)
	}
	if decoded.ReceiptID != r.ReceiptID || decoded.EventUID != r.EventUID || decoded.ContentHash != r.ContentHash {
		t.Fatalf("round-trip identity mismatch:\n%+v\n%+v", decoded, r)
	}
	var payload map[string]any
	if err := json.Unmarshal(decoded.Payload, &payload); err != nil {
		t.Fatal(err)
	}
	if payload["ok"] != true || payload["n"].(float64) != 42 {
		t.Fatalf("payload corrupted: %+v", payload)
	}
}

func TestWriteAtomicReplacesExistingFile(t *testing.T) {
	dir := t.TempDir()
	target := filepath.Join(dir, "receipt.json")
	if err := os.WriteFile(target, []byte("placeholder"), 0o644); err != nil {
		t.Fatal(err)
	}
	r, err := Build(okSpec(), []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	if err := Write(target, r); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(target)
	if err != nil {
		t.Fatal(err)
	}
	if string(raw) == "placeholder" {
		t.Fatal("Write must replace existing file content")
	}
	if !json.Valid(raw) {
		t.Fatalf("post-replace content must be valid JSON, got: %s", string(raw))
	}
}

func TestWriteLeavesNoTempFileOnSuccess(t *testing.T) {
	dir := t.TempDir()
	target := filepath.Join(dir, "receipt.json")
	r, err := Build(okSpec(), []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	if err := Write(target, r); err != nil {
		t.Fatal(err)
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 {
		var names []string
		for _, e := range entries {
			names = append(names, e.Name())
		}
		t.Fatalf("expected 1 file, got %d: %v", len(entries), names)
	}
	if entries[0].Name() != "receipt.json" {
		t.Fatalf("temp file leaked: %s", entries[0].Name())
	}
}

func TestWriteFailsWhenDirCannotBeCreated(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("running as root; skipping unwritable-parent test")
	}
	dir := t.TempDir()
	blocker := filepath.Join(dir, "blocker")
	// Create a read-only parent so MkdirAll on a child fails.
	if err := os.MkdirAll(blocker, 0o500); err != nil {
		t.Fatal(err)
	}
	defer os.Chmod(blocker, 0o755)
	target := filepath.Join(blocker, "child", "receipt.json")
	r, err := Build(okSpec(), []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	if err := Write(target, r); err == nil {
		t.Fatal("expected Write to fail under unwritable parent")
	}
}

func TestWriteIsConcurrencySafeForDistinctPaths(t *testing.T) {
	dir := t.TempDir()
	r, err := Build(okSpec(), []byte(`{"ok":true}`))
	if err != nil {
		t.Fatal(err)
	}
	const n = 8
	var wg sync.WaitGroup
	errs := make(chan error, n)
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			path := filepath.Join(dir, "r_"+fmtInt(i)+".json")
			if err := Write(path, r); err != nil {
				errs <- err
			}
		}(i)
	}
	wg.Wait()
	close(errs)
	var collected []error
	for e := range errs {
		collected = append(collected, e)
	}
	if len(collected) > 0 {
		t.Fatalf("concurrent writes failed: %v", errors.Join(collected...))
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != n {
		t.Fatalf("expected %d files after concurrent writes, got %d", n, len(entries))
	}
}

// fmtInt renders a small non-negative int without pulling in strconv to keep
// imports tight; the tests only need values 0..n.
func fmtInt(i int) string {
	if i == 0 {
		return "0"
	}
	var digits []byte
	for i > 0 {
		digits = append([]byte{byte('0' + i%10)}, digits...)
		i /= 10
	}
	return string(digits)
}

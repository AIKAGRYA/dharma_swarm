package spool

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

const fixedObservedAt = "2026-05-09T00:00:00Z"

func testReceipt(t *testing.T, corrID string, payload []byte) receipt.Receipt {
	t.Helper()
	r, err := receipt.Build(receipt.BuildSpec{
		Source:        "spool_fixture",
		SourceURL:     "fixture://spool/" + corrID,
		CorrelationID: corrID,
		ObservedAt:    fixedObservedAt,
	}, payload)
	if err != nil {
		t.Fatal(err)
	}
	return r
}

func TestAppendIsIdempotentByReceiptID(t *testing.T) {
	dir := t.TempDir()
	r := testReceipt(t, "corr_spool_001", []byte(`{"ok":true}`))

	first, err := Append(dir, r, "world_projection")
	if err != nil {
		t.Fatal(err)
	}
	second, err := Append(dir, r, "world_projection")
	if err != nil {
		t.Fatal(err)
	}

	if first.SpoolID != r.ReceiptID || second.SpoolID != first.SpoolID {
		t.Fatalf("unexpected spool identity: first=%+v second=%+v", first, second)
	}
	if first.FirstSeenAt != second.FirstSeenAt {
		t.Fatalf("duplicate append must return existing entry, got %q then %q", first.FirstSeenAt, second.FirstSeenAt)
	}
	files, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil {
		t.Fatal(err)
	}
	if len(files) != 1 {
		t.Fatalf("duplicate append wrote %d files, want 1", len(files))
	}
}

func TestReplayPendingIsIdempotentAfterDelivery(t *testing.T) {
	dir := t.TempDir()
	a := testReceipt(t, "corr_spool_a", []byte(`{"n":1}`))
	b := testReceipt(t, "corr_spool_b", []byte(`{"n":2}`))
	if _, err := Append(dir, a, "world_projection"); err != nil {
		t.Fatal(err)
	}
	if _, err := Append(dir, b, "world_projection"); err != nil {
		t.Fatal(err)
	}

	delivered := []string{}
	first, err := ReplayPending(dir, "world_projection", func(entry Entry) error {
		delivered = append(delivered, entry.SpoolID)
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(first.Delivered) != 2 || len(delivered) != 2 {
		t.Fatalf("first replay delivered=%d callback=%d", len(first.Delivered), len(delivered))
	}

	second, err := ReplayPending(dir, "world_projection", func(entry Entry) error {
		t.Fatalf("delivered entry replayed again: %+v", entry)
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(second.Delivered) != 0 || len(second.Failed) != 0 {
		t.Fatalf("second replay must be a no-op, got %+v", second)
	}

	list, err := List(dir, StateDelivered)
	if err != nil {
		t.Fatal(err)
	}
	for _, entry := range list.Entries {
		if entry.AttemptCount != 1 || entry.LastAttemptAt == nil {
			t.Fatalf("delivered entry did not record one attempt: %+v", entry)
		}
	}
}

func TestReplayMarksFailedEntries(t *testing.T) {
	dir := t.TempDir()
	r := testReceipt(t, "corr_spool_fail", []byte(`{"ok":false}`))
	if _, err := Append(dir, r, "world_projection"); err != nil {
		t.Fatal(err)
	}

	result, err := ReplayPending(dir, "world_projection", func(entry Entry) error {
		return errors.New("projection failed")
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Failed) != 1 || result.Failed[0].LastError == nil || *result.Failed[0].LastError != "projection failed" {
		t.Fatalf("expected failed entry with error, got %+v", result)
	}

	failed, err := List(dir, StateFailed)
	if err != nil {
		t.Fatal(err)
	}
	if len(failed.Entries) != 1 || failed.Entries[0].AttemptCount != 1 {
		t.Fatalf("failed entry not persisted correctly: %+v", failed)
	}
}

func TestListReportsCorruptEntriesWithoutBlockingValidEntries(t *testing.T) {
	dir := t.TempDir()
	r := testReceipt(t, "corr_spool_valid", []byte(`{"ok":true}`))
	if _, err := Append(dir, r, "world_projection"); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "corrupt.json"), []byte(`{not json`), 0o644); err != nil {
		t.Fatal(err)
	}

	result, err := List(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Entries) != 1 {
		t.Fatalf("valid entry was blocked by corrupt file: %+v", result)
	}
	if len(result.Errors) != 1 || result.Errors[0].Path == "" {
		t.Fatalf("corrupt entry was not reported: %+v", result)
	}
}

func TestConsumerMismatchIsRejected(t *testing.T) {
	dir := t.TempDir()
	r := testReceipt(t, "corr_spool_consumer", []byte(`{"ok":true}`))
	entry, err := Append(dir, r, "world_projection")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := MarkDelivered(dir, entry.SpoolID, "other_projection"); err == nil {
		t.Fatal("expected consumer mismatch to fail")
	}
}

package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

const fixedObservedAt = "2026-05-09T00:00:00Z"

func writeTempPayload(t *testing.T, dir string, body string) string {
	t.Helper()
	path := filepath.Join(dir, "payload.json")
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

func baseOptions(input, output string) Options {
	return Options{
		InputPath:     input,
		OutputPath:    output,
		Source:        "agentops_fixture",
		SourceURL:     "fixture://agentops/success",
		CorrelationID: "corr_v0_test_001",
		ObservedAt:    fixedObservedAt,
		SchemaVersion: defaultSchemaVersion,
	}
}

func TestBuildReceiptIsDeterministic(t *testing.T) {
	dir := t.TempDir()
	input := writeTempPayload(t, dir, `{"gate_state":"all_green","scope_state":"scope_clean"}`)
	opts := baseOptions(input, filepath.Join(dir, "receipt.json"))

	a, err := BuildReceipt(opts)
	if err != nil {
		t.Fatal(err)
	}
	b, err := BuildReceipt(opts)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(a, b) {
		t.Fatalf("receipt must be deterministic:\n%+v\n%+v", a, b)
	}
	if a.ContentHash == "" || a.EventUID == "" || a.ReceiptID == "" {
		t.Fatalf("missing identity fields: %+v", a)
	}
}

func TestBuildReceiptRejectsMissingCorrelationID(t *testing.T) {
	dir := t.TempDir()
	input := writeTempPayload(t, dir, `{"ok":true}`)
	opts := baseOptions(input, filepath.Join(dir, "receipt.json"))
	opts.CorrelationID = ""

	_, err := BuildReceipt(opts)
	if err == nil {
		t.Fatal("expected missing correlation id error")
	}
}

func TestContentChangeChangesEventUID(t *testing.T) {
	dir := t.TempDir()
	input := writeTempPayload(t, dir, `{"ok":true}`)
	opts := baseOptions(input, filepath.Join(dir, "receipt.json"))
	a, err := BuildReceipt(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(input, []byte(`{"ok":false}`), 0o644); err != nil {
		t.Fatal(err)
	}
	b, err := BuildReceipt(opts)
	if err != nil {
		t.Fatal(err)
	}
	if a.EventUID == b.EventUID {
		t.Fatalf("event uid must change when content changes: %s", a.EventUID)
	}
}

func TestWriteReceiptRoundTrip(t *testing.T) {
	dir := t.TempDir()
	input := writeTempPayload(t, dir, `{"ok":true}`)
	output := filepath.Join(dir, "out", "receipt.json")
	receipt, err := BuildReceipt(baseOptions(input, output))
	if err != nil {
		t.Fatal(err)
	}
	if err := WriteReceipt(output, receipt); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(output)
	if err != nil {
		t.Fatal(err)
	}
	var decoded EvidenceReceipt
	if err := json.Unmarshal(raw, &decoded); err != nil {
		t.Fatal(err)
	}
	if decoded.ReceiptID != receipt.ReceiptID || decoded.EventUID != receipt.EventUID {
		t.Fatalf("round trip identity mismatch:\n%+v\n%+v", decoded, receipt)
	}
	var payload map[string]bool
	if err := json.Unmarshal(decoded.Payload, &payload); err != nil {
		t.Fatal(err)
	}
	if !payload["ok"] {
		t.Fatalf("payload lost during round trip: %s", string(decoded.Payload))
	}
}

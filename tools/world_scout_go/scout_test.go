package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestCollectWorldWritesHealthSummary(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/rss+xml")
		_, _ = w.Write([]byte(`<rss><channel><item><title>SubQ-style long context agent infra</title><link>https://example.test/subq</link><description>Subquadratic inference for coding agents</description></item></channel></rss>`))
	}))
	defer server.Close()

	sources := []Source{{ID: "unit_rss", Family: "agent_infra", Title: "Unit RSS", URL: server.URL, Kind: "rss", Publisher: "Unit", Keywords: []string{"agent infra"}}}
	result, err := CollectWorld(Options{Fetch: true, TimeoutMS: 1000, MaxBodyBytes: 1 << 20}, sources)
	if err != nil {
		t.Fatal(err)
	}
	if result.ReachableCount != 1 || result.ItemCount != 1 {
		t.Fatalf("unexpected health: %#v", result)
	}
	path := filepath.Join(t.TempDir(), "health.json")
	if err := WriteHealth(path, result); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var health ScoutResult
	if err := json.Unmarshal(raw, &health); err != nil {
		t.Fatal(err)
	}
	if health.Sources[0].SourceID != "unit_rss" || !health.Sources[0].Reachable {
		t.Fatalf("bad health payload: %#v", health.Sources[0])
	}
}

func TestCollectWorldDisabledDoesNotFetch(t *testing.T) {
	sources := []Source{{ID: "disabled", Family: "ai_frontier", Title: "Disabled", URL: "http://127.0.0.1:1/nope", Kind: "rss"}}
	result, err := CollectWorld(Options{Fetch: false}, sources)
	if err != nil {
		t.Fatal(err)
	}
	if result.FetchEnabled || result.ItemCount != 0 || len(result.Observations) != 0 {
		t.Fatalf("disabled scout fetched: %#v", result)
	}
}

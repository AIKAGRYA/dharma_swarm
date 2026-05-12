package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestCollectObservationsNoFetchEmitsSixFamilies(t *testing.T) {
	rows, err := CollectObservations(Options{Fetch: false, ObservedAt: "2026-05-12T00:00:00Z"}, DefaultSources())
	if err != nil {
		t.Fatal(err)
	}
	families := map[string]bool{}
	for _, row := range rows {
		families[row.Source] = true
	}
	want := []string{
		"world_scout_go:ai_frontier",
		"world_scout_go:practitioner",
		"world_scout_go:agent_infra",
		"world_scout_go:product_company",
		"world_scout_go:github",
		"world_scout_go:security_regulatory",
	}
	for _, family := range want {
		if !families[family] {
			t.Fatalf("missing family %s in %#v", family, families)
		}
	}
}

func TestCollectWorldWritesHealthSummary(t *testing.T) {
	result, err := CollectWorld(Options{Fetch: false, ObservedAt: "2026-05-12T00:00:00Z"}, DefaultSources())
	if err != nil {
		t.Fatal(err)
	}
	if result.SourceCount == 0 || len(result.Sources) != result.SourceCount {
		t.Fatalf("bad source counts: %+v", result)
	}
	if result.FetchEnabled {
		t.Fatal("fetch should be disabled")
	}

	dir := t.TempDir()
	health := filepath.Join(dir, "world_scout_health.json")
	if err := WriteHealth(health, result); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(health)
	if err != nil {
		t.Fatal(err)
	}
	var stored ScoutResult
	if err := json.Unmarshal(raw, &stored); err != nil {
		t.Fatal(err)
	}
	if stored.SourceCount != result.SourceCount {
		t.Fatalf("stored source_count=%d want %d", stored.SourceCount, result.SourceCount)
	}
}

func TestRSSFetchExtractsSubQObservation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/rss+xml")
		_, _ = w.Write([]byte(`<?xml version="1.0"?><rss><channel><item><title>SubQ claims subquadratic long-context LLM for coding agents</title><link>https://subq.ai/</link><description>SubQ launches an OpenAI-compatible API for coding agents.</description><pubDate>Tue, 12 May 2026 00:00:00 GMT</pubDate></item></channel></rss>`))
	}))
	defer server.Close()

	source := SourceDefinition{
		ID:        "product_hunt_test",
		Family:    "product_company",
		Title:     "Product test",
		URL:       server.URL,
		Kind:      "rss_feed",
		Publisher: "Product Test",
		Keywords:  []string{"product launch"},
	}
	rows, err := CollectObservations(
		Options{Fetch: true, ObservedAt: "2026-05-12T00:00:00Z", TimeoutMS: 1000},
		[]SourceDefinition{source},
	)
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 1 {
		t.Fatalf("len(rows) = %d, want 1", len(rows))
	}
	if rows[0].Title != "SubQ claims subquadratic long-context LLM for coding agents" {
		t.Fatalf("title = %q", rows[0].Title)
	}
	if rows[0].SourceURL != "https://subq.ai/" {
		t.Fatalf("source_url = %q", rows[0].SourceURL)
	}
}

func TestWriteObservationsJSONL(t *testing.T) {
	dir := t.TempDir()
	output := filepath.Join(dir, "observations.jsonl")
	rows := []RawObservation{{
		ID:          "obs_test",
		Source:      "world_scout_go:test",
		SourceURL:   "https://example.com",
		Title:       "New coding agent launch",
		Description: "A coding agent API launched.",
	}}
	if err := WriteObservations(output, rows, true); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(output)
	if err != nil {
		t.Fatal(err)
	}
	var row RawObservation
	if err := json.Unmarshal(raw, &row); err != nil {
		t.Fatal(err)
	}
	if row.ID != "obs_test" {
		t.Fatalf("id = %q", row.ID)
	}
}

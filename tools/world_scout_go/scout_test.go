package main

import "testing"

func TestObservationFromText(t *testing.T) {
	obs, ok := observationFromText(Source{Name: "test", URL: "https://example.com"}, "<p>Agentic AI benchmark release</p>")
	if !ok {
		t.Fatal("expected observation")
	}
	if obs.ID == "" || obs.URL == "" {
		t.Fatalf("incomplete observation: %+v", obs)
	}
	if len(obs.Keywords) == 0 {
		t.Fatalf("expected keywords: %+v", obs)
	}
}

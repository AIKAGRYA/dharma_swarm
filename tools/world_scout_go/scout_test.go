package main

import "testing"

func TestParseHNEmitsItems(t *testing.T) {
	rows := parseHN(Source{Name: "hn", Kind: "hn_algolia"}, []byte(`{"hits":[{"objectID":"1","title":"Agent runtime","url":"https://example.com"}]}`))
	if len(rows) != 1 || rows[0].URL == "" || rows[0].SourceType != "hn_algolia" {
		t.Fatalf("unexpected rows: %+v", rows)
	}
}

func TestParseGitHubReposEmitsItems(t *testing.T) {
	rows := parseGitHubRepos(Source{Name: "gh", Kind: "github_repos"}, []byte(`{"items":[{"id":7,"full_name":"org/agent","description":"agent runtime","html_url":"https://github.com/org/agent","stargazers_count":12}]}`))
	if len(rows) != 1 || rows[0].Title != "org/agent" {
		t.Fatalf("unexpected rows: %+v", rows)
	}
}

func TestObservationFromText(t *testing.T) {
	obs, ok := observationFromText(Source{Name: "test", URL: "https://example.com", Kind: "html"}, "<p>Agentic AI benchmark release</p>")
	if !ok || obs.ID == "" || len(obs.Keywords) == 0 {
		t.Fatalf("unexpected observation: %+v", obs)
	}
}

package main

import (
	"encoding/json"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type Source struct {
	Name       string `json:"name"`
	URL        string `json:"url"`
	Kind       string `json:"kind"`
	CascadeFor string `json:"cascade_for,omitempty"`
}

func DefaultSources() []Source {
	return []Source{
		{Name: "openai_news", URL: "https://openai.com/news/", Kind: "html"},
		{Name: "anthropic_news", URL: "https://www.anthropic.com/news", Kind: "html"},
		{Name: "hacker_news_ai", URL: "https://hn.algolia.com/api/v1/search_by_date?query=agentic%20AI", Kind: "hn_algolia"},
		{Name: "reddit_localllama", URL: "https://www.reddit.com/r/LocalLLaMA/search.json?q=agents&sort=new&restrict_sr=1", Kind: "reddit"},
		{Name: "github_trending_agents", URL: "https://api.github.com/search/repositories?q=agentic+ai&sort=updated&order=desc", Kind: "github_repos"},
		{Name: "github_advisories_ai", URL: "https://api.github.com/advisories?query=ai", Kind: "github_advisories"},
		{Name: "arxiv_agents", URL: "https://export.arxiv.org/api/query?search_query=all:agentic%20AI&sortBy=submittedDate&sortOrder=descending&max_results=10", Kind: "arxiv"},
		{Name: "arxiv_long_context", URL: "https://export.arxiv.org/api/query?search_query=all:long%20context%20agents&sortBy=submittedDate&sortOrder=descending&max_results=10", Kind: "arxiv"},
		// Agentic design-patterns / agentic-engineering literature — added 2026-07-01
		// so the hourly world_scout radar tracks this class of knowledge on a
		// regular basis. Companion to docs/architecture/AGENTIC_PATTERNS_ATLAS.md;
		// keeps that atlas refreshed as the field moves instead of frozen at one read.
		{Name: "arxiv_agentic_design_patterns", URL: "https://export.arxiv.org/api/query?search_query=all:%22agentic%20design%20patterns%22&sortBy=submittedDate&sortOrder=descending&max_results=10", Kind: "arxiv"},
		{Name: "arxiv_llm_agent_architecture", URL: "https://export.arxiv.org/api/query?search_query=all:LLM%20agent%20architecture&sortBy=submittedDate&sortOrder=descending&max_results=10", Kind: "arxiv"},
		{Name: "hacker_news_agentic_engineering", URL: "https://hn.algolia.com/api/v1/search_by_date?query=agentic%20engineering", Kind: "hn_algolia"},
		{Name: "github_agentic_design_patterns", URL: "https://api.github.com/search/repositories?q=agentic+design+patterns&sort=updated&order=desc", Kind: "github_repos"},
	}
}

func LoadSources(stateDir string) []Source {
	path := filepath.Join(stateDir, "meta", "world_radar", "sources.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return DefaultSources()
	}
	var sources []Source
	if err := json.Unmarshal(data, &sources); err != nil {
		return DefaultSources()
	}
	out := []Source{}
	for _, source := range sources {
		if source.Name == "" || source.URL == "" {
			continue
		}
		if source.Kind == "" {
			source.Kind = inferKind(source.URL)
		}
		out = append(out, source)
	}
	if len(out) == 0 {
		return DefaultSources()
	}
	return out
}

func SourcesForQueries(queries []string, cascadeFor string) []Source {
	sources := []Source{}
	for idx, query := range queries {
		escaped := url.QueryEscape(query)
		prefix := "cascade"
		if cascadeFor != "" {
			prefix = "cascade_" + cascadeFor
		}
		suffix := "_" + strconv.Itoa(idx)
		sources = append(sources,
			Source{Name: prefix + "_hn" + suffix, URL: "https://hn.algolia.com/api/v1/search_by_date?query=" + escaped, Kind: "hn_algolia", CascadeFor: cascadeFor},
			Source{Name: prefix + "_github" + suffix, URL: "https://api.github.com/search/repositories?q=" + escaped + "&sort=updated&order=desc", Kind: "github_repos", CascadeFor: cascadeFor},
			Source{Name: prefix + "_arxiv" + suffix, URL: "https://export.arxiv.org/api/query?search_query=all:" + escaped + "&sortBy=submittedDate&sortOrder=descending&max_results=5", Kind: "arxiv", CascadeFor: cascadeFor},
			Source{Name: prefix + "_reddit" + suffix, URL: "https://www.reddit.com/search.json?q=" + escaped + "&sort=new", Kind: "reddit", CascadeFor: cascadeFor},
		)
	}
	return sources
}

func inferKind(rawURL string) string {
	switch {
	case strings.Contains(rawURL, "hn.algolia.com"):
		return "hn_algolia"
	case strings.Contains(rawURL, "api.github.com/search/repositories"):
		return "github_repos"
	case strings.Contains(rawURL, "api.github.com/advisories"):
		return "github_advisories"
	case strings.Contains(rawURL, "export.arxiv.org"):
		return "arxiv"
	case strings.Contains(rawURL, "reddit.com"):
		return "reddit"
	default:
		return "html"
	}
}

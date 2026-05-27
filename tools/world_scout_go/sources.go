package main

import (
	"encoding/json"
	"fmt"
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

func URLsFromFiles(paths []string) ([]string, error) {
	urls := []string{}
	errors := []string{}
	for _, path := range paths {
		data, err := os.ReadFile(strings.TrimSpace(path))
		if err != nil {
			errors = append(errors, err.Error())
			continue
		}
		for _, line := range strings.Split(string(data), "\n") {
			trimmed := strings.TrimSpace(line)
			if trimmed == "" || strings.HasPrefix(trimmed, "#") {
				continue
			}
			urls = append(urls, trimmed)
		}
	}
	if len(errors) > 0 {
		return urls, fmt.Errorf("url file errors: %s", strings.Join(errors, "; "))
	}
	return urls, nil
}

func SourcesForURLs(rawURLs []string, cascadeFor string) []Source {
	sources := []Source{}
	seen := map[string]bool{}
	for idx, rawURL := range rawURLs {
		trimmed := strings.TrimSpace(rawURL)
		canonical := canonicalURL(trimmed)
		if canonical == "" || seen[canonical] {
			continue
		}
		seen[canonical] = true
		nameURL := strings.TrimPrefix(strings.TrimPrefix(canonical, "https://"), "http://")
		nameURL = strings.NewReplacer("/", "_", ":", "_", "?", "_", "&", "_", "=", "_").Replace(nameURL)
		nameURL = strings.Trim(nameURL, "_")
		if len(nameURL) > 72 {
			nameURL = nameURL[:72]
		}
		if nameURL == "" {
			nameURL = "url"
		}
		sources = append(sources, Source{
			Name:       "direct_" + strconv.Itoa(idx) + "_" + nameURL,
			URL:        canonical,
			Kind:       inferKind(canonical),
			CascadeFor: cascadeFor,
		})
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
	case strings.HasSuffix(rawURL, "/llms.txt") || strings.HasSuffix(rawURL, "/llms-full.txt"):
		return "llms_txt"
	case strings.Contains(rawURL, "reddit.com"):
		return "reddit"
	default:
		return "html"
	}
}

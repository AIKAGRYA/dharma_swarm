package main

type Source struct {
	ID        string   `json:"id"`
	Family    string   `json:"family"`
	Title     string   `json:"title"`
	URL       string   `json:"url"`
	Kind      string   `json:"kind"`
	Publisher string   `json:"publisher,omitempty"`
	Keywords  []string `json:"keywords,omitempty"`
}

func DefaultSources() []Source {
	return []Source{
		{ID: "openai_news", Family: "ai_frontier", Title: "OpenAI news", URL: "https://openai.com/news/rss.xml", Kind: "rss", Publisher: "OpenAI", Keywords: []string{"agent", "model", "inference", "safety"}},
		{ID: "anthropic_news", Family: "ai_frontier", Title: "Anthropic news", URL: "https://www.anthropic.com/news/rss.xml", Kind: "rss", Publisher: "Anthropic", Keywords: []string{"claude", "agent", "safety"}},
		{ID: "hn_agent_search", Family: "practitioner_signal", Title: "HN agent discussion", URL: "https://hn.algolia.com/api/v1/search_by_date?query=ai%20agent&tags=story", Kind: "hackernews", Publisher: "Hacker News", Keywords: []string{"agent", "startup", "developer"}},
		{ID: "reddit_localllama", Family: "practitioner_signal", Title: "LocalLLaMA discussion", URL: "https://www.reddit.com/r/LocalLLaMA/new.json?limit=25", Kind: "reddit", Publisher: "Reddit", Keywords: []string{"open model", "inference", "agents"}},
		{ID: "github_agent_repos", Family: "agent_infra", Title: "GitHub agent repositories", URL: "https://api.github.com/search/repositories?q=ai+agent+created:%3E2025-01-01&sort=updated&order=desc", Kind: "github_search", Publisher: "GitHub", Keywords: []string{"agent infra", "workflow", "developer tool"}},
		{ID: "github_advisories_ai", Family: "security_regulatory", Title: "GitHub advisories AI search", URL: "https://api.github.com/search/advisories?query=AI", Kind: "github_advisory", Publisher: "GitHub", Keywords: []string{"security", "supply chain", "governance"}},
		{ID: "arxiv_agents", Family: "ai_frontier", Title: "arXiv agent search", URL: "https://export.arxiv.org/api/query?search_query=all:AI%20agent&sortBy=submittedDate&sortOrder=descending&max_results=25", Kind: "atom", Publisher: "arXiv", Keywords: []string{"paper", "benchmark", "agent"}},
		{ID: "arxiv_long_context", Family: "ai_frontier", Title: "arXiv long context search", URL: "https://export.arxiv.org/api/query?search_query=all:long%20context%20transformer&sortBy=submittedDate&sortOrder=descending&max_results=25", Kind: "atom", Publisher: "arXiv", Keywords: []string{"long context", "inference", "benchmark"}},
	}
}

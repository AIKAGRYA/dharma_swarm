package main

type Source struct {
	Name string
	URL  string
}

func DefaultSources() []Source {
	return []Source{
		{Name: "openai_news", URL: "https://openai.com/news/"},
		{Name: "anthropic_news", URL: "https://www.anthropic.com/news"},
		{Name: "hacker_news_ai", URL: "https://hn.algolia.com/api/v1/search_by_date?query=agentic%20AI"},
		{Name: "reddit_localllama", URL: "https://www.reddit.com/r/LocalLLaMA/search.json?q=agents&sort=new&restrict_sr=1"},
		{Name: "github_trending_agents", URL: "https://api.github.com/search/repositories?q=agentic+ai&sort=updated&order=desc"},
		{Name: "github_advisories_ai", URL: "https://api.github.com/advisories?query=ai"},
		{Name: "arxiv_agents", URL: "https://export.arxiv.org/api/query?search_query=all:agentic%20AI&sortBy=submittedDate&sortOrder=descending&max_results=10"},
		{Name: "arxiv_long_context", URL: "https://export.arxiv.org/api/query?search_query=all:long%20context%20agents&sortBy=submittedDate&sortOrder=descending&max_results=10"},
	}
}

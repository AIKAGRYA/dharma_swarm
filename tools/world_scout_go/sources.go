package main

type SourceDefinition struct {
	ID        string
	Family    string
	Title     string
	URL       string
	Kind      string
	Publisher string
	Keywords  []string
}

func DefaultSources() []SourceDefinition {
	return []SourceDefinition{
		{ID: "arxiv_ai_agents", Family: "ai_frontier", Title: "arXiv AI agent and long-context papers", URL: "https://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+AND+all:agent&sortBy=submittedDate&sortOrder=descending&max_results=20", Kind: "atom_feed", Publisher: "arXiv", Keywords: []string{"paper", "research", "agents", "long context"}},
		{ID: "hugging_face_papers", Family: "ai_frontier", Title: "Hugging Face Papers", URL: "https://huggingface.co/papers/rss", Kind: "rss_feed", Publisher: "Hugging Face", Keywords: []string{"model release", "paper", "open source"}},
		{ID: "openai_news", Family: "ai_frontier", Title: "OpenAI News", URL: "https://openai.com/news/rss.xml", Kind: "rss_feed", Publisher: "OpenAI", Keywords: []string{"model release", "api", "agents"}},
		{ID: "anthropic_news", Family: "ai_frontier", Title: "Anthropic News", URL: "https://www.anthropic.com/news/rss.xml", Kind: "rss_feed", Publisher: "Anthropic", Keywords: []string{"model release", "agents", "research"}},
		{ID: "hacker_news_ai", Family: "practitioner", Title: "Hacker News AI Search", URL: "https://hn.algolia.com/api/v1/search_by_date?query=ai%20agent&tags=story&hitsPerPage=25", Kind: "json_hn_algolia", Publisher: "HN Algolia", Keywords: []string{"social signal", "practitioner", "agents"}},
		{ID: "reddit_localllama", Family: "practitioner", Title: "Reddit LocalLLaMA Top Daily", URL: "https://www.reddit.com/r/LocalLLaMA/top.json?t=day&limit=25", Kind: "json_reddit_listing", Publisher: "Reddit", Keywords: []string{"social signal", "local models", "open source"}},
		{ID: "simon_willison", Family: "practitioner", Title: "Simon Willison Weblog", URL: "https://simonwillison.net/atom/everything/", Kind: "atom_feed", Publisher: "Simon Willison", Keywords: []string{"practitioner", "llm", "engineering"}},
		{ID: "latent_space", Family: "practitioner", Title: "Latent Space", URL: "https://www.latent.space/feed", Kind: "rss_feed", Publisher: "Latent Space", Keywords: []string{"practitioner", "ai", "podcast"}},
		{ID: "mcp_docs", Family: "agent_infra", Title: "Model Context Protocol Documentation", URL: "https://modelcontextprotocol.io/introduction", Kind: "html_doc", Publisher: "Model Context Protocol", Keywords: []string{"mcp", "agents", "tools"}},
		{ID: "a2a_protocol_repo", Family: "agent_infra", Title: "Agent2Agent Protocol Repository", URL: "https://api.github.com/repos/a2aproject/A2A", Kind: "json_github_repo", Publisher: "A2A Project", Keywords: []string{"a2a", "agents", "protocol"}},
		{ID: "langgraph_durable_execution", Family: "agent_infra", Title: "LangGraph Durable Execution Documentation", URL: "https://docs.langchain.com/oss/python/langgraph/durable-execution", Kind: "html_doc", Publisher: "LangChain", Keywords: []string{"agents", "durable execution", "tools"}},
		{ID: "openai_agents_docs", Family: "agent_infra", Title: "OpenAI Agents SDK Documentation", URL: "https://openai.github.io/openai-agents-python/", Kind: "html_doc", Publisher: "OpenAI", Keywords: []string{"agents", "sdk", "tools"}},
		{ID: "product_hunt_feed", Family: "product_company", Title: "Product Hunt Launch Feed", URL: "https://www.producthunt.com/feed", Kind: "rss_feed", Publisher: "Product Hunt", Keywords: []string{"product launch", "startup", "company"}},
		{ID: "techcrunch_startups", Family: "product_company", Title: "TechCrunch Startups", URL: "https://techcrunch.com/category/startups/feed/", Kind: "rss_feed", Publisher: "TechCrunch", Keywords: []string{"funding", "startup", "launch"}},
		{ID: "ycombinator_ai_companies", Family: "product_company", Title: "Y Combinator AI Companies", URL: "https://www.ycombinator.com/companies?query=AI", Kind: "html_doc", Publisher: "Y Combinator", Keywords: []string{"startup", "company", "funding"}},
		{ID: "github_ai_repo_search", Family: "github", Title: "GitHub AI Repository Search", URL: "https://api.github.com/search/repositories?q=topic:artificial-intelligence+agent&sort=updated&order=desc&per_page=25", Kind: "json_github_search", Publisher: "GitHub", Keywords: []string{"github", "open source", "agents"}},
		{ID: "github_llm_releases", Family: "github", Title: "GitHub LLM Repository Search", URL: "https://api.github.com/search/repositories?q=llm+agent+in:name,description&sort=updated&order=desc&per_page=25", Kind: "json_github_search", Publisher: "GitHub", Keywords: []string{"github", "llm", "agent"}},
		{ID: "cisa_kev", Family: "security_regulatory", Title: "CISA Known Exploited Vulnerabilities Catalog", URL: "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", Kind: "json_generic", Publisher: "CISA", Keywords: []string{"security", "risk", "advisory"}},
		{ID: "github_global_advisories", Family: "security_regulatory", Title: "GitHub Global Security Advisories", URL: "https://api.github.com/advisories?per_page=100&sort=updated&direction=desc", Kind: "json_github_advisories", Publisher: "GitHub Advisory Database", Keywords: []string{"security", "supply chain", "advisory"}},
	}
}

package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"html"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
)

const scoutMaxAttempts = 3

// Sequential fetching over the full source list (default sources + up to ~40
// beat-derived query sources in --beats mode) could exceed the cron scout
// timeout before any observation is persisted, turning a slow/rate-limited
// endpoint into an empty failed run instead of a partial success (Codex
// review finding, main.go:52). Bounded concurrency keeps total wall time
// close to one round-trip regardless of source count.
const scoutFetchConcurrency = 8

var scoutSleep = time.Sleep

type Observation struct {
	ID          string   `json:"id"`
	Source      string   `json:"source"`
	SourceType  string   `json:"source_type"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	URL         string   `json:"url"`
	ObservedAt  string   `json:"observed_at"`
	Keywords    []string `json:"keywords"`
	CascadeFor  string   `json:"cascade_for,omitempty"`
}

func FetchSources(sources []Source) ([]Observation, ScoutResult, error) {
	return FetchSourcesWithContext(context.Background(), sources)
}

func FetchSourcesWithContext(ctx context.Context, sources []Source) ([]Observation, ScoutResult, error) {
	client := &http.Client{Timeout: 12 * time.Second}
	return fetchSourcesWithClient(ctx, sources, client)
}

type sourceFetchOutcome struct {
	name         string
	observations []Observation
	retries      int
	err          error
}

func fetchSourcesWithClient(ctx context.Context, sources []Source, client *http.Client) ([]Observation, ScoutResult, error) {
	result := ScoutResult{FetchEnabled: true, SourceCount: len(sources)}

	// Fetch concurrently (bounded by scoutFetchConcurrency) but collect into
	// an index-ordered slice so downstream ordering/determinism (and existing
	// tests) match the old sequential behavior exactly.
	outcomes := make([]sourceFetchOutcome, len(sources))
	sem := make(chan struct{}, scoutFetchConcurrency)
	var wg sync.WaitGroup
	for i, source := range sources {
		wg.Add(1)
		sem <- struct{}{}
		go func(i int, source Source) {
			defer wg.Done()
			defer func() { <-sem }()
			body, retries, err := fetchSourceBytes(ctx, client, source)
			outcome := sourceFetchOutcome{name: source.Name, retries: retries, err: err}
			if err == nil {
				outcome.observations = observationsFromBytes(source, body)
			}
			outcomes[i] = outcome
		}(i, source)
	}
	wg.Wait()

	observations := []Observation{}
	var errors []string
	for _, outcome := range outcomes {
		result.RetryCount += outcome.retries
		if outcome.err != nil {
			result.FailedSources++
			errors = append(errors, fmt.Sprintf("%s: %v", outcome.name, outcome.err))
			continue
		}
		result.SuccessfulSources++
		observations = append(observations, outcome.observations...)
	}
	result.Errors = errors
	if len(errors) > 0 && len(observations) == 0 {
		return observations, result, fmt.Errorf("%s", strings.Join(errors, "; "))
	}
	return observations, result, nil
}

func fetchSourceBytes(ctx context.Context, client *http.Client, source Source) ([]byte, int, error) {
	var lastErr error
	retries := 0
	for attempt := 1; attempt <= scoutMaxAttempts; attempt++ {
		if err := ctx.Err(); err != nil {
			return nil, retries, err
		}
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, source.URL, nil)
		if err != nil {
			return nil, retries, err
		}
		req.Header.Set("User-Agent", "dharma-world-scout/1.0")
		resp, err := client.Do(req)
		if err != nil {
			lastErr = err
			if attempt < scoutMaxAttempts {
				retries++
				waitForRetry(ctx, scoutRetryDelay("", attempt))
				continue
			}
			return nil, retries, err
		}
		body, readErr := io.ReadAll(io.LimitReader(resp.Body, 300_000))
		resp.Body.Close()
		if readErr != nil {
			lastErr = readErr
			if attempt < scoutMaxAttempts {
				retries++
				waitForRetry(ctx, scoutRetryDelay("", attempt))
				continue
			}
			return nil, retries, readErr
		}
		if resp.StatusCode >= 400 {
			lastErr = fmt.Errorf("status %d", resp.StatusCode)
			if isRetryableStatus(resp.StatusCode) && attempt < scoutMaxAttempts {
				retries++
				waitForRetry(ctx, scoutRetryDelay(resp.Header.Get("Retry-After"), attempt))
				continue
			}
			return nil, retries, lastErr
		}
		return body, retries, nil
	}
	return nil, retries, lastErr
}

func waitForRetry(ctx context.Context, delay time.Duration) {
	if delay <= 0 {
		return
	}
	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
	case <-timer.C:
	}
}

func scoutRetryDelay(header string, attempt int) time.Duration {
	if seconds, err := time.ParseDuration(strings.TrimSpace(header) + "s"); err == nil && seconds >= 0 {
		return seconds
	}
	if when, err := http.ParseTime(strings.TrimSpace(header)); err == nil {
		if delay := time.Until(when); delay > 0 {
			return delay
		}
	}
	return time.Duration(attempt*100) * time.Millisecond
}

func isRetryableStatus(status int) bool {
	switch status {
	case http.StatusTooManyRequests, http.StatusInternalServerError, http.StatusBadGateway, http.StatusServiceUnavailable, http.StatusGatewayTimeout:
		return true
	default:
		return false
	}
}

func observationsFromBytes(source Source, body []byte) []Observation {
	switch source.Kind {
	case "hn_algolia":
		return parseHN(source, body)
	case "github_repos":
		return parseGitHubRepos(source, body)
	case "github_advisories":
		return parseGitHubAdvisories(source, body)
	case "arxiv":
		return parseArxiv(source, body)
	case "reddit":
		return parseReddit(source, body)
	case "youtube_atom":
		return parseYouTubeAtom(source, body)
	case "rss":
		return parseRSS(source, body)
	default:
		if obs, ok := observationFromText(source, string(body)); ok {
			return []Observation{obs}
		}
		return nil
	}
}

func parseHN(source Source, body []byte) []Observation {
	var payload struct {
		Hits []struct {
			ObjectID  string `json:"objectID"`
			Title     string `json:"title"`
			StoryText string `json:"story_text"`
			URL       string `json:"url"`
			Author    string `json:"author"`
		} `json:"hits"`
	}
	if json.Unmarshal(body, &payload) != nil {
		return fallbackObservation(source, body)
	}
	observations := []Observation{}
	for _, hit := range payload.Hits {
		url := hit.URL
		if url == "" && hit.ObjectID != "" {
			url = "https://news.ycombinator.com/item?id=" + hit.ObjectID
		}
		description := hit.StoryText
		if description == "" && hit.Author != "" {
			description = "Hacker News item by " + hit.Author
		}
		observations = append(observations, makeObservation(source, hit.ObjectID, firstNonEmpty(hit.Title, "HN signal"), description, url))
	}
	return observations
}

func parseGitHubRepos(source Source, body []byte) []Observation {
	var payload struct {
		Items []struct {
			ID          int64  `json:"id"`
			FullName    string `json:"full_name"`
			Description string `json:"description"`
			HTMLURL     string `json:"html_url"`
			Language    string `json:"language"`
			Stars       int    `json:"stargazers_count"`
		} `json:"items"`
	}
	if json.Unmarshal(body, &payload) != nil {
		return fallbackObservation(source, body)
	}
	observations := []Observation{}
	for _, repo := range payload.Items {
		description := strings.TrimSpace(fmt.Sprintf("%s language=%s stars=%d", repo.Description, repo.Language, repo.Stars))
		observations = append(observations, makeObservation(source, fmt.Sprint(repo.ID), repo.FullName, description, repo.HTMLURL))
	}
	return observations
}

func parseGitHubAdvisories(source Source, body []byte) []Observation {
	var items []struct {
		GHSAID      string `json:"ghsa_id"`
		Summary     string `json:"summary"`
		Description string `json:"description"`
		HTMLURL     string `json:"html_url"`
	}
	if json.Unmarshal(body, &items) != nil {
		return fallbackObservation(source, body)
	}
	observations := []Observation{}
	for _, item := range items {
		observations = append(observations, makeObservation(source, item.GHSAID, item.Summary, item.Description, item.HTMLURL))
	}
	return observations
}

func parseArxiv(source Source, body []byte) []Observation {
	var feed struct {
		Entries []struct {
			ID      string `xml:"id"`
			Title   string `xml:"title"`
			Summary string `xml:"summary"`
		} `xml:"entry"`
	}
	if xml.Unmarshal(body, &feed) != nil {
		return fallbackObservation(source, body)
	}
	observations := []Observation{}
	for _, entry := range feed.Entries {
		observations = append(observations, makeObservation(source, entry.ID, entry.Title, entry.Summary, entry.ID))
	}
	return observations
}

func parseReddit(source Source, body []byte) []Observation {
	var payload struct {
		Data struct {
			Children []struct {
				Data struct {
					ID        string `json:"id"`
					Title     string `json:"title"`
					Selftext  string `json:"selftext"`
					Permalink string `json:"permalink"`
					URL       string `json:"url"`
					Subreddit string `json:"subreddit"`
				} `json:"data"`
			} `json:"children"`
		} `json:"data"`
	}
	if json.Unmarshal(body, &payload) != nil {
		return fallbackObservation(source, body)
	}
	observations := []Observation{}
	for _, child := range payload.Data.Children {
		data := child.Data
		url := data.URL
		if data.Permalink != "" {
			url = "https://www.reddit.com" + data.Permalink
		}
		description := strings.TrimSpace(data.Selftext + " subreddit=" + data.Subreddit)
		observations = append(observations, makeObservation(source, data.ID, data.Title, description, url))
	}
	return observations
}

func parseYouTubeAtom(source Source, body []byte) []Observation {
	var feed struct {
		Entries []struct {
			ID      string `xml:"id"`
			VideoID string `xml:"videoId"`
			Title   string `xml:"title"`
			Link    struct {
				Href string `xml:"href,attr"`
			} `xml:"link"`
			Published string `xml:"published"`
			Group     struct {
				Description string `xml:"description"`
			} `xml:"group"`
		} `xml:"entry"`
	}
	if xml.Unmarshal(body, &feed) != nil {
		return fallbackObservation(source, body)
	}
	observations := []Observation{}
	for _, entry := range feed.Entries {
		itemURL := strings.TrimSpace(entry.Link.Href)
		if itemURL == "" && entry.VideoID != "" {
			itemURL = "https://www.youtube.com/watch?v=" + entry.VideoID
		}
		itemID := firstNonEmpty(entry.VideoID, entry.ID)
		observations = append(observations, makeObservation(source, itemID, entry.Title, entry.Group.Description, itemURL))
	}
	if len(observations) == 0 {
		return fallbackObservation(source, body)
	}
	return observations
}

func parseRSS(source Source, body []byte) []Observation {
	var feed struct {
		Channel struct {
			Items []struct {
				Title       string `xml:"title"`
				Link        string `xml:"link"`
				Description string `xml:"description"`
				GUID        string `xml:"guid"`
			} `xml:"item"`
		} `xml:"channel"`
	}
	if xml.Unmarshal(body, &feed) != nil {
		return fallbackObservation(source, body)
	}
	observations := []Observation{}
	for _, item := range feed.Channel.Items {
		observations = append(observations, makeObservation(source, firstNonEmpty(item.GUID, item.Link, item.Title), item.Title, item.Description, item.Link))
	}
	if len(observations) == 0 {
		return fallbackObservation(source, body)
	}
	return observations
}

func fallbackObservation(source Source, body []byte) []Observation {
	if obs, ok := observationFromText(source, string(body)); ok {
		return []Observation{obs}
	}
	return nil
}

func observationFromText(source Source, text string) (Observation, bool) {
	compact := strings.Join(strings.Fields(stripTags(text)), " ")
	if compact == "" {
		return Observation{}, false
	}
	if len(compact) > 800 {
		compact = compact[:800]
	}
	return makeObservation(source, stableID(source.URL+compact), source.Name+" public signal", compact, source.URL), true
}

func makeObservation(source Source, itemID, title, description, itemURL string) Observation {
	title = strings.Join(strings.Fields(html.UnescapeString(stripTags(title))), " ")
	description = strings.Join(strings.Fields(html.UnescapeString(stripTags(description))), " ")
	if title == "" {
		title = source.Name
	}
	if len(description) > 800 {
		description = description[:800]
	}
	if itemURL == "" {
		itemURL = source.URL
	}
	return Observation{
		ID:          stableID(source.Name + itemID + itemURL + title),
		Source:      source.Name,
		SourceType:  source.Kind,
		Title:       title,
		Description: description,
		URL:         itemURL,
		ObservedAt:  time.Now().UTC().Format(time.RFC3339),
		Keywords:    extractKeywords(title + " " + description),
		CascadeFor:  source.CascadeFor,
	}
}

func stripTags(text string) string {
	out := strings.Builder{}
	inTag := false
	for _, r := range text {
		switch r {
		case '<':
			inTag = true
		case '>':
			inTag = false
		default:
			if !inTag {
				out.WriteRune(r)
			}
		}
	}
	return out.String()
}

func extractKeywords(text string) []string {
	lower := strings.ToLower(text)
	candidates := []string{"agent", "agentic", "benchmark", "github", "governance", "startup", "research", "model", "tool", "runtime", "coding"}
	keywords := []string{}
	for _, candidate := range candidates {
		if strings.Contains(lower, candidate) {
			keywords = append(keywords, candidate)
		}
	}
	return keywords
}

func stableID(seed string) string {
	sum := sha256.Sum256([]byte(seed))
	return hex.EncodeToString(sum[:])[:16]
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

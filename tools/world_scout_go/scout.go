package main

import (
	"bufio"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"html"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

const (
	DefaultTimeoutMS         = 750
	DefaultMaxBodyBytes      = 1 << 20
	DefaultMaxItemsPerSource = 10
	ScoutVersion             = "world_scout_go.v0"
)

type RawObservation struct {
	ID          string   `json:"id,omitempty"`
	Source      string   `json:"source,omitempty"`
	SourceID    string   `json:"source_id,omitempty"`
	SourceURL   string   `json:"source_url,omitempty"`
	URL         string   `json:"url,omitempty"`
	Publisher   string   `json:"publisher,omitempty"`
	Title       string   `json:"title"`
	Description string   `json:"description,omitempty"`
	Body        string   `json:"body,omitempty"`
	PublishedAt string   `json:"published_at,omitempty"`
	Keywords    []string `json:"keywords,omitempty"`
	Family      string   `json:"family,omitempty"`
	Kind        string   `json:"kind,omitempty"`
	ObservedAt  string   `json:"observed_at"`
	Scout       string   `json:"scout"`
}

func LoadSources(path string) ([]Source, error) {
	if path == "" {
		return DefaultSources(), nil
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var sources []Source
	if err := json.Unmarshal(raw, &sources); err != nil {
		return nil, err
	}
	return sources, nil
}

func CollectObservations(opts Options, sources []Source) ([]RawObservation, error) {
	result, err := CollectWorld(opts, sources)
	if err != nil {
		return nil, err
	}
	return result.Observations, nil
}

func CollectWorld(opts Options, sources []Source) (ScoutResult, error) {
	observedAt := time.Now().UTC()
	result := ScoutResult{
		ObservedAt:   observedAt.Format(time.RFC3339),
		FetchEnabled: opts.Fetch,
		SourceCount:  len(sources),
		Sources:      []SourceHealth{},
	}
	for _, source := range sources {
		health := newHealth(source, opts.Fetch, observedAt)
		if !opts.Fetch {
			result.Sources = append(result.Sources, health)
			continue
		}
		start := time.Now()
		observations, err := collectSource(opts, source, observedAt)
		health.LatencyMS = time.Since(start).Milliseconds()
		if err != nil {
			health.Error = err.Error()
			result.Sources = append(result.Sources, health)
			continue
		}
		health.Reachable = true
		health.ItemCount = len(observations)
		result.ReachableCount++
		result.ItemCount += len(observations)
		result.Observations = append(result.Observations, observations...)
		result.Sources = append(result.Sources, health)
	}
	return result, nil
}

func WriteObservations(path string, observations []RawObservation) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil && filepath.Dir(path) != "." {
		return err
	}
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	writer := bufio.NewWriter(file)
	for _, observation := range observations {
		raw, err := json.Marshal(observation)
		if err != nil {
			return err
		}
		if _, err := writer.Write(append(raw, '\n')); err != nil {
			return err
		}
	}
	return writer.Flush()
}

func collectSource(opts Options, source Source, observedAt time.Time) ([]RawObservation, error) {
	body, err := fetchBody(opts, source.URL)
	if err != nil {
		return nil, err
	}
	switch source.Kind {
	case "rss", "atom":
		return feedObservations(source, body, observedAt), nil
	case "hackernews":
		return hackerNewsObservations(source, body, observedAt), nil
	case "reddit":
		return redditObservations(source, body, observedAt), nil
	case "github_search":
		return githubRepoObservations(source, body, observedAt), nil
	case "github_advisory":
		return githubAdvisoryObservations(source, body, observedAt), nil
	default:
		return htmlObservation(source, body, observedAt), nil
	}
}

func fetchBody(opts Options, url string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(opts.TimeoutMS)*time.Millisecond)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "dharma-world-scout/0.1")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("status %d", resp.StatusCode)
	}
	limit := opts.MaxBodyBytes
	if limit <= 0 {
		limit = DefaultMaxBodyBytes
	}
	return io.ReadAll(io.LimitReader(resp.Body, limit))
}

func feedObservations(source Source, body []byte, observedAt time.Time) []RawObservation {
	type item struct {
		Title       string `xml:"title"`
		Link        string `xml:"link"`
		Description string `xml:"description"`
		Summary     string `xml:"summary"`
		PubDate     string `xml:"pubDate"`
		Updated     string `xml:"updated"`
	}
	var payload struct {
		Channel struct {
			Items []item `xml:"item"`
		} `xml:"channel"`
		Entries []item `xml:"entry"`
	}
	if err := xml.Unmarshal(body, &payload); err != nil {
		return htmlObservation(source, body, observedAt)
	}
	items := payload.Channel.Items
	if len(items) == 0 {
		items = payload.Entries
	}
	out := []RawObservation{}
	for _, item := range items {
		title := cleanText(item.Title)
		if title == "" {
			continue
		}
		link := cleanText(item.Link)
		desc := cleanText(firstNonEmpty(item.Description, item.Summary))
		out = append(out, observation(source, link, title, desc, "", firstNonEmpty(item.PubDate, item.Updated), observedAt, nil))
	}
	return out
}

func hackerNewsObservations(source Source, body []byte, observedAt time.Time) []RawObservation {
	var payload struct {
		Hits []struct {
			Title       string `json:"title"`
			StoryTitle  string `json:"story_title"`
			URL         string `json:"url"`
			StoryURL    string `json:"story_url"`
			CreatedAt   string `json:"created_at"`
			ObjectID    string `json:"objectID"`
			Author      string `json:"author"`
			NumComments int    `json:"num_comments"`
		} `json:"hits"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return htmlObservation(source, body, observedAt)
	}
	out := []RawObservation{}
	for _, hit := range payload.Hits {
		title := cleanText(firstNonEmpty(hit.Title, hit.StoryTitle))
		if title == "" {
			continue
		}
		desc := strings.TrimSpace(hit.Author + " comments=" + strconv.Itoa(hit.NumComments))
		out = append(out, observation(source, firstNonEmpty(hit.URL, hit.StoryURL), title, desc, "", hit.CreatedAt, observedAt, nil))
	}
	return out
}

func redditObservations(source Source, body []byte, observedAt time.Time) []RawObservation {
	var payload struct {
		Data struct {
			Children []struct {
				Data struct {
					Title      string  `json:"title"`
					SelfText   string  `json:"selftext"`
					URL        string  `json:"url"`
					Permalink  string  `json:"permalink"`
					Subreddit  string  `json:"subreddit"`
					CreatedUTC float64 `json:"created_utc"`
				} `json:"data"`
			} `json:"children"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return htmlObservation(source, body, observedAt)
	}
	out := []RawObservation{}
	for _, child := range payload.Data.Children {
		item := child.Data
		title := cleanText(item.Title)
		if title == "" {
			continue
		}
		link := item.URL
		if link == "" && item.Permalink != "" {
			link = "https://www.reddit.com" + item.Permalink
		}
		published := ""
		if item.CreatedUTC > 0 {
			published = time.Unix(int64(item.CreatedUTC), 0).UTC().Format(time.RFC3339)
		}
		out = append(out, observation(source, link, title, item.SelfText, "", published, observedAt, []string{item.Subreddit}))
	}
	return out
}

func githubRepoObservations(source Source, body []byte, observedAt time.Time) []RawObservation {
	var payload struct {
		Items []struct {
			FullName    string   `json:"full_name"`
			HTMLURL     string   `json:"html_url"`
			Description string   `json:"description"`
			Topics      []string `json:"topics"`
			UpdatedAt   string   `json:"updated_at"`
			Stars       int      `json:"stargazers_count"`
		} `json:"items"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return htmlObservation(source, body, observedAt)
	}
	out := []RawObservation{}
	for _, repo := range payload.Items {
		title := cleanText(repo.FullName)
		if title == "" {
			continue
		}
		body := fmt.Sprintf("%s stars=%d", repo.Description, repo.Stars)
		out = append(out, observation(source, repo.HTMLURL, title, body, "", repo.UpdatedAt, observedAt, repo.Topics))
	}
	return out
}

func githubAdvisoryObservations(source Source, body []byte, observedAt time.Time) []RawObservation {
	var payload struct {
		Items []struct {
			GHSAID      string `json:"ghsa_id"`
			HTMLURL     string `json:"html_url"`
			Summary     string `json:"summary"`
			Description string `json:"description"`
			PublishedAt string `json:"published_at"`
		} `json:"items"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return htmlObservation(source, body, observedAt)
	}
	out := []RawObservation{}
	for _, item := range payload.Items {
		title := cleanText(firstNonEmpty(item.Summary, item.GHSAID))
		if title == "" {
			continue
		}
		out = append(out, observation(source, item.HTMLURL, title, item.Description, "", item.PublishedAt, observedAt, nil))
	}
	return out
}

func htmlObservation(source Source, body []byte, observedAt time.Time) []RawObservation {
	text := cleanText(string(body))
	title := source.Title
	if match := regexp.MustCompile(`(?is)<title[^>]*>(.*?)</title>`).FindStringSubmatch(string(body)); len(match) > 1 {
		title = cleanText(match[1])
	}
	if title == "" {
		return nil
	}
	return []RawObservation{observation(source, source.URL, title, text[:min(len(text), 600)], "", "", observedAt, nil)}
}

func observation(source Source, url, title, desc, body, published string, observedAt time.Time, extra []string) RawObservation {
	keywords := unique(append(append([]string{}, source.Keywords...), extra...))
	row := RawObservation{
		Source:      source.Title,
		SourceID:    source.ID,
		SourceURL:   source.URL,
		URL:         url,
		Publisher:   firstNonEmpty(source.Publisher, source.Title),
		Title:       cleanText(title),
		Description: cleanText(desc),
		Body:        cleanText(body),
		PublishedAt: published,
		Keywords:    keywords,
		Family:      source.Family,
		Kind:        source.Kind,
		ObservedAt:  observedAt.Format(time.RFC3339),
		Scout:       ScoutVersion,
	}
	row.ID = stableID(row.SourceID, row.URL, row.Title)
	return row
}

func cleanText(text string) string {
	text = html.UnescapeString(text)
	text = regexp.MustCompile(`(?s)<[^>]+>`).ReplaceAllString(text, " ")
	text = strings.Join(strings.Fields(text), " ")
	return strings.TrimSpace(text)
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func stableID(parts ...string) string {
	hash := sha256.New()
	for _, part := range parts {
		hash.Write([]byte(part))
		hash.Write([]byte{0})
	}
	return hex.EncodeToString(hash.Sum(nil))[:16]
}

func unique(values []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" || seen[value] {
			continue
		}
		seen[value] = true
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

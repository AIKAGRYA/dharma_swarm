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
}

type rssDoc struct {
	Channel struct {
		Items []rssItem `xml:"item"`
	} `xml:"channel"`
}

type rssItem struct {
	Title       string `xml:"title"`
	Link        string `xml:"link"`
	Description string `xml:"description"`
	PubDate     string `xml:"pubDate"`
}

type atomFeed struct {
	Entries []atomEntry `xml:"entry"`
}

type atomEntry struct {
	Title   string     `xml:"title"`
	ID      string     `xml:"id"`
	Links   []atomLink `xml:"link"`
	Summary string     `xml:"summary"`
	Content string     `xml:"content"`
	Updated string     `xml:"updated"`
}

type atomLink struct {
	Href string `xml:"href,attr"`
	Rel  string `xml:"rel,attr"`
}

func CollectObservations(opts Options, sources []SourceDefinition) ([]RawObservation, error) {
	result, err := CollectWorld(opts, sources)
	return result.Observations, err
}

func collectSource(ctx context.Context, client *http.Client, source SourceDefinition, opts Options) ([]RawObservation, error) {
	if !opts.Fetch {
		return []RawObservation{catalogObservation(source, opts.ObservedAt, "")}, nil
	}
	body, err := fetchBody(ctx, client, source.URL, opts.MaxBodyBytes)
	if err != nil {
		return nil, err
	}
	rows := observationsFromBody(source, body, opts)
	if len(rows) > opts.MaxItems {
		rows = rows[:opts.MaxItems]
	}
	return rows, nil
}

func fetchBody(ctx context.Context, client *http.Client, url string, maxBytes int64) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "dharma-world-scout/0.1")
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("status_%d", resp.StatusCode)
	}
	return io.ReadAll(io.LimitReader(resp.Body, maxBytes))
}

func observationsFromBody(source SourceDefinition, body []byte, opts Options) []RawObservation {
	switch source.Kind {
	case "rss_feed":
		return rssObservations(source, body, opts.ObservedAt)
	case "atom_feed":
		return atomObservations(source, body, opts.ObservedAt)
	case "json_hn_algolia":
		return hnObservations(source, body, opts.ObservedAt)
	case "json_reddit_listing":
		return redditObservations(source, body, opts.ObservedAt)
	case "json_github_search":
		return githubSearchObservations(source, body, opts.ObservedAt)
	case "json_github_repo":
		return githubRepoObservation(source, body, opts.ObservedAt)
	case "json_github_advisories":
		return githubAdvisoryObservations(source, body, opts.ObservedAt)
	default:
		return htmlObservation(source, body, opts.ObservedAt)
	}
}

func rssObservations(source SourceDefinition, body []byte, observedAt string) []RawObservation {
	var doc rssDoc
	if err := xml.Unmarshal(body, &doc); err != nil {
		return htmlObservation(source, body, observedAt)
	}
	out := []RawObservation{}
	for _, item := range doc.Channel.Items {
		title := cleanText(item.Title)
		if title == "" {
			continue
		}
		out = append(out, observation(source, item.Link, title, item.Description, "", item.PubDate, observedAt, nil))
	}
	return out
}

func atomObservations(source SourceDefinition, body []byte, observedAt string) []RawObservation {
	var feed atomFeed
	if err := xml.Unmarshal(body, &feed); err != nil {
		return htmlObservation(source, body, observedAt)
	}
	out := []RawObservation{}
	for _, entry := range feed.Entries {
		title := cleanText(entry.Title)
		if title == "" {
			continue
		}
		link := entry.ID
		for _, candidate := range entry.Links {
			if candidate.Href != "" && (candidate.Rel == "" || candidate.Rel == "alternate") {
				link = candidate.Href
				break
			}
		}
		out = append(out, observation(source, link, title, entry.Summary, entry.Content, entry.Updated, observedAt, nil))
	}
	return out
}

func hnObservations(source SourceDefinition, body []byte, observedAt string) []RawObservation {
	var payload struct {
		Hits []struct {
			Title     string `json:"title"`
			StoryText string `json:"story_text"`
			URL       string `json:"url"`
			CreatedAt string `json:"created_at"`
		} `json:"hits"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return htmlObservation(source, body, observedAt)
	}
	out := []RawObservation{}
	for _, hit := range payload.Hits {
		title := cleanText(hit.Title)
		if title == "" {
			continue
		}
		out = append(out, observation(source, hit.URL, title, hit.StoryText, "", hit.CreatedAt, observedAt, nil))
	}
	return out
}

func redditObservations(source SourceDefinition, body []byte, observedAt string) []RawObservation {
	var payload struct {
		Data struct {
			Children []struct {
				Data struct {
					Title      string  `json:"title"`
					URL        string  `json:"url"`
					SelfText   string  `json:"selftext"`
					CreatedUTC float64 `json:"created_utc"`
					Subreddit  string  `json:"subreddit"`
					Permalink  string  `json:"permalink"`
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
		extra := []string{}
		if item.Subreddit != "" {
			extra = append(extra, item.Subreddit)
		}
		out = append(out, observation(source, link, title, item.SelfText, "", published, observedAt, extra))
	}
	return out
}

func githubSearchObservations(source SourceDefinition, body []byte, observedAt string) []RawObservation {
	var payload struct {
		Items []struct {
			FullName    string   `json:"full_name"`
			HTMLURL     string   `json:"html_url"`
			Description string   `json:"description"`
			UpdatedAt   string   `json:"updated_at"`
			Topics      []string `json:"topics"`
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
		out = append(out, observation(source, repo.HTMLURL, title, repo.Description, "", repo.UpdatedAt, observedAt, repo.Topics))
	}
	return out
}

func githubRepoObservation(source SourceDefinition, body []byte, observedAt string) []RawObservation {
	var repo struct {
		FullName    string   `json:"full_name"`
		HTMLURL     string   `json:"html_url"`
		Description string   `json:"description"`
		UpdatedAt   string   `json:"updated_at"`
		Topics      []string `json:"topics"`
	}
	if err := json.Unmarshal(body, &repo); err != nil {
		return htmlObservation(source, body, observedAt)
	}
	title := cleanText(repo.FullName)
	if title == "" {
		title = source.Title
	}
	return []RawObservation{observation(source, repo.HTMLURL, title, repo.Description, "", repo.UpdatedAt, observedAt, repo.Topics)}
}

func githubAdvisoryObservations(source SourceDefinition, body []byte, observedAt string) []RawObservation {
	var payload []struct {
		GHSAID      string `json:"ghsa_id"`
		HTMLURL     string `json:"html_url"`
		Summary     string `json:"summary"`
		Description string `json:"description"`
		UpdatedAt   string `json:"updated_at"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return htmlObservation(source, body, observedAt)
	}
	out := []RawObservation{}
	for _, advisory := range payload {
		title := cleanText(strings.Join([]string{advisory.GHSAID, advisory.Summary}, " "))
		if title == "" {
			continue
		}
		out = append(out, observation(source, advisory.HTMLURL, title, advisory.Summary, advisory.Description, advisory.UpdatedAt, observedAt, nil))
	}
	return out
}

func htmlObservation(source SourceDefinition, body []byte, observedAt string) []RawObservation {
	text := string(body)
	title := firstMatch(text, `(?is)<title[^>]*>(.*?)</title>`)
	if title == "" {
		title = source.Title
	}
	description := firstMatch(text, `(?is)<meta\s+name=["']description["'][^>]*content=["'](.*?)["']`)
	cleanBody := summarize(stripTags(text), 1800)
	return []RawObservation{observation(source, source.URL, title, description, cleanBody, "", observedAt, nil)}
}

func catalogObservation(source SourceDefinition, observedAt string, note string) RawObservation {
	description := "Static world scout source registered for " + source.Family + "."
	if note != "" {
		description = description + " " + note
	}
	return observation(source, source.URL, source.Title, description, "", observedAt, observedAt, []string{"catalog"})
}

func observation(source SourceDefinition, url, title, description, body, publishedAt, observedAt string, extra []string) RawObservation {
	title = cleanText(title)
	description = summarize(cleanText(description), 420)
	body = summarize(cleanText(body), 1800)
	keywords := unique(append(append([]string{}, source.Keywords...), extra...))
	row := RawObservation{
		Source:      "world_scout_go:" + source.Family,
		SourceID:    source.ID,
		SourceURL:   strings.TrimSpace(url),
		URL:         strings.TrimSpace(url),
		Publisher:   source.Publisher,
		Title:       title,
		Description: description,
		Body:        body,
		PublishedAt: strings.TrimSpace(publishedAt),
		Keywords:    keywords,
	}
	row.ID = observationID(row, observedAt)
	return row
}

func WriteObservations(path string, rows []RawObservation, replace bool) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	flag := os.O_CREATE | os.O_WRONLY | os.O_APPEND
	if replace {
		flag = os.O_CREATE | os.O_WRONLY | os.O_TRUNC
	}
	fh, err := os.OpenFile(path, flag, 0o644)
	if err != nil {
		return err
	}
	defer fh.Close()
	writer := bufio.NewWriter(fh)
	enc := json.NewEncoder(writer)
	for _, row := range rows {
		if strings.TrimSpace(row.Title) == "" {
			continue
		}
		if err := enc.Encode(row); err != nil {
			return err
		}
	}
	return writer.Flush()
}

func withDefaults(opts Options) Options {
	if opts.TimeoutMS <= 0 {
		opts.TimeoutMS = DefaultTimeoutMS
	}
	if opts.MaxBodyBytes <= 0 {
		opts.MaxBodyBytes = DefaultMaxBodyBytes
	}
	if opts.MaxItems <= 0 {
		opts.MaxItems = DefaultMaxItemsPerSource
	}
	return opts
}

func observationID(row RawObservation, observedAt string) string {
	h := sha256.New()
	for _, part := range []string{ScoutVersion, row.Source, row.SourceID, row.SourceURL, row.Title, row.PublishedAt, observedAt} {
		h.Write([]byte(part))
		h.Write([]byte{0})
	}
	return "obs_" + hex.EncodeToString(h.Sum(nil))[:16]
}

func cleanText(value string) string {
	value = html.UnescapeString(value)
	value = strings.Join(strings.Fields(value), " ")
	return strings.TrimSpace(value)
}

func summarize(value string, limit int) string {
	value = cleanText(value)
	if len(value) <= limit {
		return value
	}
	return value[:limit]
}

func unique(values []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, value := range values {
		value = cleanText(value)
		if value == "" {
			continue
		}
		key := strings.ToLower(value)
		if seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}

func firstMatch(text, pattern string) string {
	re := regexp.MustCompile(pattern)
	match := re.FindStringSubmatch(text)
	if len(match) < 2 {
		return ""
	}
	return cleanText(match[1])
}

func stripTags(text string) string {
	text = regexp.MustCompile(`(?is)<script.*?</script>`).ReplaceAllString(text, " ")
	text = regexp.MustCompile(`(?is)<style.*?</style>`).ReplaceAllString(text, " ")
	text = regexp.MustCompile(`(?is)<[^>]+>`).ReplaceAllString(text, " ")
	text = strings.ReplaceAll(text, "\u00a0", " ")
	return text
}

func parseFloat(value any) float64 {
	switch typed := value.(type) {
	case float64:
		return typed
	case int:
		return float64(typed)
	case string:
		parsed, _ := strconv.ParseFloat(typed, 64)
		return parsed
	default:
		return 0
	}
}

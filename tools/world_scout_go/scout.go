package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"html"
	"io"
	"net/http"
	"strings"
	"time"
)

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
	client := &http.Client{Timeout: 12 * time.Second}
	result := ScoutResult{FetchEnabled: true, SourceCount: len(sources)}
	observations := []Observation{}
	var errors []string
	for _, source := range sources {
		req, err := http.NewRequest(http.MethodGet, source.URL, nil)
		if err != nil {
			result.FailedSources++
			errors = append(errors, fmt.Sprintf("%s: %v", source.Name, err))
			continue
		}
		req.Header.Set("User-Agent", "dharma-world-scout/1.0")
		resp, err := client.Do(req)
		if err != nil {
			result.FailedSources++
			errors = append(errors, fmt.Sprintf("%s: %v", source.Name, err))
			continue
		}
		body, readErr := io.ReadAll(io.LimitReader(resp.Body, 300_000))
		resp.Body.Close()
		if readErr != nil || resp.StatusCode >= 400 {
			result.FailedSources++
			if readErr != nil {
				errors = append(errors, fmt.Sprintf("%s: %v", source.Name, readErr))
			} else {
				errors = append(errors, fmt.Sprintf("%s: status %d", source.Name, resp.StatusCode))
			}
			continue
		}
		result.SuccessfulSources++
		observations = append(observations, observationsFromBytes(source, body)...)
	}
	result.Errors = errors
	if len(errors) > 0 && len(observations) == 0 {
		return observations, result, fmt.Errorf("%s", strings.Join(errors, "; "))
	}
	return observations, result, nil
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

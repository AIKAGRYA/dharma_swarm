package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type Observation struct {
	ID          string   `json:"id"`
	Source      string   `json:"source"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	URL         string   `json:"url"`
	ObservedAt  string   `json:"observed_at"`
	Keywords    []string `json:"keywords"`
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
		req.Header.Set("User-Agent", "dharma-world-scout/0.1")
		resp, err := client.Do(req)
		if err != nil {
			result.FailedSources++
			errors = append(errors, fmt.Sprintf("%s: %v", source.Name, err))
			continue
		}
		body, readErr := io.ReadAll(io.LimitReader(resp.Body, 200_000))
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
		text := string(body)
		if obs, ok := observationFromText(source, text); ok {
			observations = append(observations, obs)
		}
	}
	result.Errors = errors
	if len(errors) > 0 && len(observations) == 0 {
		return observations, result, fmt.Errorf("%s", strings.Join(errors, "; "))
	}
	return observations, result, nil
}

func observationFromText(source Source, text string) (Observation, bool) {
	compact := strings.Join(strings.Fields(stripTags(text)), " ")
	if compact == "" {
		return Observation{}, false
	}
	if len(compact) > 500 {
		compact = compact[:500]
	}
	title := source.Name
	for _, marker := range []string{"agent", "AI", "model", "benchmark", "governance"} {
		if strings.Contains(strings.ToLower(compact), strings.ToLower(marker)) {
			title = fmt.Sprintf("%s public signal", source.Name)
			break
		}
	}
	id := stableID(source.URL + compact)
	return Observation{
		ID:          id,
		Source:      source.Name,
		Title:       title,
		Description: compact,
		URL:         source.URL,
		ObservedAt:  time.Now().UTC().Format(time.RFC3339),
		Keywords:    extractKeywords(compact),
	}, true
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
	candidates := []string{"agent", "agentic", "benchmark", "github", "governance", "startup", "research", "model", "tool"}
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

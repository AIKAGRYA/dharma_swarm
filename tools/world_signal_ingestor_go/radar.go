package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

const RadarVersion = "world_radar_go.v0"

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

type WorldSignal struct {
	ID             string         `json:"id"`
	Source         string         `json:"source"`
	SourceURL      string         `json:"source_url,omitempty"`
	Category       string         `json:"category"`
	Title          string         `json:"title"`
	RelevanceScore float64        `json:"relevance_score"`
	Keywords       []string       `json:"keywords"`
	Description    string         `json:"description"`
	ObservedAt     string         `json:"observed_at"`
	Metadata       map[string]any `json:"metadata"`
}

type weightedTerm struct {
	Term     string
	Weight   float64
	Keywords []string
}

var signalTerms = []weightedTerm{
	{Term: "subquadratic", Weight: 0.20, Keywords: []string{"subquadratic"}},
	{Term: "long context", Weight: 0.14, Keywords: []string{"long context"}},
	{Term: "million token", Weight: 0.12, Keywords: []string{"long context"}},
	{Term: "coding agent", Weight: 0.14, Keywords: []string{"coding agents"}},
	{Term: "agent", Weight: 0.08, Keywords: []string{"agents"}},
	{Term: "openai-compatible", Weight: 0.08, Keywords: []string{"api"}},
	{Term: "api", Weight: 0.06, Keywords: []string{"api"}},
	{Term: "swe-bench", Weight: 0.10, Keywords: []string{"benchmark"}},
	{Term: "benchmark", Weight: 0.08, Keywords: []string{"benchmark"}},
	{Term: "raised", Weight: 0.08, Keywords: []string{"funding"}},
	{Term: "seed funding", Weight: 0.10, Keywords: []string{"funding"}},
	{Term: "series a", Weight: 0.10, Keywords: []string{"funding"}},
	{Term: "launch", Weight: 0.07, Keywords: []string{"product launch"}},
	{Term: "preview", Weight: 0.06, Keywords: []string{"model release"}},
	{Term: "github", Weight: 0.07, Keywords: []string{"github"}},
	{Term: "open source", Weight: 0.07, Keywords: []string{"open source"}},
	{Term: "arxiv", Weight: 0.08, Keywords: []string{"paper"}},
	{Term: "paper", Weight: 0.06, Keywords: []string{"paper"}},
}

func ReadObservations(path string) ([]RawObservation, error) {
	if path == "" {
		return nil, errors.New("--input is required")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	trimmed := strings.TrimSpace(string(raw))
	if trimmed == "" {
		return nil, errors.New("input is empty")
	}
	if strings.HasPrefix(trimmed, "[") {
		var rows []RawObservation
		if err := json.Unmarshal([]byte(trimmed), &rows); err != nil {
			return nil, err
		}
		return rows, nil
	}

	var rows []RawObservation
	scanner := bufio.NewScanner(strings.NewReader(trimmed))
	for lineNumber := 1; scanner.Scan(); lineNumber++ {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var row RawObservation
		if err := json.Unmarshal([]byte(line), &row); err != nil {
			return nil, fmt.Errorf("line %d: %w", lineNumber, err)
		}
		rows = append(rows, row)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return rows, nil
}

func BuildSignals(rows []RawObservation, observedAt string, minScore float64) []WorldSignal {
	if observedAt == "" {
		observedAt = time.Now().UTC().Format(time.RFC3339)
	}
	out := make([]WorldSignal, 0, len(rows))
	for _, row := range rows {
		signal, ok := AnalyzeObservation(row, observedAt)
		if ok && signal.RelevanceScore >= minScore {
			out = append(out, signal)
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].RelevanceScore == out[j].RelevanceScore {
			return out[i].Title < out[j].Title
		}
		return out[i].RelevanceScore > out[j].RelevanceScore
	})
	return out
}

func AnalyzeObservation(row RawObservation, observedAt string) (WorldSignal, bool) {
	title := strings.TrimSpace(row.Title)
	if title == "" {
		return WorldSignal{}, false
	}
	sourceURL := strings.TrimSpace(row.SourceURL)
	if sourceURL == "" {
		sourceURL = strings.TrimSpace(row.URL)
	}
	source := strings.TrimSpace(row.Source)
	if source == "" {
		source = "world_radar_go"
	}
	text := strings.Join([]string{title, row.Description, row.Body, strings.Join(row.Keywords, " ")}, " ")
	lower := strings.ToLower(text)

	score := 0.28
	matchedTerms := []string{}
	keywords := append([]string{}, row.Keywords...)
	for _, item := range signalTerms {
		if strings.Contains(lower, item.Term) {
			score += item.Weight
			matchedTerms = append(matchedTerms, item.Term)
			keywords = append(keywords, item.Keywords...)
		}
	}
	if sourceURL != "" {
		score += 0.04
	}
	score = clamp(score, 0.0, 0.98)
	keywords = uniqueSorted(keywords)
	if len(keywords) > 10 {
		keywords = keywords[:10]
	}

	category := categorize(lower)
	description := strings.TrimSpace(row.Description)
	if description == "" {
		description = summarizeText(row.Body)
	}
	if description == "" {
		description = title
	}

	return WorldSignal{
		ID:             signalID(row, sourceURL, title),
		Source:         source,
		SourceURL:      sourceURL,
		Category:       category,
		Title:          title,
		RelevanceScore: round2(score),
		Keywords:       keywords,
		Description:    description,
		ObservedAt:     observedAt,
		Metadata: map[string]any{
			"radar_version":                 RadarVersion,
			"source_id":                     row.SourceID,
			"publisher":                     row.Publisher,
			"published_at":                  row.PublishedAt,
			"matched_terms":                 matchedTerms,
			"first_principles_questions":    FirstPrinciplesQuestions(),
			"iteration_steps":               IterationSteps(),
			"adjacent_search_queries":       AdjacentSearchQueries(title, keywords),
			"strategic_moves":               StrategicMoves(),
			"advancement_pressure":          "research, verify, map adjacency, reverse-engineer, prototype, route outcome",
			"human_review_required":         true,
			"claims_self_reported":          true,
			"raw_signal_not_final_judgment": true,
		},
	}, true
}

func WriteSignals(path string, signals []WorldSignal, replace bool) error {
	if path == "" {
		return errors.New("--output is required")
	}
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
	enc := json.NewEncoder(fh)
	for _, signal := range signals {
		if err := enc.Encode(signal); err != nil {
			return err
		}
	}
	return nil
}

func categorize(lower string) string {
	switch {
	case containsAny(lower, "raised", "seed funding", "series a", "funding"):
		return "funding"
	case containsAny(lower, "model", "llm", "token", "context", "benchmark", "preview"):
		return "model_release"
	case containsAny(lower, "github", "open source", "tool", "cli", "api", "mcp", "agent"):
		return "tool_release"
	case containsAny(lower, "arxiv", "paper", "research"):
		return "paper"
	default:
		return "opportunity"
	}
}

func containsAny(text string, needles ...string) bool {
	for _, needle := range needles {
		if strings.Contains(text, needle) {
			return true
		}
	}
	return false
}

func signalID(row RawObservation, sourceURL, title string) string {
	if strings.TrimSpace(row.ID) != "" {
		return row.ID
	}
	h := sha256.New()
	for _, part := range []string{row.Source, row.SourceID, sourceURL, title, row.PublishedAt} {
		h.Write([]byte(part))
		h.Write([]byte{0})
	}
	return "world_" + hex.EncodeToString(h.Sum(nil))[:16]
}

func summarizeText(text string) string {
	text = strings.Join(strings.Fields(text), " ")
	if len(text) <= 280 {
		return text
	}
	return text[:280]
}

func uniqueSorted(values []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, value := range values {
		value = strings.TrimSpace(value)
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

func clamp(value, minValue, maxValue float64) float64 {
	if value < minValue {
		return minValue
	}
	if value > maxValue {
		return maxValue
	}
	return value
}

func round2(value float64) float64 {
	return float64(int(value*100+0.5)) / 100
}

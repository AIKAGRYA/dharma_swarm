package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type Observation struct {
	ID          string   `json:"id"`
	Source      string   `json:"source"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	URL         string   `json:"url"`
	Keywords    []string `json:"keywords"`
}

type Signal struct {
	ID             string         `json:"id"`
	Source         string         `json:"source"`
	RawSource      string         `json:"raw_source"`
	Category       string         `json:"category"`
	Title          string         `json:"title"`
	Description    string         `json:"description"`
	RelevanceScore float64        `json:"relevance_score"`
	URL            string         `json:"url,omitempty"`
	Keywords       []string       `json:"keywords"`
	ObservedAt     string         `json:"observed_at"`
	Metadata       map[string]any `json:"metadata"`
}

func main() {
	input := flag.String("input", "", "raw observation JSONL path")
	output := flag.String("output", "", "normalized signal JSONL path")
	minScore := flag.Float64("min-score", 0.45, "minimum relevance score")
	flag.Parse()
	if *input == "" || *output == "" {
		fmt.Fprintln(os.Stderr, "--input and --output are required")
		os.Exit(2)
	}
	observations, err := readObservations(*input)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	signals := []Signal{}
	for _, obs := range observations {
		signal := SignalFromObservation(obs)
		if signal.RelevanceScore >= *minScore {
			signals = append(signals, signal)
		}
	}
	if err := writeSignals(*output, signals); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func SignalFromObservation(obs Observation) Signal {
	text := strings.ToLower(obs.Title + " " + obs.Description + " " + strings.Join(obs.Keywords, " "))
	category := categoryFor(text)
	score := scoreFor(text, obs.URL, obs.Source)
	title := strings.TrimSpace(obs.Title)
	if title == "" {
		title = "Untitled world signal"
	}
	return Signal{
		ID:             "sig-" + stableID(obs.ID+obs.URL+title),
		Source:         "world_scout",
		RawSource:      obs.Source,
		Category:       category,
		Title:          trim(title, 180),
		Description:    trim(obs.Description, 1400),
		RelevanceScore: score,
		URL:            obs.URL,
		Keywords:       mergeKeywords(obs.Keywords, text),
		ObservedAt:     time.Now().UTC().Format(time.RFC3339),
		Metadata: map[string]any{
			"raw_source":                   obs.Source,
			"url":                          obs.URL,
			"first_principles_questions":   firstPrinciples(title),
			"iteration_steps":              iterationSteps(),
			"adjacent_searches":            adjacentSearches(title),
			"strategic_moves":              []string{"verify", "map_pattern", "prototype", "feed_shakti"},
			"uncertainty":                  "requires independent corroboration before promotion",
			"reverse_engineering_boundary": "use only public facts and patterns",
		},
	}
}

func readObservations(path string) ([]Observation, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	observations := []Observation{}
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var obs Observation
		if err := json.Unmarshal([]byte(line), &obs); err == nil && obs.Title != "" {
			observations = append(observations, obs)
			continue
		}
		var row map[string]any
		if err := json.Unmarshal([]byte(line), &row); err != nil {
			continue
		}
		observations = append(observations, observationFromMap(row))
	}
	return observations, scanner.Err()
}

func observationFromMap(row map[string]any) Observation {
	return Observation{
		ID:          str(row["id"]),
		Source:      first(str(row["source"]), str(row["raw_source"]), "unknown"),
		Title:       first(str(row["title"]), str(row["headline"]), "Untitled world signal"),
		Description: first(str(row["description"]), str(row["summary"]), ""),
		URL:         first(str(row["url"]), str(row["source_url"]), ""),
		Keywords:    stringSlice(row["keywords"]),
	}
}

func writeSignals(path string, signals []Signal) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	enc := json.NewEncoder(file)
	for _, signal := range signals {
		if err := enc.Encode(signal); err != nil {
			return err
		}
	}
	return nil
}

func categoryFor(text string) string {
	switch {
	case containsAny(text, "benchmark", "eval", "swe-bench"):
		return "benchmark"
	case containsAny(text, "github", "repo", "open source", "tool"):
		return "tool_release"
	case containsAny(text, "startup", "company", "funding", "seed round"):
		return "company"
	case containsAny(text, "arxiv", "paper", "research", "preprint"):
		return "research"
	case containsAny(text, "governance", "safety", "policy"):
		return "governance"
	default:
		return "opportunity"
	}
}

func scoreFor(text, url, source string) float64 {
	score := 0.35
	for _, word := range []string{"agent", "agentic", "autonomous", "coding", "benchmark", "github", "startup", "research", "governance", "runtime"} {
		if strings.Contains(text, word) {
			score += 0.07
		}
	}
	if url != "" {
		score += 0.08
	}
	if source == "operator_drop" {
		score += 0.12
	}
	if score > 1.0 {
		return 1.0
	}
	return score
}

func firstPrinciples(title string) []string {
	return []string{
		"What capability boundary does " + title + " reveal?",
		"What primitive pattern is reusable without copying the surface?",
		"What is the smallest governed Dharma proof that would test this?",
	}
}

func iterationSteps() []string {
	return []string{
		"Verify primary public source.",
		"Find independent corroboration.",
		"List adjacent companies, repos, papers, and discussions.",
		"Extract user pain and capability primitive.",
		"Map to existing Dharma organs.",
		"Draft smallest prototype.",
		"Define evidence of success.",
		"Define governance and safety constraints.",
		"Feed Shakti as a draft opportunity.",
		"Re-score after next scan.",
	}
}

func adjacentSearches(title string) []string {
	return []string{
		"\"" + title + "\" company launch",
		"\"" + title + "\" GitHub",
		"\"" + title + "\" arxiv",
		"\"" + title + "\" alternatives competitors",
	}
}

func mergeKeywords(existing []string, text string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, keyword := range existing {
		addKeyword(&out, seen, keyword)
	}
	for _, keyword := range []string{"agent", "agentic", "benchmark", "github", "startup", "research", "governance", "runtime", "coding"} {
		if strings.Contains(text, keyword) {
			addKeyword(&out, seen, keyword)
		}
	}
	return out
}

func addKeyword(out *[]string, seen map[string]bool, keyword string) {
	keyword = strings.TrimSpace(strings.ToLower(keyword))
	if keyword == "" || seen[keyword] {
		return
	}
	seen[keyword] = true
	*out = append(*out, keyword)
}

func containsAny(text string, values ...string) bool {
	for _, value := range values {
		if strings.Contains(text, value) {
			return true
		}
	}
	return false
}

func stringSlice(value any) []string {
	items, ok := value.([]any)
	if !ok {
		return nil
	}
	out := []string{}
	for _, item := range items {
		if s := strings.TrimSpace(str(item)); s != "" {
			out = append(out, s)
		}
	}
	return out
}

func str(value any) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
}

func first(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func trim(value string, limit int) string {
	value = strings.TrimSpace(value)
	if len(value) <= limit {
		return value
	}
	return value[:limit]
}

func stableID(seed string) string {
	sum := sha256.Sum256([]byte(seed))
	return hex.EncodeToString(sum[:])[:16]
}

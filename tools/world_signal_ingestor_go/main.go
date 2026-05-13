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
	"sort"
	"strconv"
	"strings"
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
	ObservedAt  string   `json:"observed_at,omitempty"`
}

type Signal struct {
	ID             string                 `json:"id"`
	Source         string                 `json:"source"`
	Category       string                 `json:"category"`
	Title          string                 `json:"title"`
	Description    string                 `json:"description,omitempty"`
	RelevanceScore float64                `json:"relevance_score"`
	Keywords       []string               `json:"keywords,omitempty"`
	URL            string                 `json:"url,omitempty"`
	SourceURL      string                 `json:"source_url,omitempty"`
	Publisher      string                 `json:"publisher,omitempty"`
	PublishedAt    string                 `json:"published_at,omitempty"`
	Metadata       map[string]interface{} `json:"metadata"`
}

func main() {
	input := flag.String("input", "", "raw observation JSONL input")
	output := flag.String("output", "", "signal JSONL output")
	minScore := flag.Float64("min-score", 0.45, "minimum relevance score")
	flag.Parse()
	if *input == "" || *output == "" {
		fmt.Fprintln(os.Stderr, "--input and --output are required")
		os.Exit(2)
	}
	if err := run(*input, *output, *minScore); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(inputPath, outputPath string, minScore float64) error {
	rows, err := readRaw(inputPath)
	if err != nil {
		return err
	}
	signals := []Signal{}
	for _, row := range rows {
		signal := signalFromObservation(row)
		if signal.RelevanceScore < minScore {
			continue
		}
		signals = append(signals, signal)
	}
	sort.SliceStable(signals, func(i, j int) bool {
		return signals[i].RelevanceScore > signals[j].RelevanceScore
	})
	return writeSignals(outputPath, signals)
}

func signalFromObservation(row RawObservation) Signal {
	text := strings.ToLower(strings.Join([]string{row.Title, row.Description, row.Body, row.Family, strings.Join(row.Keywords, " ")}, " "))
	category := categoryFor(row, text)
	score := scoreFor(text, row)
	keywords := extractKeywords(text, row.Keywords)
	id := row.ID
	if id == "" {
		id = stableID(row.SourceID, row.URL, row.Title)
	}
	metadata := map[string]interface{}{
		"raw_source":                 firstNonEmpty(row.SourceID, row.Source, row.Publisher),
		"family":                     row.Family,
		"kind":                       row.Kind,
		"first_principles_questions": firstPrinciplesQuestions(row.Title),
		"iteration_steps":            iterationSteps(row.Title),
		"adjacent_searches":          adjacentSearches(row.Title, keywords),
		"strategic_moves":            strategicMoves(category),
		"dimensions":                 []string{"research", "prototype", "market", "governance"},
		"uncertainty":                uncertainty(score, row.URL),
	}
	return Signal{ID: id, Source: firstNonEmpty(row.Source, row.Publisher, row.SourceID, "world_scout"), Category: category, Title: row.Title, Description: firstNonEmpty(row.Description, row.Body), RelevanceScore: score, Keywords: keywords, URL: row.URL, SourceURL: row.SourceURL, Publisher: row.Publisher, PublishedAt: row.PublishedAt, Metadata: metadata}
}

func categoryFor(row RawObservation, text string) string {
	family := strings.ToLower(row.Family)
	if family == "agent_infra" {
		return "agent_infra"
	}
	if family == "security_regulatory" || containsAny(text, "cve", "advisory", "regulation", "policy") {
		return "security_regulatory"
	}
	if containsAny(text, "launch", "startup", "company", "product", "waitlist") {
		return "product_company"
	}
	if containsAny(text, "paper", "arxiv", "research", "benchmark") {
		return "competing_research"
	}
	if containsAny(text, "github", "repo", "framework", "sdk", "agent") {
		return "agent_infra"
	}
	return "world_signal"
}

func scoreFor(text string, row RawObservation) float64 {
	score := 0.25
	boosts := map[string]float64{"agent": 0.15, "coding agent": 0.15, "long context": 0.15, "subquadratic": 0.20, "startup": 0.10, "governance": 0.12, "safety": 0.10, "inference": 0.12, "workflow": 0.08, "benchmark": 0.10}
	for phrase, boost := range boosts {
		if strings.Contains(text, phrase) {
			score += boost
		}
	}
	if row.URL != "" {
		score += 0.05
	}
	if row.Family != "" {
		score += 0.05
	}
	if score > 1.0 {
		score = 1.0
	}
	return round(score)
}

func extractKeywords(text string, seeds []string) []string {
	terms := []string{"agent", "coding agent", "long context", "subquadratic", "inference", "governance", "security", "workflow", "benchmark", "startup", "github"}
	seen := map[string]bool{}
	out := []string{}
	for _, seed := range seeds {
		seed = strings.TrimSpace(seed)
		if seed != "" && !seen[seed] {
			seen[seed] = true
			out = append(out, seed)
		}
	}
	for _, term := range terms {
		if strings.Contains(text, term) && !seen[term] {
			seen[term] = true
			out = append(out, term)
		}
	}
	sort.Strings(out)
	return out
}

func firstPrinciplesQuestions(title string) []string {
	base := cleanTitle(title)
	return []string{"What primitive capability or constraint does this signal reveal?", "What changed in the world that made " + base + " possible now?", "What would our smallest truthful version of this be?", "Which adjacent markets or research threads become newly reachable?", "What evidence would prove this is signal rather than hype?", "Which moat is technical, distributional, regulatory, or workflow-based?", "What can be copied, what must be re-invented, and what should be avoided?", "Which current Dharma substrate can absorb this without new sprawl?", "What is the fast prototype, the deep research path, and the governance risk?", "What outcome would make Shakti prioritize this next week?"}
}

func iterationSteps(title string) []string {
	base := cleanTitle(title)
	return []string{"Verify the primary source and capture two independent adjacent witnesses.", "Map " + base + " to primitives: capability, audience, distribution, evidence.", "Find five similar companies, papers, repos, or practitioner threads.", "Reverse engineer the workflow and identify the smallest local prototype.", "Write the first-principles brief and expected failure modes.", "Draft a 24-hour experiment that can produce a visible artifact.", "Route the artifact candidate into opportunity_board with source metadata.", "Check governance, safety, and reputation constraints before public action.", "Compare outcome value against the source-weight memory.", "Promote, park, or discard based on evidence from the experiment."}
}

func adjacentSearches(title string, keywords []string) []string {
	terms := append([]string{cleanTitle(title)}, keywords...)
	out := []string{}
	for _, term := range terms {
		term = strings.TrimSpace(term)
		if term == "" {
			continue
		}
		out = append(out, term+" competitors", term+" github", term+" funding", term+" arxiv")
		if len(out) >= 12 {
			break
		}
	}
	return out[:min(len(out), 12)]
}

func strategicMoves(category string) []string {
	switch category {
	case "product_company", "agent_infra":
		return []string{"prototype wedge", "competitor map", "workflow teardown"}
	case "security_regulatory":
		return []string{"risk memo", "policy watch", "defensive checklist"}
	default:
		return []string{"research memo", "adjacent scan", "artifact experiment"}
	}
}

func readRaw(path string) ([]RawObservation, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	out := []RawObservation{}
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var row RawObservation
		if err := json.Unmarshal([]byte(line), &row); err != nil {
			continue
		}
		if strings.TrimSpace(row.Title) != "" {
			out = append(out, row)
		}
	}
	return out, scanner.Err()
}

func writeSignals(path string, signals []Signal) error {
	dir := filepath.Dir(path)
	if dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	writer := bufio.NewWriter(file)
	for _, signal := range signals {
		raw, err := json.Marshal(signal)
		if err != nil {
			return err
		}
		if _, err := writer.Write(append(raw, '\n')); err != nil {
			return err
		}
	}
	return writer.Flush()
}

func containsAny(text string, terms ...string) bool {
	for _, term := range terms {
		if strings.Contains(text, term) {
			return true
		}
	}
	return false
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

func cleanTitle(title string) string {
	title = strings.TrimSpace(title)
	if title == "" {
		return "this signal"
	}
	if len(title) > 80 {
		title = title[:80]
	}
	return title
}

func uncertainty(score float64, url string) string {
	if url == "" {
		return "high"
	}
	if score >= 0.8 {
		return "medium"
	}
	return "high"
}

func round(value float64) float64 {
	raw := strconv.FormatFloat(value, 'f', 3, 64)
	parsed, _ := strconv.ParseFloat(raw, 64)
	return parsed
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

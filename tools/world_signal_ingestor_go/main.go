package main

import (
	"bufio"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/adaptercontract"
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

const maxObservationLineBytes = 4 * 1024 * 1024

type Observation struct {
	ID          string   `json:"id"`
	Source      string   `json:"source"`
	SourceType  string   `json:"source_type"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	URL         string   `json:"url"`
	Keywords    []string `json:"keywords"`
	CascadeFor  string   `json:"cascade_for,omitempty"`
}

type Signal struct {
	ID             string         `json:"id"`
	Source         string         `json:"source"`
	RawSource      string         `json:"raw_source"`
	SourceType     string         `json:"source_type"`
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
	receiptDir := flag.String("receipt-dir", "", "normal mode directory for per-signal receipt JSON files")
	eventType := flag.String("event-type", "", "receipt mode event type")
	sourceURL := flag.String("source-url", "", "receipt mode source URL")
	correlationID := flag.String("correlation-id", "", "receipt mode correlation ID")
	observedAt := flag.String("observed-at", "", "receipt mode observed-at timestamp")
	flag.Parse()

	if *input == "" || *output == "" {
		fmt.Fprintln(os.Stderr, "--input and --output are required")
		os.Exit(2)
	}
	if *eventType != "" {
		if *sourceURL == "" || *correlationID == "" {
			fmt.Fprintln(os.Stderr, "--source-url and --correlation-id are required in receipt mode")
			os.Exit(2)
		}
		if err := writeReceipt(*input, *output, *eventType, *sourceURL, *correlationID, *observedAt); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		return
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
	if *receiptDir != "" {
		if *correlationID == "" {
			fmt.Fprintln(os.Stderr, "--correlation-id is required when --receipt-dir is set")
			os.Exit(2)
		}
		if err := writeSignalReceipts(*receiptDir, signals, *correlationID, *observedAt); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
}

func writeReceipt(inputPath, outputPath, eventType, sourceURL, correlationID, observedAt string) error {
	payload, err := os.ReadFile(inputPath)
	if err != nil {
		return err
	}
	fixture := adaptercontract.Fixture{
		CorrelationID: correlationID,
		Source:        eventType,
		SourceURL:     sourceURL,
		ObservedAt:    observedAt,
		Payload:       json.RawMessage(payload),
	}
	r, adaptErr := Adapter{}.Adapt(context.Background(), fixture)
	if adaptErr != nil && r.ReceiptID == "" {
		return adaptErr
	}
	if err := receipt.Write(outputPath, r); err != nil {
		return err
	}
	return adaptErr
}

func writeSignalReceipts(receiptDir string, signals []Signal, correlationID, observedAt string) error {
	if err := os.MkdirAll(receiptDir, 0o755); err != nil {
		return err
	}
	for _, signal := range signals {
		payload, err := json.Marshal(signal)
		if err != nil {
			return err
		}
		fixture := adaptercontract.Fixture{
			CorrelationID: correlationID,
			Source:        string(EventWorldSignal),
			SourceURL:     first(signal.URL, "world_signal://"+signal.ID),
			ObservedAt:    first(observedAt, signal.ObservedAt),
			Payload:       json.RawMessage(payload),
		}
		r, adaptErr := Adapter{}.Adapt(context.Background(), fixture)
		if adaptErr != nil && r.ReceiptID == "" {
			return adaptErr
		}
		if adaptErr != nil {
			return adaptErr
		}
		if err := receipt.Write(filepath.Join(receiptDir, r.ReceiptID+".json"), r); err != nil {
			return err
		}
	}
	return nil
}

func SignalFromObservation(obs Observation) Signal {
	text := strings.ToLower(obs.Title + " " + obs.Description + " " + strings.Join(obs.Keywords, " "))
	category := categoryFor(text)
	score := scoreFor(text, obs.URL, obs.Source, obs.SourceType)
	title := strings.TrimSpace(obs.Title)
	if title == "" {
		title = "Untitled world signal"
	}

	// Generate deterministic ID from observation ID or content hash
	sigID := obs.ID
	if sigID == "" {
		h := sha256.Sum256([]byte(obs.Title + obs.Description + obs.URL))
		sigID = hex.EncodeToString(h[:8])
	}

	observedAt := time.Now().UTC().Format(time.RFC3339)

	iterationSteps := []string{
		"ingest", "parse", "score", "categorize",
		"enrich", "dedupe", "validate", "emit",
		"receipt", "archive",
	}

	return Signal{
		ID:             "sig-" + sigID,
		Source:         "world_scout",
		RawSource:      first(obs.Source, obs.SourceType),
		SourceType:     obs.SourceType,
		Category:       category,
		Title:          title,
		Description:    obs.Description,
		RelevanceScore: score,
		URL:            obs.URL,
		Keywords:       obs.Keywords,
		ObservedAt:     observedAt,
		Metadata: map[string]any{
			"raw_source":      first(obs.Source, obs.SourceType),
			"iteration_steps": iterationSteps,
		},
	}
}

// categoryFor returns a category string based on text content.
func categoryFor(text string) string {
	benchmarkKeywords := []string{"benchmark", "eval", "evaluation", "leaderboard", "performance", "metric"}
	for _, kw := range benchmarkKeywords {
		if strings.Contains(text, kw) {
			return "benchmark"
		}
	}
	agentKeywords := []string{"agent", "agentic", "autonomous", "automation"}
	for _, kw := range agentKeywords {
		if strings.Contains(text, kw) {
			return "agent"
		}
	}
	infraKeywords := []string{"infrastructure", "platform", "runtime", "sdk", "api", "cloud"}
	for _, kw := range infraKeywords {
		if strings.Contains(text, kw) {
			return "infrastructure"
		}
	}
	return "general"
}

// scoreFor returns a relevance score based on text content and source signals.
func scoreFor(text, url, source, sourceType string) float64 {
	score := 0.5

	highValueKeywords := []string{
		"agentic", "agent", "benchmark", "startup", "github",
		"coding", "runtime", "ecosystem", "infrastructure",
	}
	for _, kw := range highValueKeywords {
		if strings.Contains(text, kw) {
			score += 0.05
		}
	}

	// Boost for trusted sources
	trustedSources := []string{"operator_drop", "github", "arxiv", "techcrunch"}
	for _, s := range trustedSources {
		if strings.Contains(strings.ToLower(source), s) ||
			strings.Contains(strings.ToLower(sourceType), s) {
			score += 0.1
			break
		}
	}

	// URL signals
	if strings.Contains(url, "github.com") || strings.Contains(url, "arxiv.org") {
		score += 0.05
	}

	if score > 1.0 {
		score = 1.0
	}
	return score
}

// readObservations reads a JSONL file of Observation records.
func readObservations(path string) ([]Observation, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, maxObservationLineBytes), maxObservationLineBytes)

	var observations []Observation
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		var obs Observation
		if err := json.Unmarshal(line, &obs); err != nil {
			return nil, fmt.Errorf("failed to parse observation: %w", err)
		}
		observations = append(observations, obs)
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("scanner error: %w", err)
	}
	return observations, nil
}

// writeSignals writes signals to a JSONL file.
func writeSignals(path string, signals []Signal) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()

	enc := json.NewEncoder(f)
	for _, sig := range signals {
		if err := enc.Encode(sig); err != nil {
			return err
		}
	}
	return nil
}

// first returns the first non-empty string from the arguments.
func first(vals ...string) string {
	for _, v := range vals {
		if v != "" {
			return v
		}
	}
	return ""
}
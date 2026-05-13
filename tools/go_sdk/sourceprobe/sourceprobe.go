// Package sourceprobe provides small, deterministic helpers for Go "mouths"
// that inventory trusted source endpoints and emit one aggregate receipt.
//
// Boundary: sourceprobe fetches metadata and hashes bounded response bodies.
// It does not summarize content, execute registry commands, call Python
// policy, write runtime DBs, or mutate ontology state.
package sourceprobe

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

const (
	DefaultTimeoutMS    = 750
	DefaultMaxBodyBytes = 1 << 20
)

// HTTPClient is the subset of http.Client used by sourceprobe. Tests inject
// a deterministic RoundTripper through a regular *http.Client.
type HTTPClient interface {
	Do(*http.Request) (*http.Response, error)
}

// SourceDefinition is a static, code-reviewed source endpoint. The CLI
// modules do not accept arbitrary URLs in v0; adding a source is a code change.
type SourceDefinition struct {
	ID                     string   `json:"id"`
	Title                  string   `json:"title"`
	URL                    string   `json:"url"`
	Kind                   string   `json:"kind"`
	Publisher              string   `json:"publisher"`
	TopicTags              []string `json:"topic_tags"`
	LicenseCompatibility   string   `json:"license_compatibility"`
	FreshnessWindow        string   `json:"freshness_window"`
	OriginAttestation      string   `json:"origin_attestation"`
	HallucinationRiskClass string   `json:"hallucination_risk_class"`
	RoutingClass           string   `json:"routing_class"`
	CorroborationCount     int      `json:"corroboration_count"`
	ClaimsSelfReported     bool     `json:"claims_self_reported,omitempty"`
	SocialRaw              bool     `json:"social_raw,omitempty"`
	HumanReviewRequired    bool     `json:"human_review_required,omitempty"`
}

// Options configures an aggregate source inventory run.
type Options struct {
	CorrelationID string
	ObservedAt    string
	TimeoutMS     int
	MaxBodyBytes  int64
	Fetch         bool
	Sources       []SourceDefinition
	HTTPClient    HTTPClient
}

// RejectError reports a malformed source catalog or probe setup failure while
// still allowing callers to persist the rejected receipt returned alongside it.
type RejectError struct {
	Reason string
}

func (e RejectError) Error() string {
	if e.Reason == "" {
		return "source probe rejected"
	}
	return "source probe rejected: " + e.Reason
}

type AggregatePayload struct {
	IngestSchema string              `json:"ingest_schema"`
	ProbePolicy  ProbePolicy         `json:"probe_policy"`
	Sources      []SourceObservation `json:"sources"`
	Summary      Summary             `json:"summary"`
	Rejections   []SourceRejection   `json:"rejections,omitempty"`
}

type ProbePolicy struct {
	ExternalNetwork   bool     `json:"external_network"`
	TimeoutMS         int      `json:"timeout_ms"`
	MaxBodyBytes      int64    `json:"max_body_bytes"`
	AllowedHosts      []string `json:"allowed_hosts"`
	RawPayloadStorage string   `json:"raw_payload_storage"`
}

type SourceObservation struct {
	ID                     string   `json:"id"`
	Title                  string   `json:"title"`
	URL                    string   `json:"url"`
	Host                   string   `json:"host"`
	Kind                   string   `json:"kind"`
	Publisher              string   `json:"publisher"`
	TopicTags              []string `json:"topic_tags"`
	LicenseCompatibility   string   `json:"license_compatibility"`
	FreshnessWindow        string   `json:"freshness_window"`
	OriginAttestation      string   `json:"origin_attestation"`
	HallucinationRiskClass string   `json:"hallucination_risk_class"`
	RoutingClass           string   `json:"routing_class"`
	CorroborationCount     int      `json:"corroboration_count"`
	ClaimsSelfReported     bool     `json:"claims_self_reported,omitempty"`
	SocialRaw              bool     `json:"social_raw,omitempty"`
	HumanReviewRequired    bool     `json:"human_review_required,omitempty"`
	Fetched                bool     `json:"fetched"`
	Reachable              bool     `json:"reachable"`
	StatusCode             int      `json:"status_code,omitempty"`
	ContentType            string   `json:"content_type,omitempty"`
	BodyBytes              int64    `json:"body_bytes,omitempty"`
	BodySHA256             string   `json:"body_sha256,omitempty"`
	Error                  string   `json:"error,omitempty"`
}

type Summary struct {
	SourceCount    int `json:"source_count"`
	FetchedCount   int `json:"fetched_count"`
	ReachableCount int `json:"reachable_count"`
	RejectedCount  int `json:"rejected_count"`
}

type SourceRejection struct {
	ID     string `json:"id"`
	URL    string `json:"url"`
	Reason string `json:"reason"`
}

// BuildAggregateReceipt emits exactly one receipt for a static source catalog.
// Unreachable endpoints are payload facts; malformed static config rejects the
// aggregate receipt.
func BuildAggregateReceipt(sourceName, sourceURL, schema string, trust *receipt.TrustEnvelope, opts Options) (receipt.Receipt, error) {
	opts = withDefaults(opts)
	spec := receipt.BuildSpec{
		Source:        sourceName,
		SourceURL:     sourceURL,
		CorrelationID: opts.CorrelationID,
		ObservedAt:    opts.ObservedAt,
		TrustEnvelope: trust,
	}
	if opts.TimeoutMS <= 0 {
		return rejectedReceipt(spec, schema, opts, nil, "invalid_timeout_ms")
	}
	if opts.MaxBodyBytes <= 0 {
		return rejectedReceipt(spec, schema, opts, nil, "invalid_max_body_bytes")
	}
	sources := sortedSources(opts.Sources)
	if len(sources) == 0 {
		return rejectedReceipt(spec, schema, opts, nil, "no_sources")
	}
	if rejection := validateSources(sources); rejection != nil {
		reason := rejection.Reason + ":" + rejection.URL
		return rejectedReceipt(spec, schema, opts, []SourceRejection{*rejection}, reason)
	}

	payload := AggregatePayload{
		IngestSchema: schema,
		ProbePolicy:  probePolicy(opts, sources),
		Sources:      observeSources(context.Background(), opts, sources),
	}
	payload.Summary = summarize(payload.Sources, 0)
	raw, err := json.Marshal(payload)
	if err != nil {
		return receipt.Receipt{}, err
	}
	return receipt.Build(spec, raw)
}

func withDefaults(opts Options) Options {
	if opts.TimeoutMS == 0 {
		opts.TimeoutMS = DefaultTimeoutMS
	}
	if opts.MaxBodyBytes == 0 {
		opts.MaxBodyBytes = DefaultMaxBodyBytes
	}
	if opts.HTTPClient == nil {
		opts.HTTPClient = &http.Client{Timeout: time.Duration(opts.TimeoutMS) * time.Millisecond}
	}
	return opts
}

func sortedSources(sources []SourceDefinition) []SourceDefinition {
	out := append([]SourceDefinition(nil), sources...)
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}

func validateSources(sources []SourceDefinition) *SourceRejection {
	seen := map[string]bool{}
	for _, source := range sources {
		if source.ID == "" {
			return &SourceRejection{URL: source.URL, Reason: "missing_source_id"}
		}
		if seen[source.ID] {
			return &SourceRejection{ID: source.ID, URL: source.URL, Reason: "duplicate_source_id"}
		}
		seen[source.ID] = true
		if err := validateSourceURL(source.URL); err != nil {
			return &SourceRejection{ID: source.ID, URL: source.URL, Reason: err.Error()}
		}
		if source.Kind == "" {
			return &SourceRejection{ID: source.ID, URL: source.URL, Reason: "missing_kind"}
		}
	}
	return nil
}

func validateSourceURL(raw string) error {
	parsed, err := url.Parse(raw)
	if err != nil {
		return errors.New("malformed_url")
	}
	if parsed.Scheme != "https" && parsed.Scheme != "http" {
		return fmt.Errorf("unsupported_scheme:%s", parsed.Scheme)
	}
	if parsed.Hostname() == "" {
		return errors.New("missing_host")
	}
	if parsed.Scheme == "http" && !isLoopbackHost(parsed.Hostname()) {
		return errors.New("insecure_external_http")
	}
	return nil
}

func isLoopbackHost(host string) bool {
	return host == "127.0.0.1" || host == "localhost" || host == "::1"
}

func observeSources(ctx context.Context, opts Options, sources []SourceDefinition) []SourceObservation {
	out := make([]SourceObservation, 0, len(sources))
	for _, source := range sources {
		obs := baseObservation(source)
		if opts.Fetch {
			fetch(ctx, opts, &obs)
		}
		out = append(out, obs)
	}
	return out
}

func baseObservation(source SourceDefinition) SourceObservation {
	host := ""
	if parsed, err := url.Parse(source.URL); err == nil {
		host = parsed.Hostname()
	}
	tags := append([]string(nil), source.TopicTags...)
	sort.Strings(tags)
	return SourceObservation{
		ID:                     source.ID,
		Title:                  source.Title,
		URL:                    source.URL,
		Host:                   host,
		Kind:                   source.Kind,
		Publisher:              source.Publisher,
		TopicTags:              tags,
		LicenseCompatibility:   source.LicenseCompatibility,
		FreshnessWindow:        source.FreshnessWindow,
		OriginAttestation:      source.OriginAttestation,
		HallucinationRiskClass: source.HallucinationRiskClass,
		RoutingClass:           source.RoutingClass,
		CorroborationCount:     source.CorroborationCount,
		ClaimsSelfReported:     source.ClaimsSelfReported,
		SocialRaw:              source.SocialRaw,
		HumanReviewRequired:    source.HumanReviewRequired,
	}
}

func fetch(parent context.Context, opts Options, obs *SourceObservation) {
	timeout := time.Duration(opts.TimeoutMS) * time.Millisecond
	ctx, cancel := context.WithTimeout(parent, timeout)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, obs.URL, nil)
	if err != nil {
		obs.Error = "request_setup_failed"
		return
	}
	req.Header.Set("User-Agent", "dharma-swarm-sourceprobe/0")
	resp, err := opts.HTTPClient.Do(req)
	obs.Fetched = true
	if err != nil {
		obs.Error = classifyFetchError(err)
		return
	}
	defer resp.Body.Close()

	obs.StatusCode = resp.StatusCode
	obs.ContentType = resp.Header.Get("Content-Type")
	body, err := io.ReadAll(io.LimitReader(resp.Body, opts.MaxBodyBytes))
	if err != nil {
		obs.Error = "read_failed"
		return
	}
	obs.BodyBytes = int64(len(body))
	if len(body) > 0 {
		obs.BodySHA256 = "sha256:" + sha256Hex(body)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		obs.Error = fmt.Sprintf("http_status:%d", resp.StatusCode)
		return
	}
	obs.Reachable = true
}

func summarize(observations []SourceObservation, rejectedCount int) Summary {
	summary := Summary{
		SourceCount:   len(observations),
		RejectedCount: rejectedCount,
	}
	for _, obs := range observations {
		if obs.Fetched {
			summary.FetchedCount++
		}
		if obs.Reachable {
			summary.ReachableCount++
		}
	}
	return summary
}

func rejectedReceipt(spec receipt.BuildSpec, schema string, opts Options, rejections []SourceRejection, reason string) (receipt.Receipt, error) {
	sources := sortedSources(opts.Sources)
	payload := AggregatePayload{
		IngestSchema: schema,
		ProbePolicy:  probePolicy(opts, sources),
		Sources:      []SourceObservation{},
		Summary:      summarize(nil, len(rejections)),
		Rejections:   rejections,
	}
	if payload.Summary.RejectedCount == 0 {
		payload.Summary.RejectedCount = 1
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return receipt.Receipt{}, err
	}
	rejected, err := receipt.Reject(spec, raw, reason)
	if err != nil {
		return receipt.Receipt{}, err
	}
	return rejected, RejectError{Reason: reason}
}

func probePolicy(opts Options, sources []SourceDefinition) ProbePolicy {
	return ProbePolicy{
		ExternalNetwork:   opts.Fetch,
		TimeoutMS:         opts.TimeoutMS,
		MaxBodyBytes:      opts.MaxBodyBytes,
		AllowedHosts:      allowedHosts(sources),
		RawPayloadStorage: "hash_only",
	}
}

func allowedHosts(sources []SourceDefinition) []string {
	seen := map[string]bool{}
	var hosts []string
	for _, source := range sources {
		parsed, err := url.Parse(source.URL)
		if err != nil {
			continue
		}
		host := parsed.Hostname()
		if host == "" || seen[host] {
			continue
		}
		seen[host] = true
		hosts = append(hosts, host)
	}
	sort.Strings(hosts)
	return hosts
}

func classifyFetchError(err error) string {
	if err == nil {
		return ""
	}
	msg := err.Error()
	if strings.Contains(msg, "Client.Timeout") || strings.Contains(msg, "context deadline exceeded") {
		return "timeout"
	}
	return "request_failed"
}

func sha256Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

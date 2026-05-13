package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"runtime"
	"sort"
	"strings"
	"time"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

const (
	InventorySchema    = "local_model_inventory.v1"
	SourceName         = "local_model_inventory_go"
	SourceURL          = "local://model-runtime-inventory"
	DefaultTimeoutMS   = 750
	maxResponseBodyLen = 1 << 20
)

var allowedLoopbackHosts = []string{"127.0.0.1", "localhost", "[::1]"}

// RuntimeEndpoint describes one loopback-only runtime probe.
type RuntimeEndpoint struct {
	Name string
	Kind string
	URL  string
}

// InventoryOptions configures one aggregate inventory run.
type InventoryOptions struct {
	CorrelationID string
	ObservedAt    string
	TimeoutMS     int
	Endpoints     []RuntimeEndpoint
	BinaryNames   []string
	LookupPath    func(string) (string, error)
	EnvNames      []string
	LookupEnv     func(string) (string, bool)
	HTTPClient    *http.Client
}

// RejectError reports a setup/config rejection while still allowing callers to
// persist the rejected receipt returned alongside it.
type RejectError struct {
	Reason string
}

func (e RejectError) Error() string {
	if e.Reason == "" {
		return "inventory rejected"
	}
	return "inventory rejected: " + e.Reason
}

type InventoryPayload struct {
	InventorySchema string             `json:"inventory_schema"`
	ProbePolicy     ProbePolicy        `json:"probe_policy"`
	Host            HostInfo           `json:"host"`
	Binaries        []BinaryPresence   `json:"binaries"`
	Environment     []EnvironmentFact  `json:"environment"`
	Runtimes        []RuntimeResult    `json:"runtimes"`
	Summary         InventorySummary   `json:"summary"`
	Rejections      []RuntimeRejection `json:"rejections,omitempty"`
}

type ProbePolicy struct {
	LoopbackOnly    bool     `json:"loopback_only"`
	TimeoutMS       int      `json:"timeout_ms"`
	ExternalNetwork bool     `json:"external_network"`
	AllowedHosts    []string `json:"allowed_hosts"`
}

type HostInfo struct {
	GOOS   string `json:"goos"`
	GOARCH string `json:"goarch"`
}

type BinaryPresence struct {
	Name    string `json:"name"`
	Present bool   `json:"present"`
	Path    string `json:"path"`
}

type RuntimeResult struct {
	Name       string          `json:"name"`
	Kind       string          `json:"kind"`
	URL        string          `json:"url"`
	Reachable  bool            `json:"reachable"`
	StatusCode int             `json:"status_code,omitempty"`
	Models     []ModelInfo     `json:"models"`
	Exposure   RuntimeExposure `json:"exposure"`
	Error      string          `json:"error,omitempty"`
}

type ModelInfo struct {
	ID string `json:"id"`
}

type RuntimeExposure struct {
	LoopbackURL          bool   `json:"loopback_url"`
	RemoteHostObserved   bool   `json:"remote_host_observed"`
	RemoteHostClass      string `json:"remote_host_class,omitempty"`
	CloudOffloadObserved bool   `json:"cloud_offload_observed"`
	CloudOffloadEnabled  bool   `json:"cloud_offload_enabled,omitempty"`
	AuthObserved         bool   `json:"auth_observed"`
	TelemetryObserved    bool   `json:"telemetry_observed"`
	LicenseObserved      bool   `json:"license_observed"`
}

type EnvironmentFact struct {
	Name       string `json:"name"`
	Present    bool   `json:"present"`
	ValueClass string `json:"value_class"`
}

type InventorySummary struct {
	RuntimeCount   int `json:"runtime_count"`
	ReachableCount int `json:"reachable_count"`
	ModelCount     int `json:"model_count"`
	RejectedCount  int `json:"rejected_count"`
}

type RuntimeRejection struct {
	Name   string `json:"name"`
	URL    string `json:"url"`
	Reason string `json:"reason"`
}

// BuildInventoryReceipt probes configured local runtimes and returns exactly
// one aggregate receipt. Unreachable loopback endpoints are payload facts, not
// failures. Non-loopback or malformed probe setup returns a rejected receipt
// plus RejectError.
func BuildInventoryReceipt(opts InventoryOptions) (receipt.Receipt, error) {
	opts = withDefaults(opts)
	spec := receipt.BuildSpec{
		Source:        SourceName,
		SourceURL:     SourceURL,
		CorrelationID: opts.CorrelationID,
		ObservedAt:    opts.ObservedAt,
		TrustEnvelope: localTrustEnvelope(),
	}

	if opts.TimeoutMS <= 0 {
		return rejectedInventory(spec, opts, nil, "invalid_timeout_ms")
	}

	if rejection := validateEndpoints(opts.Endpoints); rejection != nil {
		reason := rejection.Reason + ":" + rejection.URL
		return rejectedInventory(spec, opts, []RuntimeRejection{*rejection}, reason)
	}

	payload := InventoryPayload{
		InventorySchema: InventorySchema,
		ProbePolicy:     probePolicy(opts.TimeoutMS),
		Host:            hostInfo(),
		Binaries:        collectBinaries(opts.BinaryNames, opts.LookupPath),
		Environment:     collectEnvironment(opts.EnvNames, opts.LookupEnv),
		Runtimes:        probeRuntimes(context.Background(), opts),
	}
	payload.Summary = summarize(payload.Runtimes, 0)

	raw, err := json.Marshal(payload)
	if err != nil {
		return receipt.Receipt{}, err
	}
	return receipt.Build(spec, raw)
}

func withDefaults(opts InventoryOptions) InventoryOptions {
	if opts.TimeoutMS == 0 {
		opts.TimeoutMS = DefaultTimeoutMS
	}
	if len(opts.Endpoints) == 0 {
		opts.Endpoints = DefaultRuntimeEndpoints()
	}
	if len(opts.BinaryNames) == 0 {
		opts.BinaryNames = DefaultBinaryNames()
	}
	if len(opts.EnvNames) == 0 {
		opts.EnvNames = DefaultEnvNames()
	}
	if opts.LookupPath == nil {
		opts.LookupPath = exec.LookPath
	}
	if opts.LookupEnv == nil {
		opts.LookupEnv = os.LookupEnv
	}
	if opts.HTTPClient == nil {
		opts.HTTPClient = &http.Client{Timeout: time.Duration(opts.TimeoutMS) * time.Millisecond}
	}
	return opts
}

func DefaultRuntimeEndpoints() []RuntimeEndpoint {
	return []RuntimeEndpoint{
		{Name: "ollama", Kind: "ollama_tags", URL: "http://127.0.0.1:11434/api/tags"},
		{Name: "ollama_running", Kind: "ollama_ps", URL: "http://127.0.0.1:11434/api/ps"},
		{Name: "lm_studio", Kind: "openai_models", URL: "http://127.0.0.1:1234/v1/models"},
		{Name: "llama_cpp", Kind: "openai_models", URL: "http://127.0.0.1:8080/v1/models"},
		{Name: "vllm_openai", Kind: "openai_models", URL: "http://127.0.0.1:8000/v1/models"},
	}
}

func DefaultBinaryNames() []string {
	return []string{
		"ollama",
		"lms",
		"lmstudio",
		"llama-server",
		"llama-cpp-server",
		"vllm",
		"sglang",
		"python",
		"nvidia-smi",
		"local-ai",
	}
}

func DefaultEnvNames() []string {
	return []string{
		"OLLAMA_HOST",
		"OLLAMA_NO_CLOUD",
		"OLLAMA_ORIGINS",
		"LMSTUDIO_HOST",
		"VLLM_HOST",
		"OPENAI_API_KEY",
		"NVIDIA_API_KEY",
	}
}

func validateEndpoints(endpoints []RuntimeEndpoint) *RuntimeRejection {
	for _, endpoint := range endpoints {
		if err := validateLoopbackURL(endpoint.URL); err != nil {
			return &RuntimeRejection{
				Name:   endpoint.Name,
				URL:    endpoint.URL,
				Reason: err.Error(),
			}
		}
	}
	return nil
}

func validateLoopbackURL(raw string) error {
	parsed, err := url.Parse(raw)
	if err != nil {
		return fmt.Errorf("malformed_url")
	}
	if parsed.Scheme != "http" {
		return fmt.Errorf("unsupported_scheme:%s", parsed.Scheme)
	}
	host := parsed.Hostname()
	if host == "127.0.0.1" || host == "localhost" || host == "::1" {
		return nil
	}
	return fmt.Errorf("non_loopback_url")
}

func probeRuntimes(ctx context.Context, opts InventoryOptions) []RuntimeResult {
	results := make([]RuntimeResult, 0, len(opts.Endpoints))
	timeout := time.Duration(opts.TimeoutMS) * time.Millisecond
	for _, endpoint := range opts.Endpoints {
		results = append(results, probeRuntime(ctx, opts.HTTPClient, timeout, endpoint))
	}
	return results
}

func probeRuntime(parent context.Context, client *http.Client, timeout time.Duration, endpoint RuntimeEndpoint) RuntimeResult {
	result := RuntimeResult{
		Name:   endpoint.Name,
		Kind:   endpoint.Kind,
		URL:    endpoint.URL,
		Models: []ModelInfo{},
		Exposure: RuntimeExposure{
			LoopbackURL: isLoopbackURL(endpoint.URL),
		},
	}

	ctx, cancel := context.WithTimeout(parent, timeout)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.URL, nil)
	if err != nil {
		result.Error = "request_setup_failed"
		return result
	}
	resp, err := client.Do(req)
	if err != nil {
		result.Error = classifyProbeError(err)
		return result
	}
	defer resp.Body.Close()

	result.StatusCode = resp.StatusCode
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		result.Error = fmt.Sprintf("http_status:%d", resp.StatusCode)
		return result
	}
	result.Reachable = true

	body, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseBodyLen))
	if err != nil {
		result.Error = "read_failed"
		return result
	}
	result.Exposure = inspectExposure(endpoint.URL, body)
	models, err := parseModels(endpoint.Kind, body)
	if err != nil {
		result.Error = "parse_failed"
		return result
	}
	result.Models = models
	return result
}

func parseModels(kind string, body []byte) ([]ModelInfo, error) {
	switch kind {
	case "ollama_tags", "ollama_ps":
		var parsed struct {
			Models []struct {
				Name  string `json:"name"`
				Model string `json:"model"`
			} `json:"models"`
		}
		if err := json.Unmarshal(body, &parsed); err != nil {
			return nil, err
		}
		ids := make([]string, 0, len(parsed.Models))
		for _, model := range parsed.Models {
			id := strings.TrimSpace(model.Name)
			if id == "" {
				id = strings.TrimSpace(model.Model)
			}
			if id != "" {
				ids = append(ids, id)
			}
		}
		return modelInfos(ids), nil
	case "openai_models":
		var parsed struct {
			Data []struct {
				ID string `json:"id"`
			} `json:"data"`
		}
		if err := json.Unmarshal(body, &parsed); err != nil {
			return nil, err
		}
		ids := make([]string, 0, len(parsed.Data))
		for _, model := range parsed.Data {
			id := strings.TrimSpace(model.ID)
			if id != "" {
				ids = append(ids, id)
			}
		}
		return modelInfos(ids), nil
	default:
		return nil, fmt.Errorf("unsupported_runtime_kind:%s", kind)
	}
}

func inspectExposure(rawURL string, body []byte) RuntimeExposure {
	exposure := RuntimeExposure{LoopbackURL: isLoopbackURL(rawURL)}
	var decoded any
	if err := json.Unmarshal(body, &decoded); err != nil {
		return exposure
	}
	walkExposure(decoded, &exposure)
	return exposure
}

func walkExposure(value any, exposure *RuntimeExposure) {
	switch v := value.(type) {
	case map[string]any:
		for key, child := range v {
			normalized := strings.ToLower(key)
			switch normalized {
			case "remote_host", "remotehost", "remote_url", "remoteurl":
				if host, ok := child.(string); ok {
					exposure.RemoteHostObserved = true
					exposure.RemoteHostClass = classifyHostValue(host)
				}
			case "cloud", "cloud_offload", "cloud_offload_enabled", "ollama_cloud":
				if enabled, ok := child.(bool); ok {
					exposure.CloudOffloadObserved = true
					exposure.CloudOffloadEnabled = enabled
				}
			case "auth", "auth_required", "authentication", "api_key_required":
				exposure.AuthObserved = true
			case "telemetry", "usage_stats", "analytics":
				exposure.TelemetryObserved = true
			case "license", "licenses", "license_url":
				exposure.LicenseObserved = true
			}
			walkExposure(child, exposure)
		}
	case []any:
		for _, child := range v {
			walkExposure(child, exposure)
		}
	}
}

func modelInfos(ids []string) []ModelInfo {
	sort.Strings(ids)
	out := make([]ModelInfo, 0, len(ids))
	var last string
	for _, id := range ids {
		if id == last {
			continue
		}
		out = append(out, ModelInfo{ID: id})
		last = id
	}
	return out
}

func collectBinaries(names []string, lookup func(string) (string, error)) []BinaryPresence {
	out := make([]BinaryPresence, 0, len(names))
	for _, name := range names {
		path, err := lookup(name)
		out = append(out, BinaryPresence{
			Name:    name,
			Present: err == nil && path != "",
			Path:    path,
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

func collectEnvironment(names []string, lookup func(string) (string, bool)) []EnvironmentFact {
	out := make([]EnvironmentFact, 0, len(names))
	for _, name := range names {
		value, ok := lookup(name)
		out = append(out, EnvironmentFact{
			Name:       name,
			Present:    ok,
			ValueClass: classifyEnvValue(name, value, ok),
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

func summarize(runtimes []RuntimeResult, rejectedCount int) InventorySummary {
	summary := InventorySummary{
		RuntimeCount:  len(runtimes),
		RejectedCount: rejectedCount,
	}
	for _, runtime := range runtimes {
		if runtime.Reachable {
			summary.ReachableCount++
		}
		summary.ModelCount += len(runtime.Models)
	}
	return summary
}

func rejectedInventory(spec receipt.BuildSpec, opts InventoryOptions, rejections []RuntimeRejection, reason string) (receipt.Receipt, error) {
	payload := InventoryPayload{
		InventorySchema: InventorySchema,
		ProbePolicy:     probePolicy(opts.TimeoutMS),
		Host:            hostInfo(),
		Binaries:        []BinaryPresence{},
		Environment:     []EnvironmentFact{},
		Runtimes:        []RuntimeResult{},
		Summary:         summarize(nil, len(rejections)),
		Rejections:      rejections,
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

func localTrustEnvelope() *receipt.TrustEnvelope {
	return &receipt.TrustEnvelope{
		OriginAttestation:      "local_unsigned_probe",
		CorroborationCount:     1,
		FreshnessWindow:        "run_scoped",
		LicenseCompatibility:   "unknown",
		HallucinationRiskClass: "raw_data",
		RoutingClass:           "review",
		HumanReviewRequired:    true,
	}
}

func probePolicy(timeoutMS int) ProbePolicy {
	allowed := append([]string(nil), allowedLoopbackHosts...)
	return ProbePolicy{
		LoopbackOnly:    true,
		TimeoutMS:       timeoutMS,
		ExternalNetwork: false,
		AllowedHosts:    allowed,
	}
}

func hostInfo() HostInfo {
	return HostInfo{
		GOOS:   runtime.GOOS,
		GOARCH: runtime.GOARCH,
	}
}

func classifyProbeError(err error) string {
	if err == nil {
		return ""
	}
	if strings.Contains(err.Error(), "Client.Timeout") || strings.Contains(err.Error(), "context deadline exceeded") {
		return "timeout"
	}
	return "request_failed"
}

func isLoopbackURL(raw string) bool {
	parsed, err := url.Parse(raw)
	if err != nil {
		return false
	}
	host := parsed.Hostname()
	return host == "127.0.0.1" || host == "localhost" || host == "::1"
}

func classifyHostValue(raw string) string {
	value := strings.TrimSpace(raw)
	if value == "" {
		return "empty"
	}
	parsed, err := url.Parse(value)
	if err == nil && parsed.Hostname() != "" {
		if parsed.Hostname() == "127.0.0.1" || parsed.Hostname() == "localhost" || parsed.Hostname() == "::1" {
			return "loopback"
		}
		return "non_loopback"
	}
	if host, _, err := net.SplitHostPort(value); err == nil {
		if host == "127.0.0.1" || host == "localhost" || host == "::1" {
			return "loopback"
		}
		return "non_loopback"
	}
	if value == "127.0.0.1" || value == "localhost" || value == "::1" {
		return "loopback"
	}
	return "set_redacted"
}

func classifyEnvValue(name, value string, present bool) string {
	if !present {
		return "unset"
	}
	if value == "" {
		return "empty"
	}
	upperName := strings.ToUpper(name)
	if strings.Contains(upperName, "KEY") || strings.Contains(upperName, "TOKEN") || strings.Contains(upperName, "SECRET") {
		return "secret_present_redacted"
	}
	lowerValue := strings.ToLower(strings.TrimSpace(value))
	if lowerValue == "true" || lowerValue == "false" || lowerValue == "1" || lowerValue == "0" {
		return "boolean"
	}
	return classifyHostValue(value)
}

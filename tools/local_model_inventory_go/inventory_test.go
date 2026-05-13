package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

const (
	testCorrelationID = "corr_v0_local_model_inventory"
	testObservedAt    = "2026-05-10T00:00:00Z"
)

func fixtureBytes(t *testing.T, name string) []byte {
	t.Helper()
	path := filepath.Join("..", "..", "tests", "fixtures", "local_model_inventory_go", name)
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read fixture %s: %v", name, err)
	}
	return raw
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return f(req)
}

func fixtureClient(t *testing.T, fixtures map[string]string) *http.Client {
	t.Helper()
	bodies := make(map[string][]byte, len(fixtures))
	for rawURL, fixtureName := range fixtures {
		bodies[rawURL] = fixtureBytes(t, fixtureName)
	}
	return &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		body, ok := bodies[req.URL.String()]
		if !ok {
			return nil, errors.New("connection refused")
		}
		return &http.Response{
			StatusCode: http.StatusOK,
			Header:     make(http.Header),
			Body:       ioNopCloser{bytes.NewReader(body)},
			Request:    req,
		}, nil
	})}
}

type ioNopCloser struct {
	*bytes.Reader
}

func (c ioNopCloser) Close() error {
	return nil
}

func fakeLookup(name string) (string, error) {
	if name == "ollama" {
		return "/usr/local/bin/ollama", nil
	}
	return "", errors.New("not found")
}

func fakeEnv(name string) (string, bool) {
	switch name {
	case "OLLAMA_HOST":
		return "127.0.0.1:11434", true
	case "OPENAI_API_KEY":
		return "present-redacted-placeholder", true
	default:
		return "", false
	}
}

func testOptions(endpoints []RuntimeEndpoint) InventoryOptions {
	return InventoryOptions{
		CorrelationID: testCorrelationID,
		ObservedAt:    testObservedAt,
		TimeoutMS:     250,
		Endpoints:     endpoints,
		BinaryNames:   []string{"ollama", "vllm"},
		LookupPath:    fakeLookup,
		EnvNames:      []string{"OLLAMA_HOST", "OPENAI_API_KEY"},
		LookupEnv:     fakeEnv,
	}
}

func decodePayload(t *testing.T, r receipt.Receipt) InventoryPayload {
	t.Helper()
	var payload InventoryPayload
	if err := json.Unmarshal(r.Payload, &payload); err != nil {
		t.Fatalf("decode payload: %v", err)
	}
	return payload
}

func TestBuildInventoryReceiptAcceptsLoopbackFixtures(t *testing.T) {
	ollamaURL := "http://127.0.0.1:11434/api/tags"
	openaiURL := "http://127.0.0.1:8000/v1/models"
	opts := testOptions([]RuntimeEndpoint{
		{Name: "ollama", Kind: "ollama_tags", URL: ollamaURL},
		{Name: "vllm_openai", Kind: "openai_models", URL: openaiURL},
	})
	opts.HTTPClient = fixtureClient(t, map[string]string{
		ollamaURL: "ollama_tags.json",
		openaiURL: "openai_models.json",
	})

	r, err := BuildInventoryReceipt(opts)
	if err != nil {
		t.Fatalf("BuildInventoryReceipt returned error: %v", err)
	}
	if r.Status != receipt.StatusAccepted {
		t.Fatalf("status = %q, want accepted", r.Status)
	}
	if r.Source != SourceName || r.SourceURL != SourceURL {
		t.Fatalf("unexpected source identity: %s %s", r.Source, r.SourceURL)
	}

	payload := decodePayload(t, r)
	if payload.InventorySchema != InventorySchema {
		t.Fatalf("inventory_schema = %q", payload.InventorySchema)
	}
	if !payload.ProbePolicy.LoopbackOnly || payload.ProbePolicy.ExternalNetwork {
		t.Fatalf("unexpected probe policy: %+v", payload.ProbePolicy)
	}
	if payload.Summary.RuntimeCount != 2 || payload.Summary.ReachableCount != 2 || payload.Summary.ModelCount != 4 {
		t.Fatalf("unexpected summary: %+v", payload.Summary)
	}
	if payload.Summary.RejectedCount != 0 {
		t.Fatalf("rejected_count = %d, want 0", payload.Summary.RejectedCount)
	}
	if len(payload.Binaries) != 2 || payload.Binaries[0].Name != "ollama" || !payload.Binaries[0].Present {
		t.Fatalf("unexpected binary presence: %+v", payload.Binaries)
	}
	if len(payload.Environment) != 2 || payload.Environment[0].Name != "OLLAMA_HOST" || payload.Environment[0].ValueClass != "loopback" {
		t.Fatalf("unexpected environment facts: %+v", payload.Environment)
	}
	if payload.Environment[1].ValueClass != "secret_present_redacted" {
		t.Fatalf("secret env value was not redacted: %+v", payload.Environment[1])
	}
	if r.TrustEnvelope == nil || r.TrustEnvelope.RoutingClass != "review" {
		t.Fatalf("missing trust envelope: %+v", r.TrustEnvelope)
	}
	if r.ContentHash != receipt.ContentHash(r.Payload) {
		t.Fatalf("content_hash = %s, want hash of payload", r.ContentHash)
	}
}

func TestUnreachableLoopbackEndpointIsRecordedNotRejected(t *testing.T) {
	unreachableURL := "http://127.0.0.1:65534/v1/models"
	opts := testOptions([]RuntimeEndpoint{
		{Name: "llama_cpp", Kind: "openai_models", URL: unreachableURL},
	})
	opts.HTTPClient = fixtureClient(t, nil)

	r, err := BuildInventoryReceipt(opts)
	if err != nil {
		t.Fatalf("unreachable localhost should not reject run: %v", err)
	}
	payload := decodePayload(t, r)
	if payload.Summary.RuntimeCount != 1 || payload.Summary.ReachableCount != 0 || payload.Summary.ModelCount != 0 {
		t.Fatalf("unexpected summary: %+v", payload.Summary)
	}
	got := payload.Runtimes[0]
	if got.Reachable {
		t.Fatalf("unreachable endpoint marked reachable: %+v", got)
	}
	if got.Error == "" {
		t.Fatalf("unreachable endpoint must record an error fact: %+v", got)
	}
}

func TestNonLoopbackEndpointRejectedBeforeHTTP(t *testing.T) {
	r, err := BuildInventoryReceipt(testOptions([]RuntimeEndpoint{
		{Name: "bad", Kind: "openai_models", URL: "http://192.0.2.10:8000/v1/models"},
	}))
	if err == nil {
		t.Fatal("expected RejectError for non-loopback endpoint")
	}
	var rejectErr RejectError
	if !errors.As(err, &rejectErr) {
		t.Fatalf("expected RejectError, got %T: %v", err, err)
	}
	if !strings.HasPrefix(rejectErr.Reason, "non_loopback_url:") {
		t.Fatalf("reason = %q, want non_loopback_url prefix", rejectErr.Reason)
	}
	if r.Status != receipt.StatusRejected || r.RejectedReason != rejectErr.Reason {
		t.Fatalf("unexpected rejected receipt: %+v", r)
	}
	payload := decodePayload(t, r)
	if payload.Summary.RejectedCount != 1 {
		t.Fatalf("rejected_count = %d, want 1", payload.Summary.RejectedCount)
	}
}

func TestInventoryReceiptIdentityIsDeterministic(t *testing.T) {
	ollamaURL := "http://127.0.0.1:11434/api/tags"
	opts := testOptions([]RuntimeEndpoint{
		{Name: "ollama", Kind: "ollama_tags", URL: ollamaURL},
	})
	opts.HTTPClient = fixtureClient(t, map[string]string{
		ollamaURL: "ollama_tags.json",
	})

	first, err := BuildInventoryReceipt(opts)
	if err != nil {
		t.Fatal(err)
	}
	second, err := BuildInventoryReceipt(opts)
	if err != nil {
		t.Fatal(err)
	}
	if first.ContentHash != second.ContentHash || first.EventUID != second.EventUID || first.ReceiptID != second.ReceiptID {
		t.Fatalf("receipt identity drifted: first=%+v second=%+v", first, second)
	}
	if !reflect.DeepEqual(first, second) {
		t.Fatalf("receipts must be deterministic: first=%+v second=%+v", first, second)
	}
}

func TestOpenAICompatibleModelListParser(t *testing.T) {
	models, err := parseModels("openai_models", fixtureBytes(t, "openai_models.json"))
	if err != nil {
		t.Fatal(err)
	}
	got := []string{models[0].ID, models[1].ID}
	want := []string{"qwen2.5-coder-7b", "text-embedding-nomic"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("models = %v, want %v", got, want)
	}
}

func TestOllamaModelListParser(t *testing.T) {
	models, err := parseModels("ollama_tags", fixtureBytes(t, "ollama_tags.json"))
	if err != nil {
		t.Fatal(err)
	}
	got := []string{models[0].ID, models[1].ID}
	want := []string{"llama3.2:latest", "mistral:latest"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("models = %v, want %v", got, want)
	}
}

func TestExposureInspectorClassifiesRemoteAndCloudSignals(t *testing.T) {
	exposure := inspectExposure("http://127.0.0.1:11434/api/tags", []byte(`{
		"models": [
			{
				"name": "remote-model",
				"remote_host": "https://inference.example.com",
				"cloud_offload_enabled": true,
				"telemetry": {"enabled": true},
				"license": "review-required"
			}
		]
	}`))
	if !exposure.LoopbackURL {
		t.Fatal("expected loopback URL exposure marker")
	}
	if !exposure.RemoteHostObserved || exposure.RemoteHostClass != "non_loopback" {
		t.Fatalf("remote host not classified: %+v", exposure)
	}
	if !exposure.CloudOffloadObserved || !exposure.CloudOffloadEnabled {
		t.Fatalf("cloud offload not observed: %+v", exposure)
	}
	if !exposure.TelemetryObserved || !exposure.LicenseObserved {
		t.Fatalf("telemetry/license not observed: %+v", exposure)
	}
}

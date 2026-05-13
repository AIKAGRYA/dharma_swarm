package sourceprobe

import (
	"bytes"
	"encoding/json"
	"errors"
	"net/http"
	"reflect"
	"strings"
	"testing"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

const (
	testSourceName = "test_source_probe_go"
	testSourceURL  = "local://test-source-probe"
	testSchema     = "test_source_probe.v0"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return f(req)
}

type ioNopCloser struct {
	*bytes.Reader
}

func (c ioNopCloser) Close() error {
	return nil
}

func testSources() []SourceDefinition {
	return []SourceDefinition{
		{
			ID:                     "cisa_kev",
			Title:                  "CISA Known Exploited Vulnerabilities",
			URL:                    "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
			Kind:                   "json_feed",
			Publisher:              "CISA",
			TopicTags:              []string{"security", "kev"},
			LicenseCompatibility:   "public_domain_or_open_government_data",
			FreshnessWindow:        "24h",
			OriginAttestation:      "unsigned",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			HumanReviewRequired:    true,
		},
	}
}

func testTrust() *receipt.TrustEnvelope {
	return &receipt.TrustEnvelope{
		OriginAttestation:      "unsigned",
		CorroborationCount:     1,
		FreshnessWindow:        "24h",
		LicenseCompatibility:   "mixed_review_required",
		HallucinationRiskClass: "raw_data",
		RoutingClass:           "review",
		HumanReviewRequired:    true,
	}
}

func TestBuildAggregateReceiptFetchesAndHashesBoundedBody(t *testing.T) {
	client := &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		if req.URL.Hostname() != "www.cisa.gov" {
			return nil, errors.New("unexpected host")
		}
		return &http.Response{
			StatusCode: http.StatusOK,
			Header:     http.Header{"Content-Type": []string{"application/json"}},
			Body:       ioNopCloser{bytes.NewReader([]byte(`{"vulnerabilities":[]}`))},
			Request:    req,
		}, nil
	})}

	r, err := BuildAggregateReceipt(testSourceName, testSourceURL, testSchema, testTrust(), Options{
		CorrelationID: "corr_source_probe_test",
		ObservedAt:    "2026-05-10T00:00:00Z",
		TimeoutMS:     250,
		MaxBodyBytes:  4096,
		Fetch:         true,
		Sources:       testSources(),
		HTTPClient:    client,
	})
	if err != nil {
		t.Fatal(err)
	}
	if r.Status != receipt.StatusAccepted {
		t.Fatalf("status = %s, want accepted", r.Status)
	}
	if r.TrustEnvelope == nil || r.TrustEnvelope.RoutingClass != "review" {
		t.Fatalf("trust envelope missing: %+v", r.TrustEnvelope)
	}
	var payload AggregatePayload
	if err := jsonUnmarshal(r.Payload, &payload); err != nil {
		t.Fatal(err)
	}
	if payload.Summary.SourceCount != 1 || payload.Summary.FetchedCount != 1 || payload.Summary.ReachableCount != 1 {
		t.Fatalf("unexpected summary: %+v", payload.Summary)
	}
	got := payload.Sources[0]
	if got.BodySHA256 != receipt.ContentHash([]byte(`{"vulnerabilities":[]}`)) {
		t.Fatalf("body hash = %s", got.BodySHA256)
	}
	if got.ContentType != "application/json" || got.BodyBytes == 0 {
		t.Fatalf("fetch metadata missing: %+v", got)
	}
}

func TestUnreachableSourceIsFactNotRejection(t *testing.T) {
	client := &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		return nil, errors.New("connection refused")
	})}
	r, err := BuildAggregateReceipt(testSourceName, testSourceURL, testSchema, testTrust(), Options{
		CorrelationID: "corr_source_probe_unreachable",
		ObservedAt:    "2026-05-10T00:00:00Z",
		Fetch:         true,
		Sources:       testSources(),
		HTTPClient:    client,
	})
	if err != nil {
		t.Fatalf("unreachable source should not reject: %v", err)
	}
	var payload AggregatePayload
	if err := jsonUnmarshal(r.Payload, &payload); err != nil {
		t.Fatal(err)
	}
	if payload.Summary.ReachableCount != 0 || payload.Sources[0].Error == "" {
		t.Fatalf("unreachable source not recorded: %+v", payload)
	}
}

func TestInvalidSourceURLRejectsBeforeHTTP(t *testing.T) {
	sources := testSources()
	sources[0].URL = "http://example.com/plain-http"
	r, err := BuildAggregateReceipt(testSourceName, testSourceURL, testSchema, testTrust(), Options{
		CorrelationID: "corr_source_probe_rejected",
		ObservedAt:    "2026-05-10T00:00:00Z",
		Fetch:         true,
		Sources:       sources,
	})
	if err == nil {
		t.Fatal("expected rejection for insecure external HTTP")
	}
	var rejectErr RejectError
	if !errors.As(err, &rejectErr) {
		t.Fatalf("expected RejectError, got %T", err)
	}
	if !strings.HasPrefix(rejectErr.Reason, "insecure_external_http:") {
		t.Fatalf("reason = %q", rejectErr.Reason)
	}
	if r.Status != receipt.StatusRejected {
		t.Fatalf("status = %s, want rejected", r.Status)
	}
}

func TestAggregateReceiptDeterministicWithoutFetch(t *testing.T) {
	opts := Options{
		CorrelationID: "corr_source_probe_deterministic",
		ObservedAt:    "2026-05-10T00:00:00Z",
		Sources:       testSources(),
	}
	first, err := BuildAggregateReceipt(testSourceName, testSourceURL, testSchema, testTrust(), opts)
	if err != nil {
		t.Fatal(err)
	}
	second, err := BuildAggregateReceipt(testSourceName, testSourceURL, testSchema, testTrust(), opts)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(first, second) {
		t.Fatalf("receipts drifted:\n%+v\n%+v", first, second)
	}
}

func jsonUnmarshal(raw []byte, out any) error {
	return json.Unmarshal(raw, out)
}

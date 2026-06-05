package main

import (
	"context"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"
)

func TestParseHNEmitsItems(t *testing.T) {
	rows := parseHN(Source{Name: "hn", Kind: "hn_algolia"}, []byte(`{"hits":[{"objectID":"1","title":"Agent runtime","url":"https://example.com"}]}`))
	if len(rows) != 1 || rows[0].URL == "" || rows[0].SourceType != "hn_algolia" {
		t.Fatalf("unexpected rows: %+v", rows)
	}
}

func TestParseGitHubReposEmitsItems(t *testing.T) {
	rows := parseGitHubRepos(Source{Name: "gh", Kind: "github_repos"}, []byte(`{"items":[{"id":7,"full_name":"org/agent","description":"agent runtime","html_url":"https://github.com/org/agent","stargazers_count":12}]}`))
	if len(rows) != 1 || rows[0].Title != "org/agent" {
		t.Fatalf("unexpected rows: %+v", rows)
	}
}

func TestObservationFromText(t *testing.T) {
	obs, ok := observationFromText(Source{Name: "test", URL: "https://example.com", Kind: "html"}, "<p>Agentic AI benchmark release</p>")
	if !ok || obs.ID == "" || len(obs.Keywords) == 0 {
		t.Fatalf("unexpected observation: %+v", obs)
	}
}

func TestFetchSourcesRetriesRetryAfter429(t *testing.T) {
	attempts := 0
	client := &http.Client{Transport: scoutRoundTripFunc(func(req *http.Request) (*http.Response, error) {
		attempts++
		if attempts == 1 {
			return scoutTextResponse(http.StatusTooManyRequests, "slow down", map[string]string{"Retry-After": "0"}), nil
		}
		return scoutTextResponse(http.StatusOK, "Agentic AI benchmark release", nil), nil
	})}

	observations, result, err := fetchSourcesWithClient(
		context.Background(),
		[]Source{{Name: "retry", URL: "https://retry.test", Kind: "html"}},
		client,
	)
	if err != nil {
		t.Fatal(err)
	}
	if attempts != 2 {
		t.Fatalf("expected one retry, got %d attempts", attempts)
	}
	if result.SuccessfulSources != 1 || result.FailedSources != 0 || result.RetryCount != 1 || len(observations) != 1 {
		t.Fatalf("unexpected result: observations=%+v result=%+v", observations, result)
	}
}

func TestFetchSourcesKeepsPartialSuccess(t *testing.T) {
	client := &http.Client{Transport: scoutRoundTripFunc(func(req *http.Request) (*http.Response, error) {
		if strings.Contains(req.URL.Host, "bad") {
			return scoutTextResponse(http.StatusBadRequest, "bad request", nil), nil
		}
		return scoutTextResponse(http.StatusOK, "Agentic AI benchmark release", nil), nil
	})}

	observations, result, err := fetchSourcesWithClient(
		context.Background(),
		[]Source{
			{Name: "bad", URL: "https://bad.test", Kind: "html"},
			{Name: "good", URL: "https://good.test", Kind: "html"},
		},
		client,
	)
	if err != nil {
		t.Fatal(err)
	}
	if result.SuccessfulSources != 1 || result.FailedSources != 1 || len(observations) != 1 {
		t.Fatalf("partial success not preserved: observations=%+v result=%+v", observations, result)
	}
}

func TestFetchSourcesHonorsContextCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	client := &http.Client{Transport: scoutRoundTripFunc(func(req *http.Request) (*http.Response, error) {
		t.Fatal("request should not execute after context cancellation")
		return nil, nil
	})}

	observations, result, err := fetchSourcesWithClient(
		ctx,
		[]Source{{Name: "cancelled", URL: "https://cancel.test", Kind: "html"}},
		client,
	)
	if err == nil || len(observations) != 0 || result.FailedSources != 1 {
		t.Fatalf("expected cancellation failure, observations=%+v result=%+v err=%v", observations, result, err)
	}
}

type scoutRoundTripFunc func(*http.Request) (*http.Response, error)

func (fn scoutRoundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return fn(req)
}

func scoutTextResponse(status int, body string, headers map[string]string) *http.Response {
	resp := &http.Response{
		StatusCode: status,
		Body:       io.NopCloser(strings.NewReader(body)),
		Header:     http.Header{},
	}
	for key, value := range headers {
		resp.Header.Set(key, value)
	}
	return resp
}

func TestScoutRetryDelayParsesRetryAfter(t *testing.T) {
	if delay := scoutRetryDelay("0", 1); delay != 0 {
		t.Fatalf("Retry-After seconds parsed incorrectly: %s", delay)
	}
	future := time.Now().Add(50 * time.Millisecond).UTC().Format(http.TimeFormat)
	if delay := scoutRetryDelay(future, 1); delay < 0 {
		t.Fatalf("Retry-After date parsed incorrectly: %s", delay)
	}
}

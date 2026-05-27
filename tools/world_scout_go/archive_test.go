package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (fn roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return fn(req)
}

func TestSourcesForURLsCreatesDirectSources(t *testing.T) {
	sources := SourcesForURLs([]string{" https://docs.example.com/llms-full.txt ", "https://docs.example.com/llms-full.txt"}, "mv1")
	if len(sources) != 1 {
		t.Fatalf("expected deduped source, got %d", len(sources))
	}
	if sources[0].Kind != "llms_txt" || sources[0].CascadeFor != "mv1" {
		t.Fatalf("unexpected direct source: %+v", sources[0])
	}
}

func TestFetchArchiveEntryWritesBodyAndReceipt(t *testing.T) {
	client := &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		body := `<html><head><title>Cofounder Fixture</title></head><body><a href="/llms.txt">LLMS</a></body></html>`
		return &http.Response{
			StatusCode: 200,
			Header:     http.Header{"Content-Type": []string{"text/html; charset=utf-8"}},
			Body:       io.NopCloser(strings.NewReader(body)),
			Request:    req,
		}, nil
	})}
	archiveDir := filepath.Join(t.TempDir(), "archive")
	opts := normalizeArchiveOptions(ArchiveOptions{
		MaxBytes:       100_000,
		Correlation:    "test_archive",
		RobotsDisabled: true,
	}, 1)
	policy := newArchiveHTTPClient(client, opts, map[string]bool{"cofounder.test": true})
	entry := fetchArchiveEntry(policy, "https://cofounder.test/", archiveDir, opts, 0)
	if len(entry.Errors) != 0 {
		t.Fatalf("unexpected errors: %+v", entry.Errors)
	}
	if entry.Title != "Cofounder Fixture" || entry.BodyPath == "" || entry.ReceiptPath == "" {
		t.Fatalf("unexpected archive entry: %+v", entry)
	}
	if len(entry.Links) != 1 || entry.Links[0] != "https://cofounder.test/llms.txt" {
		t.Fatalf("unexpected links: %+v", entry.Links)
	}
	body, err := os.ReadFile(entry.BodyPath)
	if err != nil || !strings.Contains(string(body), "Cofounder Fixture") {
		t.Fatalf("body not written correctly: %v", err)
	}
	receipt, err := os.ReadFile(entry.ReceiptPath)
	if err != nil || !strings.Contains(string(receipt), "go_site_archive_receipt.v1") {
		t.Fatalf("receipt not written correctly: %v", err)
	}
	indexPath := filepath.Join(archiveDir, "archive_index.jsonl")
	if err := writeArchiveIndex(indexPath, []ArchiveEntry{entry}); err != nil {
		t.Fatal(err)
	}
	indexRows := readArchiveIndexForTest(t, indexPath)
	if len(indexRows) != 1 || indexRows[0].ContentHash != entry.ContentHash {
		t.Fatalf("unexpected index rows: %+v", indexRows)
	}
}

func readArchiveIndexForTest(t *testing.T, path string) []ArchiveEntry {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	entries := []ArchiveEntry{}
	for _, line := range strings.Split(string(data), "\n") {
		if strings.TrimSpace(line) == "" {
			continue
		}
		var entry ArchiveEntry
		if err := json.Unmarshal([]byte(line), &entry); err != nil {
			t.Fatal(err)
		}
		entries = append(entries, entry)
	}
	return entries
}

func TestURLsFromFilesReadsSeedsAndIgnoresComments(t *testing.T) {
	seedFile := filepath.Join(t.TempDir(), "urls.txt")
	if err := os.WriteFile(seedFile, []byte("# comment\nhttps://cofounder.test/\n\nhttps://docs.cofounder.test/llms.txt\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	urls, err := URLsFromFiles([]string{seedFile})
	if err != nil {
		t.Fatal(err)
	}
	if len(urls) != 2 || urls[0] != "https://cofounder.test/" || urls[1] != "https://docs.cofounder.test/llms.txt" {
		t.Fatalf("unexpected urls: %+v", urls)
	}
}

func TestDiscoverArchiveURLsAddsLLMSAndSitemapURLs(t *testing.T) {
	client := &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		switch req.URL.Path {
		case "/robots.txt":
			return textResponse(req, "Sitemap: https://cofounder.test/sitemap.xml\n"), nil
		case "/sitemap.xml":
			return textResponse(req, "<urlset><url><loc>https://cofounder.test/docs/a</loc></url><url><loc>https://cofounder.test/docs/b</loc></url></urlset>"), nil
		default:
			return textResponse(req, ""), nil
		}
	})}
	sources := []Source{{Name: "cofounder", URL: "https://cofounder.test/start", Kind: "html"}}
	opts := normalizeArchiveOptions(ArchiveOptions{
		SameDomain:      true,
		DiscoverLLMS:    true,
		DiscoverSitemap: true,
		SitemapMaxURLs:  10,
		RobotsDisabled:  true,
	}, len(sources))
	policy := newArchiveHTTPClient(client, opts, archiveSeedHosts(sources))
	urls, _, errors := discoverArchiveURLs(policy, sources, opts)
	if len(errors) != 0 {
		t.Fatalf("unexpected errors: %+v", errors)
	}
	joined := strings.Join(urls, "\n")
	for _, expected := range []string{
		"https://cofounder.test/llms.txt",
		"https://cofounder.test/llms-full.txt",
		"https://cofounder.test/docs/a",
		"https://cofounder.test/docs/b",
	} {
		if !strings.Contains(joined, expected) {
			t.Fatalf("missing %s in %+v", expected, urls)
		}
	}
}

func TestWriteArchiveManifestRecordsRunShape(t *testing.T) {
	manifestPath := filepath.Join(t.TempDir(), "manifest.json")
	result := ArchiveResult{
		ArchiveDir:      "/tmp/archive",
		IndexPath:       "/tmp/archive/archive_index.jsonl",
		ArchiveCount:    3,
		DedupeCount:     1,
		DiscoveredCount: 2,
		WorkerCount:     4,
		TotalBytes:      99,
	}
	if err := writeArchiveManifest(manifestPath, result, []Source{{Name: "a", URL: "https://a.test", Kind: "html"}}, ArchiveOptions{Workers: 4, MaxPages: 5}, time.Now().UTC()); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(manifestPath)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(data), "world_scout_archive_manifest.v1") || !strings.Contains(string(data), "\"worker_count\": 4") {
		t.Fatalf("manifest missing expected content: %s", string(data))
	}
}

func TestNormalizeArchiveOptionsBoundsWorkers(t *testing.T) {
	opts := normalizeArchiveOptions(ArchiveOptions{Workers: 100, MaxPages: 3}, 10)
	if opts.Workers != 3 {
		t.Fatalf("expected workers bounded to max pages, got %d", opts.Workers)
	}
	opts = normalizeArchiveOptions(ArchiveOptions{}, 0)
	if opts.Workers != 1 || opts.MaxPages != 1 || opts.SitemapMaxURLs != 100 {
		t.Fatalf("unexpected normalized defaults: %+v", opts)
	}
}

func textResponse(req *http.Request, body string) *http.Response {
	return &http.Response{
		StatusCode: 200,
		Header:     http.Header{"Content-Type": []string{"text/plain"}},
		Body:       io.NopCloser(strings.NewReader(body)),
		Request:    req,
	}
}

func TestCanonicalURLNormalizesArchiveIdentity(t *testing.T) {
	cases := map[string]string{
		"HTTPS://Example.COM:443/a?b=2&a=1&utm_source=x#frag":  "https://example.com/a?a=1&b=2",
		"http://Example.COM:80":                                "http://example.com/",
		"https://example.com:8443/path":                        "https://example.com:8443/path",
		"https://example.com/docs/":                            "https://example.com/docs/",
		"https://example.com/search?sort=new&q=agent&fbclid=x": "https://example.com/search?q=agent&sort=new",
		"ftp://example.com/file":                               "",
	}
	for raw, expected := range cases {
		if got := canonicalURL(raw); got != expected {
			t.Fatalf("canonicalURL(%q) = %q, want %q", raw, got, expected)
		}
	}
}

func TestRobotsParserSupportsAllowDisallowWildcardAndAnchor(t *testing.T) {
	policy := parseRobots(`
User-agent: *
Disallow: /private*
Allow: /private/public$
Crawl-delay: 0.01
Sitemap: https://example.test/sitemap.xml
`, "https://example.test", archiveUserAgent)
	if len(policy.Sitemaps) != 1 || policy.CrawlDelayMS != 10 {
		t.Fatalf("unexpected robots metadata: %+v", policy)
	}
	if allowed, _ := policy.allowed("https://example.test/private/secret"); allowed {
		t.Fatal("expected private URL blocked")
	}
	if allowed, _ := policy.allowed("https://example.test/private/public"); !allowed {
		t.Fatal("expected anchored allow to win")
	}
}

func TestResolveRunSourcesDoesNotScoutExplicitArchiveURLs(t *testing.T) {
	scoutSources, archiveSources, errors := resolveRunSources(t.TempDir(), nil, "mv1", []string{"https://docs.example.test/a"}, nil, true)
	if len(errors) != 0 {
		t.Fatalf("unexpected errors: %+v", errors)
	}
	if len(scoutSources) != 0 {
		t.Fatalf("explicit archive URL seeds must bypass legacy scout fetch, got %+v", scoutSources)
	}
	if len(archiveSources) != 1 || archiveSources[0].URL != "https://docs.example.test/a" {
		t.Fatalf("expected direct archive source, got %+v", archiveSources)
	}

	scoutSources, _, errors = resolveRunSources(t.TempDir(), []string{"agent tools"}, "mv1", []string{"https://docs.example.test/a"}, nil, true)
	if len(errors) != 0 {
		t.Fatalf("unexpected query errors: %+v", errors)
	}
	for _, source := range scoutSources {
		if source.URL == "https://docs.example.test/a" {
			t.Fatalf("direct archive URL leaked into scout sources: %+v", scoutSources)
		}
	}
	if len(scoutSources) == 0 {
		t.Fatal("expected query sources to remain eligible for legacy scout fetch")
	}
}

func TestArchiveRedirectTargetBlockedByRobotsIsNotFetched(t *testing.T) {
	blockedFetches := 0
	client := &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		switch req.URL.Path {
		case "/robots.txt":
			return textResponse(req, "User-agent: *\nDisallow: /blocked\n"), nil
		case "/allowed":
			return &http.Response{
				StatusCode: http.StatusFound,
				Header:     http.Header{"Location": []string{"https://redirect-robots.test/blocked"}},
				Body:       io.NopCloser(strings.NewReader("redirect")),
				Request:    req,
			}, nil
		case "/blocked":
			blockedFetches++
			return textResponse(req, "blocked"), nil
		default:
			return &http.Response{StatusCode: http.StatusNotFound, Body: io.NopCloser(strings.NewReader("missing")), Request: req}, nil
		}
	})}
	result := archiveSourcesWithHTTPClient([]Source{{Name: "redirect", URL: "https://redirect-robots.test/allowed", Kind: "html"}}, ArchiveOptions{
		ArchiveDir: filepath.Join(t.TempDir(), "archive"),
		MaxPages:   1,
		Workers:    1,
	}, client)
	if len(result.Entries) != 1 {
		t.Fatalf("expected one entry, got %+v", result.Entries)
	}
	entry := result.Entries[0]
	if entry.CaptureStatus != CaptureBlockedByRobots || entry.BodyPath != "" || entry.ReceiptPath != "" {
		t.Fatalf("expected redirect target blocked by robots without files, got %+v", entry)
	}
	if entry.FinalCanonicalURL != "https://redirect-robots.test/blocked" {
		t.Fatalf("expected final blocked URL recorded, got %q", entry.FinalCanonicalURL)
	}
	if blockedFetches != 0 {
		t.Fatalf("blocked redirect target was fetched %d times", blockedFetches)
	}
}

func TestArchiveRobotsFetchIsSingleFlightPerOrigin(t *testing.T) {
	var mu sync.Mutex
	robotsFetches := 0
	client := &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		if req.URL.Path == "/robots.txt" {
			mu.Lock()
			robotsFetches++
			mu.Unlock()
			time.Sleep(20 * time.Millisecond)
			return &http.Response{StatusCode: http.StatusNotFound, Body: io.NopCloser(strings.NewReader("")), Request: req}, nil
		}
		return textResponse(req, "ok"), nil
	})}
	result := archiveSourcesWithHTTPClient([]Source{
		{Name: "a", URL: "https://singleflight.test/a", Kind: "html"},
		{Name: "b", URL: "https://singleflight.test/b", Kind: "html"},
	}, ArchiveOptions{
		ArchiveDir: filepath.Join(t.TempDir(), "archive"),
		MaxPages:   2,
		Workers:    2,
	}, client)
	if len(result.Entries) != 2 {
		t.Fatalf("expected two entries, got %+v", result.Entries)
	}
	mu.Lock()
	defer mu.Unlock()
	if robotsFetches != 1 {
		t.Fatalf("expected one robots fetch, got %d", robotsFetches)
	}
}

func TestArchiveDoesNotContentDedupeHTTPErrorRows(t *testing.T) {
	client := &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		if req.URL.Path == "/robots.txt" {
			return &http.Response{StatusCode: http.StatusNotFound, Body: io.NopCloser(strings.NewReader("")), Request: req}, nil
		}
		return &http.Response{
			StatusCode: http.StatusNotFound,
			Header:     http.Header{"Content-Type": []string{"text/plain"}},
			Body:       io.NopCloser(strings.NewReader("same missing body")),
			Request:    req,
		}, nil
	})}
	result := archiveSourcesWithHTTPClient([]Source{
		{Name: "a", URL: "https://errors.test/a", Kind: "html"},
		{Name: "b", URL: "https://errors.test/b", Kind: "html"},
	}, ArchiveOptions{
		ArchiveDir: filepath.Join(t.TempDir(), "archive"),
		MaxPages:   2,
		Workers:    2,
	}, client)
	if result.DedupeCount != 0 {
		t.Fatalf("http error rows should not content-dedupe, got %d", result.DedupeCount)
	}
	for _, entry := range result.Entries {
		if entry.CaptureStatus != CaptureHTTPError || entry.DedupeOf != "" {
			t.Fatalf("expected independent http error row, got %+v", entry)
		}
	}
}

func TestArchiveFixtureServerEndToEndEvidenceSemantics(t *testing.T) {
	client, origin := newArchiveFixtureClient(t)
	archiveDir := filepath.Join(t.TempDir(), "archive")
	result := archiveSourcesWithHTTPClient([]Source{{Name: "fixture", URL: origin + "/", Kind: "html"}}, ArchiveOptions{
		ArchiveDir:       archiveDir,
		MaxBytes:         64,
		MaxDepth:         1,
		MaxPages:         20,
		SameDomain:       true,
		RateLimitMS:      0,
		Workers:          2,
		DiscoverLLMS:     true,
		DiscoverSitemap:  true,
		SitemapMaxURLs:   20,
		MaxRetries:       1,
		RetryBaseDelayMS: 1,
		RetryMaxDelayMS:  1,
	}, client)
	if result.IndexPath == "" || result.ManifestPath == "" || result.IndexHash == "" {
		t.Fatalf("missing archive outputs: %+v", result)
	}
	if result.ReplayValidation.Status != "passed" {
		t.Fatalf("replay validation failed: %+v", result.ReplayValidation)
	}
	entries := map[string]ArchiveEntry{}
	for _, entry := range result.Entries {
		entries[entry.CanonicalURL] = entry
	}
	if _, ok := entries[origin+"/llms.txt"]; !ok {
		t.Fatalf("expected llms discovery entry in %+v", entries)
	}
	if blocked := entries[origin+"/blocked"]; blocked.CaptureStatus != CaptureBlockedByRobots || blocked.BodyPath != "" || blocked.ReceiptPath != "" {
		t.Fatalf("expected robots-blocked entry without files, got %+v", blocked)
	}
	if huge := entries[origin+"/huge"]; huge.CaptureStatus != CaptureTruncated || !huge.Truncated || huge.Bytes != 64 {
		t.Fatalf("expected truncated huge entry, got %+v", huge)
	}
	if missing := entries[origin+"/missing"]; missing.CaptureStatus != CaptureHTTPError || missing.BodyPath != "" {
		t.Fatalf("expected http error without body file, got %+v", missing)
	}
	if redirect := entries[origin+"/redirect"]; redirect.FinalCanonicalURL != origin+"/docs/final" || len(redirect.RedirectChain) == 0 {
		t.Fatalf("expected redirect final evidence, got %+v", redirect)
	}
	if off := entries[origin+"/off-redirect"]; off.CaptureStatus != CaptureSkippedPolicy || off.BodyPath != "" {
		t.Fatalf("expected off-domain redirect skipped, got %+v", off)
	}
	if result.DedupeCount == 0 {
		t.Fatalf("expected at least one content/identity dedupe, got %+v", result)
	}
	manifestData, err := os.ReadFile(result.ManifestPath)
	if err != nil {
		t.Fatal(err)
	}
	for _, expected := range []string{"archive_index_hash", "discovery_events", "replay_validation", "status_counts"} {
		if !strings.Contains(string(manifestData), expected) {
			t.Fatalf("manifest missing %s: %s", expected, string(manifestData))
		}
	}
}

func TestArchiveRetryIsBoundedAndRecorded(t *testing.T) {
	attempts := 0
	client := &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		attempts++
		if attempts == 1 {
			return &http.Response{StatusCode: 500, Header: http.Header{"Retry-After": []string{"0"}}, Body: io.NopCloser(strings.NewReader("try again")), Request: req}, nil
		}
		return &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": []string{"text/plain"}}, Body: io.NopCloser(strings.NewReader("ok")), Request: req}, nil
	})}
	opts := normalizeArchiveOptions(ArchiveOptions{MaxBytes: 100, MaxRetries: 1, RetryBaseDelayMS: 1, RetryMaxDelayMS: 1, RobotsDisabled: true}, 1)
	policy := newArchiveHTTPClient(client, opts, map[string]bool{"retry.test": true})
	entry := fetchArchiveEntry(policy, "https://retry.test/a", filepath.Join(t.TempDir(), "archive"), opts, 0)
	if entry.CaptureStatus != CaptureCaptured || entry.RetryCount != 1 || attempts != 2 {
		t.Fatalf("expected one retry then capture, attempts=%d entry=%+v", attempts, entry)
	}
}

func TestArchivePerHostLimiterSerializesConcurrentWorkers(t *testing.T) {
	var mu sync.Mutex
	var times []time.Time
	client := &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		if req.URL.Path == "/robots.txt" {
			return &http.Response{StatusCode: 404, Body: io.NopCloser(strings.NewReader("")), Request: req}, nil
		}
		mu.Lock()
		times = append(times, time.Now())
		mu.Unlock()
		return &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": []string{"text/plain"}}, Body: io.NopCloser(strings.NewReader("ok")), Request: req}, nil
	})}
	archiveSourcesWithHTTPClient([]Source{{Name: "a", URL: "https://limit.test/a", Kind: "html"}, {Name: "b", URL: "https://limit.test/b", Kind: "html"}}, ArchiveOptions{
		ArchiveDir:  filepath.Join(t.TempDir(), "archive"),
		MaxPages:    2,
		Workers:     2,
		RateLimitMS: 5,
	}, client)
	mu.Lock()
	defer mu.Unlock()
	if len(times) != 2 {
		t.Fatalf("expected two fetched pages, got %d", len(times))
	}
	if delta := times[1].Sub(times[0]); delta < 3*time.Millisecond {
		t.Fatalf("expected per-host limiter gap, got %s", delta)
	}
}

func newArchiveFixtureClient(t *testing.T) (*http.Client, string) {
	t.Helper()
	origin := "https://fixture.test"
	client := &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		body := ""
		status := 200
		header := http.Header{"Content-Type": []string{"text/html"}}
		switch req.URL.Path {
		case "/robots.txt":
			header.Set("Content-Type", "text/plain")
			body = fmt.Sprintf("User-agent: %s\nDisallow: /blocked\nCrawl-delay: 0\nSitemap: %s/sitemap.xml\n", archiveUserAgent, origin)
		case "/sitemap.xml":
			header.Set("Content-Type", "application/xml")
			body = fmt.Sprintf(`<urlset>
<url><loc>%s/docs/a</loc></url>
<url><loc>%s/duplicate?utm_source=x</loc></url>
<url><loc>%s/duplicate-copy</loc></url>
<url><loc>%s/redirect</loc></url>
<url><loc>%s/off-redirect</loc></url>
<url><loc>%s/missing</loc></url>
<url><loc>%s/huge</loc></url>
<url><loc>%s/blocked</loc></url>
<url><loc>https://off.example/elsewhere</loc></url>
</urlset>`, origin, origin, origin, origin, origin, origin, origin, origin)
		case "/":
			body = `<html><head><title>Fixture</title></head><body>
<a href="/docs/b">B</a>
<a href="/duplicate">D1</a>
<a href="/duplicate?utm_campaign=x">D2</a>
<a href="/tracking?utm_source=x&fbclid=y&q=agent">T</a>
<a href="/llms.txt">LLMS</a>
</body></html>`
		case "/docs/a":
			body = "doc a"
		case "/docs/b":
			body = "doc b"
		case "/docs/final":
			body = "final"
		case "/duplicate", "/duplicate-copy":
			body = "same duplicate body"
		case "/tracking":
			body = "tracking"
		case "/redirect":
			status = http.StatusFound
			header.Set("Location", origin+"/docs/final")
		case "/off-redirect":
			status = http.StatusFound
			header.Set("Location", "https://off.example/final")
		case "/missing":
			status = http.StatusNotFound
			body = "missing"
		case "/huge":
			body = strings.Repeat("x", 200)
		case "/blocked":
			body = "blocked"
		case "/llms.txt":
			header.Set("Content-Type", "text/plain")
			body = "llms"
		case "/llms-full.txt":
			header.Set("Content-Type", "text/plain")
			body = "llms full"
		default:
			status = http.StatusNotFound
			body = "not found"
		}
		return &http.Response{StatusCode: status, Header: header, Body: io.NopCloser(strings.NewReader(body)), Request: req}, nil
	})}
	return client, origin
}

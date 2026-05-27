package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

const archiveToolVersion = "world_scout_go.archive.v1"
const archiveUserAgent = "dharma-world-scout"
const archiveHTTPUserAgent = "dharma-world-scout/1.0 archive"
const archiveDiscoveryUserAgent = "dharma-world-scout/1.0 discovery"

const (
	CaptureCaptured          = "captured"
	CaptureDeduped           = "deduped"
	CaptureBlockedByRobots   = "blocked_by_robots"
	CaptureHTTPError         = "http_error"
	CaptureNetworkError      = "network_error"
	CaptureTruncated         = "truncated"
	CaptureSkippedPolicy     = "skipped_policy"
	CaptureUnsupportedScheme = "unsupported_scheme"
	CaptureDiscoveryError    = "discovery_error"
)

type ArchiveOptions struct {
	StateDir            string
	ArchiveDir          string
	MaxBytes            int64
	MaxDepth            int
	MaxPages            int
	SameDomain          bool
	RateLimitMS         int
	Include             []string
	Exclude             []string
	Correlation         string
	Workers             int
	DiscoverLLMS        bool
	DiscoverSitemap     bool
	SitemapMaxURLs      int
	RunID               string
	ToolVersion         string
	Args                []string
	RobotsEnabled       bool
	RobotsDisabled      bool
	DefaultCrawlDelayMS int
	MaxRetries          int
	RetryBaseDelayMS    int
	RetryMaxDelayMS     int
	MaxFetchDurationMS  int
}

type ArchiveEntry struct {
	URL               string        `json:"url"`
	CanonicalURL      string        `json:"canonical_url"`
	FinalURL          string        `json:"final_url,omitempty"`
	FinalCanonicalURL string        `json:"final_canonical_url,omitempty"`
	Title             string        `json:"title"`
	ContentType       string        `json:"content_type"`
	ContentHash       string        `json:"content_hash"`
	StartedAt         string        `json:"started_at,omitempty"`
	FetchedAt         string        `json:"fetched_at"`
	BodyPath          string        `json:"body_path"`
	ReceiptPath       string        `json:"receipt_path"`
	Links             []string      `json:"links"`
	SourceKind        string        `json:"source_kind"`
	StatusCode        int           `json:"status_code"`
	Bytes             int64         `json:"bytes"`
	Depth             int           `json:"depth"`
	DedupeOf          string        `json:"dedupe_of,omitempty"`
	CaptureStatus     string        `json:"capture_status"`
	ErrorClass        string        `json:"error_class,omitempty"`
	DurationMS        int64         `json:"duration_ms"`
	RetryCount        int           `json:"retry_count"`
	Truncated         bool          `json:"truncated"`
	RobotsDecision    string        `json:"robots_decision,omitempty"`
	RobotsReason      string        `json:"robots_reason,omitempty"`
	RedirectChain     []RedirectHop `json:"redirect_chain,omitempty"`
	Errors            []string      `json:"errors"`
}

type RedirectHop struct {
	From       string `json:"from"`
	To         string `json:"to"`
	StatusCode int    `json:"status_code,omitempty"`
}

type ArchiveDiscoveryEvent struct {
	Source         string `json:"source"`
	URL            string `json:"url"`
	CanonicalURL   string `json:"canonical_url"`
	StatusCode     int    `json:"status_code"`
	ContentHash    string `json:"content_hash,omitempty"`
	Bytes          int64  `json:"bytes"`
	RobotsDecision string `json:"robots_decision,omitempty"`
	RobotsReason   string `json:"robots_reason,omitempty"`
	CaptureStatus  string `json:"capture_status"`
	ErrorClass     string `json:"error_class,omitempty"`
	DurationMS     int64  `json:"duration_ms"`
	RetryCount     int    `json:"retry_count"`
	Error          string `json:"error,omitempty"`
}

type ReplayValidation struct {
	Status string   `json:"status"`
	Errors []string `json:"errors,omitempty"`
}

type SourceHash struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Kind string `json:"kind"`
	Hash string `json:"hash"`
}

type ArchiveResult struct {
	Entries          []ArchiveEntry
	ArchiveDir       string
	IndexPath        string
	IndexHash        string
	ManifestPath     string
	ArchiveCount     int
	DedupeCount      int
	DiscoveredCount  int
	WorkerCount      int
	TotalBytes       int64
	DiscoveryEvents  []ArchiveDiscoveryEvent
	StatusCounts     map[string]int
	ErrorCounts      map[string]int
	ReplayValidation ReplayValidation
	Errors           []string
}

type archiveQueueItem struct {
	URL   string
	Depth int
}

type archiveFetchResult struct {
	Entry ArchiveEntry
}

type archiveFileRefs struct {
	BodyPath    string
	ReceiptPath string
}

type archiveFetchOutcome struct {
	Body              []byte
	StartedAt         time.Time
	FetchedAt         time.Time
	StatusCode        int
	ContentType       string
	FinalURL          string
	FinalCanonicalURL string
	ContentHash       string
	Bytes             int64
	DurationMS        int64
	RetryCount        int
	RetryAfterMS      int
	Truncated         bool
	CaptureStatus     string
	ErrorClass        string
	Errors            []string
	RobotsDecision    string
	RobotsReason      string
	RedirectChain     []RedirectHop
}

type archiveHTTPClient struct {
	client    *http.Client
	opts      ArchiveOptions
	seedHosts map[string]bool
	mu        sync.Mutex
	robots    map[string]robotsPolicy
	robotsReq map[string]chan struct{}
	limiters  map[string]*hostLimiter
}

type hostLimiter struct {
	nextAllowed time.Time
}

type robotsPolicy struct {
	Origin       string
	StatusCode   int
	AllowAll     bool
	DisallowAll  bool
	Rules        []robotsRule
	Sitemaps     []string
	CrawlDelayMS int
	Warnings     []string
	FetchError   string
}

type robotsRule struct {
	Allow   bool
	Pattern string
}

type robotsGroup struct {
	Agents       []string
	Rules        []robotsRule
	CrawlDelayMS int
	Warnings     []string
}

func ArchiveSources(sources []Source, opts ArchiveOptions) ArchiveResult {
	return archiveSourcesWithHTTPClient(sources, opts, &http.Client{Timeout: 20 * time.Second})
}

func archiveSourcesWithHTTPClient(sources []Source, opts ArchiveOptions, httpClient *http.Client) ArchiveResult {
	started := time.Now().UTC()
	opts = normalizeArchiveOptions(opts, len(sources))
	archiveDir := opts.ArchiveDir
	if archiveDir == "" {
		archiveDir = filepath.Join(opts.StateDir, "meta", "world_radar", "archive", "world_scout")
	}
	_ = os.MkdirAll(filepath.Join(archiveDir, "bodies"), 0o755)
	_ = os.MkdirAll(filepath.Join(archiveDir, "receipts"), 0o755)
	indexPath := filepath.Join(archiveDir, "archive_index.jsonl")
	manifestPath := filepath.Join(archiveDir, "manifest.json")
	client := newArchiveHTTPClient(httpClient, opts, archiveSeedHosts(sources))
	queue := archiveInitialQueue(sources)
	discovered, discoveryEvents, discoveryErrors := discoverArchiveURLs(client, sources, opts)
	for _, rawURL := range discovered {
		queue = append(queue, archiveQueueItem{URL: rawURL, Depth: 0})
	}
	entries, dedupeCount, totalBytes, archiveErrors := runArchiveQueue(client, queue, archiveDir, opts)
	errors := append(discoveryErrors, archiveErrors...)
	if err := writeArchiveIndex(indexPath, entries); err != nil {
		errors = append(errors, err.Error())
	}
	indexHash := ""
	if hash, err := fileSHA256(indexPath); err != nil {
		errors = append(errors, err.Error())
	} else {
		indexHash = hash
	}
	result := ArchiveResult{
		Entries:          entries,
		ArchiveDir:       archiveDir,
		IndexPath:        indexPath,
		IndexHash:        indexHash,
		ManifestPath:     manifestPath,
		ArchiveCount:     len(entries),
		DedupeCount:      dedupeCount,
		DiscoveredCount:  len(discovered),
		WorkerCount:      opts.Workers,
		TotalBytes:       totalBytes,
		DiscoveryEvents:  discoveryEvents,
		StatusCounts:     archiveStatusCounts(entries),
		ErrorCounts:      archiveErrorCounts(entries, discoveryEvents),
		ReplayValidation: validateArchiveReplay(entries, indexPath, indexHash),
		Errors:           errors,
	}
	if result.ReplayValidation.Status == "failed" {
		result.Errors = append(result.Errors, result.ReplayValidation.Errors...)
	}
	if err := writeArchiveManifest(manifestPath, result, sources, opts, started); err != nil {
		result.Errors = append(result.Errors, err.Error())
	}
	return result
}

func normalizeArchiveOptions(opts ArchiveOptions, sourceCount int) ArchiveOptions {
	if opts.MaxPages <= 0 {
		opts.MaxPages = sourceCount
	}
	if opts.MaxPages <= 0 {
		opts.MaxPages = 1
	}
	if opts.MaxBytes <= 0 {
		opts.MaxBytes = 2_000_000
	}
	if opts.Workers <= 0 {
		opts.Workers = 6
	}
	if opts.Workers > 32 {
		opts.Workers = 32
	}
	if opts.Workers > opts.MaxPages {
		opts.Workers = opts.MaxPages
	}
	if opts.SitemapMaxURLs <= 0 {
		opts.SitemapMaxURLs = 100
	}
	if opts.RunID == "" {
		opts.RunID = "world_scout_archive_" + stableID(time.Now().UTC().Format(time.RFC3339Nano)+strings.Join(opts.Args, "\x00"))
	}
	if opts.ToolVersion == "" {
		opts.ToolVersion = archiveToolVersion
	}
	if opts.RobotsDisabled {
		opts.RobotsEnabled = false
	} else if !opts.RobotsEnabled {
		opts.RobotsEnabled = true
	}
	if opts.RateLimitMS < 0 {
		opts.RateLimitMS = 0
	}
	if opts.DefaultCrawlDelayMS < 0 {
		opts.DefaultCrawlDelayMS = 0
	}
	if opts.MaxRetries < 0 {
		opts.MaxRetries = 0
	}
	if opts.RetryBaseDelayMS <= 0 {
		opts.RetryBaseDelayMS = 250
	}
	if opts.RetryMaxDelayMS <= 0 {
		opts.RetryMaxDelayMS = 2_000
	}
	if opts.MaxFetchDurationMS <= 0 {
		opts.MaxFetchDurationMS = 30_000
	}
	return opts
}

func archiveInitialQueue(sources []Source) []archiveQueueItem {
	queue := []archiveQueueItem{}
	for _, source := range sources {
		if canonical := canonicalURL(source.URL); canonical != "" {
			queue = append(queue, archiveQueueItem{URL: canonical, Depth: 0})
		}
	}
	return queue
}

func archiveSeedHosts(sources []Source) map[string]bool {
	seedHosts := map[string]bool{}
	for _, source := range sources {
		if u, err := url.Parse(canonicalURL(source.URL)); err == nil && u.Hostname() != "" {
			seedHosts[strings.ToLower(u.Hostname())] = true
		}
	}
	return seedHosts
}

func newArchiveHTTPClient(client *http.Client, opts ArchiveOptions, seedHosts map[string]bool) *archiveHTTPClient {
	if client == nil {
		client = &http.Client{Timeout: 20 * time.Second}
	}
	return &archiveHTTPClient{
		client:    client,
		opts:      opts,
		seedHosts: seedHosts,
		robots:    map[string]robotsPolicy{},
		robotsReq: map[string]chan struct{}{},
		limiters:  map[string]*hostLimiter{},
	}
}

func runArchiveQueue(client *archiveHTTPClient, queue []archiveQueueItem, archiveDir string, opts ArchiveOptions) ([]ArchiveEntry, int, int64, []string) {
	jobs := make(chan archiveQueueItem)
	results := make(chan archiveFetchResult, opts.Workers)
	var wg sync.WaitGroup
	for i := 0; i < opts.Workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for item := range jobs {
				entry := fetchArchiveEntry(client, canonicalURL(item.URL), archiveDir, opts, item.Depth)
				results <- archiveFetchResult{Entry: entry}
			}
		}()
	}
	seenURL := map[string]bool{}
	seenHash := map[string]string{}
	keptFilesByURL := map[string]archiveFileRefs{}
	entries := []ArchiveEntry{}
	errors := []string{}
	dedupeCount := 0
	totalBytes := int64(0)
	active := 0
	for len(entries) < opts.MaxPages && (len(queue) > 0 || active > 0) {
		for active < opts.Workers && len(queue) > 0 && len(entries)+active < opts.MaxPages {
			item := queue[0]
			queue = queue[1:]
			canonical := canonicalURL(item.URL)
			if canonical == "" || seenURL[canonical] || !archiveURLAllowed(canonical, client.seedHosts, opts) {
				continue
			}
			seenURL[canonical] = true
			jobs <- archiveQueueItem{URL: canonical, Depth: item.Depth}
			active++
		}
		if active == 0 {
			break
		}
		result := <-results
		active--
		entry := result.Entry
		if entry.FinalCanonicalURL != "" && entry.FinalCanonicalURL != entry.CanonicalURL && seenURL[entry.FinalCanonicalURL] {
			removeDuplicateArchiveFilesExcept(entry, keptFilesByURL[entry.FinalCanonicalURL])
			entry.DedupeOf = entry.FinalCanonicalURL
			entry.BodyPath = ""
			entry.ReceiptPath = ""
			entry.CaptureStatus = CaptureDeduped
			dedupeCount++
		} else if entry.FinalCanonicalURL != "" {
			seenURL[entry.FinalCanonicalURL] = true
		}
		if prior, ok := seenHash[entry.ContentHash]; ok && entry.ContentHash != "" && archiveEntryDedupeEligible(entry) {
			removeDuplicateArchiveFiles(entry)
			entry.DedupeOf = prior
			entry.BodyPath = ""
			entry.ReceiptPath = ""
			entry.CaptureStatus = CaptureDeduped
			dedupeCount++
		} else if entry.ContentHash != "" && archiveEntryDedupeEligible(entry) {
			seenHash[entry.ContentHash] = firstNonEmpty(entry.FinalCanonicalURL, entry.CanonicalURL)
		}
		if archiveEntryDedupeEligible(entry) {
			files := archiveFileRefs{BodyPath: entry.BodyPath, ReceiptPath: entry.ReceiptPath}
			keptFilesByURL[entry.CanonicalURL] = files
			if entry.FinalCanonicalURL != "" {
				keptFilesByURL[entry.FinalCanonicalURL] = files
			}
		}
		if len(entry.Errors) > 0 {
			errors = append(errors, fmt.Sprintf("%s: %s", entry.CanonicalURL, strings.Join(entry.Errors, "; ")))
		}
		entries = append(entries, entry)
		totalBytes += entry.Bytes
		if entry.Depth >= opts.MaxDepth || entry.CaptureStatus == CaptureBlockedByRobots || entry.CaptureStatus == CaptureSkippedPolicy {
			continue
		}
		for _, link := range entry.Links {
			canonical := canonicalURL(link)
			if canonical != "" && !seenURL[canonical] && archiveURLAllowed(canonical, client.seedHosts, opts) {
				queue = append(queue, archiveQueueItem{URL: canonical, Depth: entry.Depth + 1})
			}
		}
	}
	close(jobs)
	wg.Wait()
	return entries, dedupeCount, totalBytes, errors
}

func archiveEntryDedupeEligible(entry ArchiveEntry) bool {
	return entry.CaptureStatus == CaptureCaptured || entry.CaptureStatus == CaptureTruncated
}

func removeDuplicateArchiveFiles(entry ArchiveEntry) {
	removeDuplicateArchiveFilesExcept(entry, archiveFileRefs{})
}

func removeDuplicateArchiveFilesExcept(entry ArchiveEntry, preserve archiveFileRefs) {
	if entry.BodyPath != "" {
		if preserve.BodyPath == "" || entry.BodyPath != preserve.BodyPath {
			_ = os.Remove(entry.BodyPath)
		}
	}
	if entry.ReceiptPath != "" {
		if preserve.ReceiptPath == "" || entry.ReceiptPath != preserve.ReceiptPath {
			_ = os.Remove(entry.ReceiptPath)
		}
	}
}

func fetchArchiveEntry(client *archiveHTTPClient, rawURL string, archiveDir string, opts ArchiveOptions, depth int) ArchiveEntry {
	canonical := canonicalURL(rawURL)
	started := time.Now().UTC()
	entry := ArchiveEntry{URL: rawURL, CanonicalURL: canonical, StartedAt: started.Format(time.RFC3339), FetchedAt: started.Format(time.RFC3339), Depth: depth, CaptureStatus: CaptureNetworkError}
	if canonical == "" {
		entry.CaptureStatus = CaptureUnsupportedScheme
		entry.ErrorClass = CaptureUnsupportedScheme
		entry.Errors = append(entry.Errors, "unsupported_scheme")
		return entry
	}
	outcome := client.fetch(canonical, archiveHTTPUserAgent, opts.MaxBytes, true, "archive")
	entry.StartedAt = outcome.StartedAt.Format(time.RFC3339)
	entry.FetchedAt = outcome.FetchedAt.Format(time.RFC3339)
	entry.StatusCode = outcome.StatusCode
	entry.ContentType = outcome.ContentType
	entry.SourceKind = archiveSourceKind(canonical, outcome.ContentType)
	entry.FinalURL = outcome.FinalURL
	entry.FinalCanonicalURL = outcome.FinalCanonicalURL
	entry.DurationMS = outcome.DurationMS
	entry.RetryCount = outcome.RetryCount
	entry.Truncated = outcome.Truncated
	entry.CaptureStatus = outcome.CaptureStatus
	entry.ErrorClass = outcome.ErrorClass
	entry.RobotsDecision = outcome.RobotsDecision
	entry.RobotsReason = outcome.RobotsReason
	entry.RedirectChain = outcome.RedirectChain
	entry.Errors = append(entry.Errors, outcome.Errors...)
	if len(outcome.Body) > 0 || outcome.ContentHash != "" {
		entry.Bytes = outcome.Bytes
		entry.ContentHash = outcome.ContentHash
		text := string(outcome.Body)
		entry.Title = extractTitle(text)
		entry.Links = extractLinks(firstNonEmpty(entry.FinalCanonicalURL, entry.CanonicalURL), text)
	}
	if outcome.CaptureStatus == CaptureBlockedByRobots || outcome.CaptureStatus == CaptureSkippedPolicy || outcome.CaptureStatus == CaptureUnsupportedScheme || outcome.CaptureStatus == CaptureNetworkError || outcome.CaptureStatus == CaptureHTTPError {
		return entry
	}
	basename := safeArchiveName(firstNonEmpty(entry.FinalCanonicalURL, entry.CanonicalURL), entry.ContentHash)
	bodyPath := filepath.Join(archiveDir, "bodies", basename+extensionFor(entry.ContentType, firstNonEmpty(entry.FinalCanonicalURL, entry.CanonicalURL)))
	if err := os.MkdirAll(filepath.Dir(bodyPath), 0o755); err != nil {
		entry.Errors = append(entry.Errors, err.Error())
		entry.ErrorClass = "write_error"
		entry.CaptureStatus = CaptureNetworkError
	} else if err := os.WriteFile(bodyPath, outcome.Body, 0o644); err != nil {
		entry.Errors = append(entry.Errors, err.Error())
		entry.ErrorClass = "write_error"
		entry.CaptureStatus = CaptureNetworkError
	} else {
		entry.BodyPath = bodyPath
	}
	receiptPath := filepath.Join(archiveDir, "receipts", basename+".receipt.json")
	if err := writeArchiveReceipt(receiptPath, entry, opts); err != nil {
		entry.Errors = append(entry.Errors, err.Error())
		entry.ErrorClass = "write_error"
		entry.CaptureStatus = CaptureNetworkError
	} else {
		entry.ReceiptPath = receiptPath
	}
	return entry
}

func (client *archiveHTTPClient) fetch(rawURL string, userAgent string, maxBytes int64, enforceRobots bool, purpose string) archiveFetchOutcome {
	started := time.Now().UTC()
	outcome := archiveFetchOutcome{StartedAt: started, FetchedAt: started, FinalURL: rawURL, FinalCanonicalURL: canonicalURL(rawURL), CaptureStatus: CaptureNetworkError}
	canonical := canonicalURL(rawURL)
	if canonical == "" {
		outcome.CaptureStatus = CaptureUnsupportedScheme
		outcome.ErrorClass = CaptureUnsupportedScheme
		outcome.Errors = append(outcome.Errors, "unsupported_scheme")
		return outcome
	}
	origin := originFor(canonical)
	robotsDelay := 0
	if enforceRobots && client.opts.RobotsEnabled {
		policy := client.robotsFor(origin)
		allowed, reason := policy.allowed(canonical)
		outcome.RobotsReason = reason
		if !allowed {
			outcome.FetchedAt = time.Now().UTC()
			outcome.DurationMS = outcome.FetchedAt.Sub(started).Milliseconds()
			outcome.CaptureStatus = CaptureBlockedByRobots
			outcome.ErrorClass = CaptureBlockedByRobots
			outcome.RobotsDecision = "blocked"
			outcome.Errors = append(outcome.Errors, reason)
			return outcome
		}
		outcome.RobotsDecision = "allowed"
		robotsDelay = policy.CrawlDelayMS
	} else {
		outcome.RobotsDecision = "not_checked"
	}
	maxDuration := time.Duration(client.opts.MaxFetchDurationMS) * time.Millisecond
	attempts := client.opts.MaxRetries + 1
	for attempt := 0; attempt < attempts; attempt++ {
		if time.Since(started) > maxDuration {
			outcome.Errors = append(outcome.Errors, "max_fetch_duration_exceeded")
			outcome.ErrorClass = "max_fetch_duration_exceeded"
			break
		}
		client.waitForHost(origin, robotsDelay)
		attemptOutcome := client.fetchOnce(canonical, userAgent, maxBytes, true)
		outcome = mergeFetchOutcome(outcome, attemptOutcome)
		outcome.RetryCount = attempt
		if !retryableOutcome(attemptOutcome) || attempt == attempts-1 {
			return outcome
		}
		delay := retryDelay(attemptOutcome, client.opts, attempt)
		if delay > 0 {
			time.Sleep(delay)
		}
	}
	outcome.FetchedAt = time.Now().UTC()
	outcome.DurationMS = outcome.FetchedAt.Sub(started).Milliseconds()
	return outcome
}

func (client *archiveHTTPClient) fetchOnce(rawURL string, userAgent string, maxBytes int64, checkRedirectRobots bool) archiveFetchOutcome {
	started := time.Now().UTC()
	outcome := archiveFetchOutcome{StartedAt: started, FetchedAt: started, FinalURL: rawURL, FinalCanonicalURL: canonicalURL(rawURL), CaptureStatus: CaptureNetworkError}
	req, err := http.NewRequest(http.MethodGet, rawURL, nil)
	if err != nil {
		outcome.FetchedAt = time.Now().UTC()
		outcome.DurationMS = outcome.FetchedAt.Sub(started).Milliseconds()
		outcome.CaptureStatus = CaptureUnsupportedScheme
		outcome.ErrorClass = "invalid_request"
		outcome.Errors = append(outcome.Errors, err.Error())
		return outcome
	}
	req.Header.Set("User-Agent", userAgent)
	redirectBlocked := false
	redirectBlockedStatus := CaptureSkippedPolicy
	redirectBlockedClass := "off_domain_redirect"
	redirectBlockedReason := "redirect_final_url_outside_allowed_scope"
	redirectBlockedTarget := ""
	redirectChain := []RedirectHop{}
	httpClient := *client.client
	httpClient.CheckRedirect = func(req *http.Request, via []*http.Request) error {
		from := ""
		if len(via) > 0 {
			from = via[len(via)-1].URL.String()
		}
		to := req.URL.String()
		redirectChain = append(redirectChain, RedirectHop{From: from, To: to})
		if client.opts.SameDomain && !archiveURLAllowed(to, client.seedHosts, client.opts) {
			redirectBlocked = true
			redirectBlockedStatus = CaptureSkippedPolicy
			redirectBlockedClass = "off_domain_redirect"
			redirectBlockedReason = "redirect_final_url_outside_allowed_scope"
			redirectBlockedTarget = to
			return http.ErrUseLastResponse
		}
		if checkRedirectRobots && client.opts.RobotsEnabled {
			toCanonical := canonicalURL(to)
			policy := client.robotsFor(originFor(toCanonical))
			allowed, reason := policy.allowed(toCanonical)
			if !allowed {
				redirectBlocked = true
				redirectBlockedStatus = CaptureBlockedByRobots
				redirectBlockedClass = CaptureBlockedByRobots
				redirectBlockedReason = "redirect_target_" + reason
				redirectBlockedTarget = to
				return http.ErrUseLastResponse
			}
		}
		return nil
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		outcome.FetchedAt = time.Now().UTC()
		outcome.DurationMS = outcome.FetchedAt.Sub(started).Milliseconds()
		outcome.ErrorClass = CaptureNetworkError
		outcome.CaptureStatus = CaptureNetworkError
		outcome.Errors = append(outcome.Errors, err.Error())
		outcome.RedirectChain = redirectChain
		return outcome
	}
	defer resp.Body.Close()
	outcome.StatusCode = resp.StatusCode
	outcome.ContentType = strings.Split(resp.Header.Get("Content-Type"), ";")[0]
	outcome.RetryAfterMS = parseRetryAfterMS(resp.Header.Get("Retry-After"))
	outcome.FinalURL = rawURL
	if resp.Request != nil && resp.Request.URL != nil {
		outcome.FinalURL = resp.Request.URL.String()
	}
	if redirectBlockedTarget != "" {
		outcome.FinalURL = redirectBlockedTarget
	}
	outcome.FinalCanonicalURL = canonicalURL(outcome.FinalURL)
	outcome.RedirectChain = redirectChain
	if redirectBlocked {
		outcome.FetchedAt = time.Now().UTC()
		outcome.DurationMS = outcome.FetchedAt.Sub(started).Milliseconds()
		outcome.CaptureStatus = redirectBlockedStatus
		outcome.ErrorClass = redirectBlockedClass
		if redirectBlockedStatus == CaptureBlockedByRobots {
			outcome.RobotsDecision = "blocked"
			outcome.RobotsReason = redirectBlockedReason
		}
		outcome.Errors = append(outcome.Errors, redirectBlockedReason)
		return outcome
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxBytes+1))
	if err != nil {
		outcome.FetchedAt = time.Now().UTC()
		outcome.DurationMS = outcome.FetchedAt.Sub(started).Milliseconds()
		outcome.ErrorClass = "read_error"
		outcome.CaptureStatus = CaptureNetworkError
		outcome.Errors = append(outcome.Errors, err.Error())
		return outcome
	}
	if int64(len(body)) > maxBytes {
		body = body[:maxBytes]
		outcome.Truncated = true
		outcome.Errors = append(outcome.Errors, "body_truncated_at_max_bytes")
	}
	outcome.Body = body
	outcome.Bytes = int64(len(body))
	outcome.ContentHash = contentHash(body)
	outcome.FetchedAt = time.Now().UTC()
	outcome.DurationMS = outcome.FetchedAt.Sub(started).Milliseconds()
	switch {
	case resp.StatusCode >= 400:
		outcome.CaptureStatus = CaptureHTTPError
		outcome.ErrorClass = fmt.Sprintf("status_%d", resp.StatusCode)
		outcome.Errors = append(outcome.Errors, fmt.Sprintf("status_%d", resp.StatusCode))
	case outcome.Truncated:
		outcome.CaptureStatus = CaptureTruncated
	default:
		outcome.CaptureStatus = CaptureCaptured
	}
	return outcome
}

func mergeFetchOutcome(base archiveFetchOutcome, attempt archiveFetchOutcome) archiveFetchOutcome {
	attempt.StartedAt = base.StartedAt
	if attempt.RobotsDecision == "" {
		attempt.RobotsDecision = base.RobotsDecision
	}
	if attempt.RobotsReason == "" {
		attempt.RobotsReason = base.RobotsReason
	}
	return attempt
}

func retryableOutcome(outcome archiveFetchOutcome) bool {
	if outcome.ErrorClass == CaptureNetworkError || outcome.ErrorClass == "read_error" {
		return true
	}
	return outcome.StatusCode == 429 || outcome.StatusCode >= 500
}

func retryDelay(outcome archiveFetchOutcome, opts ArchiveOptions, attempt int) time.Duration {
	base := opts.RetryBaseDelayMS
	if base <= 0 {
		base = 250
	}
	delayMS := base << attempt
	if outcome.RetryAfterMS > delayMS {
		delayMS = outcome.RetryAfterMS
	}
	if opts.RetryMaxDelayMS > 0 && delayMS > opts.RetryMaxDelayMS {
		delayMS = opts.RetryMaxDelayMS
	}
	return time.Duration(delayMS) * time.Millisecond
}

func parseRetryAfterMS(value string) int {
	value = strings.TrimSpace(value)
	if value == "" {
		return 0
	}
	if seconds, err := strconv.Atoi(value); err == nil && seconds >= 0 {
		return seconds * 1000
	}
	if when, err := http.ParseTime(value); err == nil {
		delta := time.Until(when)
		if delta > 0 {
			return int(delta / time.Millisecond)
		}
	}
	return 0
}

func (client *archiveHTTPClient) waitForHost(origin string, robotsDelayMS int) {
	delayMS := client.opts.RateLimitMS
	if client.opts.DefaultCrawlDelayMS > delayMS {
		delayMS = client.opts.DefaultCrawlDelayMS
	}
	if robotsDelayMS > delayMS {
		delayMS = robotsDelayMS
	}
	if delayMS <= 0 || origin == "" {
		return
	}
	client.mu.Lock()
	limiter := client.limiters[origin]
	if limiter == nil {
		limiter = &hostLimiter{}
		client.limiters[origin] = limiter
	}
	now := time.Now()
	wait := time.Duration(0)
	if limiter.nextAllowed.After(now) {
		wait = limiter.nextAllowed.Sub(now)
		limiter.nextAllowed = limiter.nextAllowed.Add(time.Duration(delayMS) * time.Millisecond)
	} else {
		limiter.nextAllowed = now.Add(time.Duration(delayMS) * time.Millisecond)
	}
	client.mu.Unlock()
	if wait > 0 {
		time.Sleep(wait)
	}
}

func (client *archiveHTTPClient) robotsFor(origin string) robotsPolicy {
	for {
		client.mu.Lock()
		if policy, ok := client.robots[origin]; ok {
			client.mu.Unlock()
			return policy
		}
		if waitCh, ok := client.robotsReq[origin]; ok {
			client.mu.Unlock()
			<-waitCh
			continue
		}
		waitCh := make(chan struct{})
		client.robotsReq[origin] = waitCh
		client.mu.Unlock()

		policy := client.fetchRobots(origin)
		client.mu.Lock()
		client.robots[origin] = policy
		delete(client.robotsReq, origin)
		close(waitCh)
		client.mu.Unlock()
		return policy
	}
}

func (client *archiveHTTPClient) fetchRobots(origin string) robotsPolicy {
	policy := robotsPolicy{Origin: origin, AllowAll: true}
	if origin == "" {
		policy.DisallowAll = true
		policy.AllowAll = false
		policy.FetchError = "missing_origin"
		return policy
	}
	robotsURL := origin + "/robots.txt"
	outcome := client.fetchOnce(robotsURL, archiveDiscoveryUserAgent, 500_000, false)
	policy.StatusCode = outcome.StatusCode
	if outcome.ErrorClass != "" && outcome.StatusCode == 0 {
		policy.AllowAll = false
		policy.DisallowAll = true
		policy.FetchError = outcome.ErrorClass
		return policy
	}
	switch {
	case outcome.StatusCode == 404:
		policy.AllowAll = true
		return policy
	case outcome.StatusCode == 401 || outcome.StatusCode == 403:
		policy.AllowAll = false
		policy.DisallowAll = true
		policy.FetchError = fmt.Sprintf("robots_status_%d", outcome.StatusCode)
		return policy
	case outcome.StatusCode >= 500:
		policy.AllowAll = false
		policy.DisallowAll = true
		policy.FetchError = fmt.Sprintf("robots_status_%d", outcome.StatusCode)
		return policy
	case outcome.StatusCode >= 400:
		policy.AllowAll = true
		return policy
	}
	if outcome.CaptureStatus != CaptureCaptured && outcome.CaptureStatus != CaptureTruncated {
		policy.AllowAll = false
		policy.DisallowAll = true
		policy.FetchError = firstNonEmpty(outcome.ErrorClass, outcome.CaptureStatus, "robots_unavailable")
		return policy
	}
	return parseRobots(string(outcome.Body), origin, archiveUserAgent)
}

func parseRobots(text string, origin string, agent string) robotsPolicy {
	policy := robotsPolicy{Origin: origin, AllowAll: true}
	groups := []robotsGroup{}
	current := robotsGroup{}
	hasRules := false
	flush := func() {
		if len(current.Agents) > 0 || len(current.Rules) > 0 || current.CrawlDelayMS > 0 || len(current.Warnings) > 0 {
			groups = append(groups, current)
		}
		current = robotsGroup{}
		hasRules = false
	}
	for _, rawLine := range strings.Split(text, "\n") {
		line := strings.TrimSpace(strings.Split(rawLine, "#")[0])
		if line == "" {
			flush()
			continue
		}
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			current.Warnings = append(current.Warnings, "unsupported_line")
			continue
		}
		key := strings.ToLower(strings.TrimSpace(parts[0]))
		value := strings.TrimSpace(parts[1])
		switch key {
		case "user-agent":
			if hasRules && len(current.Agents) > 0 {
				flush()
			}
			current.Agents = append(current.Agents, strings.ToLower(value))
		case "allow":
			current.Rules = append(current.Rules, robotsRule{Allow: true, Pattern: value})
			hasRules = true
		case "disallow":
			if value != "" {
				current.Rules = append(current.Rules, robotsRule{Allow: false, Pattern: value})
			}
			hasRules = true
		case "crawl-delay":
			if delay, err := strconv.ParseFloat(value, 64); err == nil && delay >= 0 {
				current.CrawlDelayMS = int(delay * 1000)
			} else {
				current.Warnings = append(current.Warnings, "invalid_crawl_delay")
			}
		case "sitemap":
			policy.Sitemaps = append(policy.Sitemaps, value)
		default:
			current.Warnings = append(current.Warnings, "unsupported_directive:"+key)
		}
	}
	flush()
	matched := selectRobotsGroup(groups, agent)
	policy.Rules = matched.Rules
	policy.CrawlDelayMS = matched.CrawlDelayMS
	policy.Warnings = matched.Warnings
	return policy
}

func selectRobotsGroup(groups []robotsGroup, agent string) robotsGroup {
	agent = strings.ToLower(agent)
	wildcard := robotsGroup{}
	for _, group := range groups {
		for _, candidate := range group.Agents {
			candidate = strings.ToLower(strings.TrimSpace(candidate))
			if candidate == "*" && len(wildcard.Agents) == 0 {
				wildcard = group
			}
			if candidate != "" && candidate != "*" && strings.Contains(agent, candidate) {
				return group
			}
		}
	}
	return wildcard
}

func (policy robotsPolicy) allowed(rawURL string) (bool, string) {
	if policy.DisallowAll {
		return false, firstNonEmpty(policy.FetchError, "robots_disallow_all")
	}
	if !policy.AllowAll && len(policy.Rules) == 0 {
		return false, firstNonEmpty(policy.FetchError, "robots_unavailable")
	}
	u, err := url.Parse(rawURL)
	if err != nil {
		return false, "invalid_url_for_robots"
	}
	path := u.EscapedPath()
	if path == "" {
		path = "/"
	}
	if u.RawQuery != "" {
		path += "?" + u.RawQuery
	}
	var best *robotsRule
	bestLen := -1
	for idx := range policy.Rules {
		rule := &policy.Rules[idx]
		if rule.Pattern == "" {
			continue
		}
		if robotsPatternMatch(rule.Pattern, path) {
			length := len(strings.ReplaceAll(strings.TrimSuffix(rule.Pattern, "$"), "*", ""))
			if length > bestLen || (length == bestLen && rule.Allow) {
				best = rule
				bestLen = length
			}
		}
	}
	if best != nil {
		if best.Allow {
			return true, "robots_allow:" + best.Pattern
		}
		return false, "robots_disallow:" + best.Pattern
	}
	if len(policy.Warnings) > 0 {
		return false, "unsupported_robots_syntax"
	}
	return true, "robots_default_allow"
}

func robotsPatternMatch(pattern string, path string) bool {
	if pattern == "" {
		return false
	}
	anchorEnd := strings.HasSuffix(pattern, "$")
	if anchorEnd {
		pattern = strings.TrimSuffix(pattern, "$")
	}
	parts := strings.Split(pattern, "*")
	if len(parts) == 1 {
		if anchorEnd {
			return path == pattern
		}
		return strings.HasPrefix(path, pattern)
	}
	pos := 0
	for idx, part := range parts {
		if part == "" {
			continue
		}
		found := strings.Index(path[pos:], part)
		if found < 0 {
			return false
		}
		if idx == 0 && !strings.HasPrefix(path, part) {
			return false
		}
		pos += found + len(part)
	}
	if anchorEnd && len(parts) > 0 {
		last := parts[len(parts)-1]
		return last == "" || strings.HasSuffix(path, last)
	}
	return true
}

func discoverArchiveURLs(client *archiveHTTPClient, sources []Source, opts ArchiveOptions) ([]string, []ArchiveDiscoveryEvent, []string) {
	seen := map[string]bool{}
	urls := []string{}
	events := []ArchiveDiscoveryEvent{}
	errors := []string{}
	add := func(rawURL string) {
		canonical := canonicalURL(rawURL)
		if canonical == "" || seen[canonical] || !archiveURLAllowed(canonical, client.seedHosts, opts) {
			return
		}
		seen[canonical] = true
		urls = append(urls, canonical)
	}
	for _, source := range sources {
		origin := originFor(source.URL)
		if origin == "" {
			continue
		}
		if opts.DiscoverLLMS {
			_, event, err := fetchSmallText(client, origin+"/llms.txt", 4_096, "llms_txt")
			events = append(events, event)
			if err == nil {
				add(origin + "/llms.txt")
			}
			_, event, err = fetchSmallText(client, origin+"/llms-full.txt", 4_096, "llms_full_txt")
			events = append(events, event)
			if err == nil {
				add(origin + "/llms-full.txt")
			}
		}
		if opts.DiscoverSitemap {
			discovered, sitemapEvents, err := discoverSitemapURLs(client, origin, opts.SitemapMaxURLs)
			events = append(events, sitemapEvents...)
			if err != nil {
				errors = append(errors, err.Error())
			}
			for _, rawURL := range discovered {
				add(rawURL)
			}
		}
	}
	return urls, events, errors
}

func discoverSitemapURLs(client *archiveHTTPClient, origin string, limit int) ([]string, []ArchiveDiscoveryEvent, error) {
	sitemapURLs := []string{}
	events := []ArchiveDiscoveryEvent{}
	policy := client.robotsFor(origin)
	sitemapURLs = append(sitemapURLs, policy.Sitemaps...)
	if len(sitemapURLs) == 0 {
		sitemapURLs = append(sitemapURLs, origin+"/sitemap.xml")
	}
	urls := []string{}
	var lastErr error
	for _, sitemapURL := range sitemapURLs {
		if len(urls) >= limit {
			break
		}
		text, event, err := fetchSmallText(client, sitemapURL, 2_000_000, "sitemap")
		events = append(events, event)
		if err != nil {
			lastErr = err
			continue
		}
		for _, loc := range extractSitemapLocs(text) {
			if len(urls) >= limit {
				break
			}
			urls = append(urls, loc)
		}
	}
	if len(urls) == 0 && lastErr != nil {
		return urls, events, lastErr
	}
	return urls, events, nil
}

func fetchSmallText(client *archiveHTTPClient, rawURL string, maxBytes int64, source string) (string, ArchiveDiscoveryEvent, error) {
	outcome := client.fetch(rawURL, archiveDiscoveryUserAgent, maxBytes, true, "discovery")
	event := ArchiveDiscoveryEvent{
		Source:         source,
		URL:            rawURL,
		CanonicalURL:   canonicalURL(rawURL),
		StatusCode:     outcome.StatusCode,
		ContentHash:    outcome.ContentHash,
		Bytes:          outcome.Bytes,
		RobotsDecision: outcome.RobotsDecision,
		RobotsReason:   outcome.RobotsReason,
		CaptureStatus:  outcome.CaptureStatus,
		ErrorClass:     outcome.ErrorClass,
		DurationMS:     outcome.DurationMS,
		RetryCount:     outcome.RetryCount,
	}
	if outcome.CaptureStatus != CaptureCaptured && outcome.CaptureStatus != CaptureTruncated {
		err := strings.Join(outcome.Errors, "; ")
		if err == "" {
			err = outcome.CaptureStatus
		}
		event.Error = err
		return "", event, fmt.Errorf("%s: %s", rawURL, err)
	}
	return string(outcome.Body), event, nil
}

func extractSitemapLocs(text string) []string {
	pattern := regexp.MustCompile(`(?is)<loc>\s*(.*?)\s*</loc>`)
	matches := pattern.FindAllStringSubmatch(text, -1)
	urls := []string{}
	for _, match := range matches {
		if len(match) > 1 {
			urls = append(urls, htmlUnescape(strings.TrimSpace(match[1])))
		}
	}
	return urls
}

func originFor(rawURL string) string {
	u, err := url.Parse(canonicalURL(rawURL))
	if err != nil || u.Scheme == "" || u.Host == "" {
		return ""
	}
	return u.Scheme + "://" + u.Host
}

func writeArchiveIndex(path string, entries []ArchiveEntry) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	file, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".*.tmp")
	if err != nil {
		return err
	}
	tmp := file.Name()
	defer os.Remove(tmp)
	enc := json.NewEncoder(file)
	for _, entry := range entries {
		if err := enc.Encode(entry); err != nil {
			file.Close()
			return err
		}
	}
	if err := file.Sync(); err != nil {
		file.Close()
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func writeArchiveManifest(path string, result ArchiveResult, sources []Source, opts ArchiveOptions, started time.Time) error {
	payload := map[string]any{
		"schema_version":        "world_scout_archive_manifest.v1",
		"run_id":                opts.RunID,
		"tool_version":          opts.ToolVersion,
		"generated_at":          time.Now().UTC().Format(time.RFC3339),
		"duration_ms":           time.Since(started).Milliseconds(),
		"archive_dir":           result.ArchiveDir,
		"archive_index_path":    result.IndexPath,
		"archive_index_hash":    result.IndexHash,
		"archive_count":         result.ArchiveCount,
		"dedupe_count":          result.DedupeCount,
		"discovered_count":      result.DiscoveredCount,
		"worker_count":          result.WorkerCount,
		"total_bytes":           result.TotalBytes,
		"source_count":          len(sources),
		"sources":               sources,
		"source_hashes":         sourceHashes(sources),
		"aggregate_source_hash": aggregateSourceHash(sources),
		"discovery_events":      result.DiscoveryEvents,
		"status_counts":         result.StatusCounts,
		"error_counts":          result.ErrorCounts,
		"replay_validation":     result.ReplayValidation,
		"cli_args":              opts.Args,
		"options": map[string]any{
			"max_bytes":              opts.MaxBytes,
			"max_depth":              opts.MaxDepth,
			"max_pages":              opts.MaxPages,
			"same_domain":            opts.SameDomain,
			"rate_limit_ms":          opts.RateLimitMS,
			"include":                opts.Include,
			"exclude":                opts.Exclude,
			"workers":                opts.Workers,
			"discover_llms":          opts.DiscoverLLMS,
			"discover_sitemap":       opts.DiscoverSitemap,
			"sitemap_max_urls":       opts.SitemapMaxURLs,
			"robots_enabled":         opts.RobotsEnabled,
			"default_crawl_delay_ms": opts.DefaultCrawlDelayMS,
			"max_retries":            opts.MaxRetries,
			"retry_base_delay_ms":    opts.RetryBaseDelayMS,
			"retry_max_delay_ms":     opts.RetryMaxDelayMS,
			"max_fetch_duration_ms":  opts.MaxFetchDurationMS,
		},
	}
	data, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if _, err := tmp.Write(append(data, '\n')); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(tmpName, path)
}

func writeArchiveReceipt(path string, entry ArchiveEntry, opts ArchiveOptions) error {
	correlation := opts.Correlation
	if correlation == "" {
		correlation = "world_scout_archive"
	}
	payload := map[string]any{
		"url": entry.URL, "canonical_url": entry.CanonicalURL, "final_url": entry.FinalURL,
		"final_canonical_url": entry.FinalCanonicalURL, "title": entry.Title,
		"content_type": entry.ContentType, "content_hash": entry.ContentHash,
		"fetched_at": entry.FetchedAt, "body_path": entry.BodyPath, "bytes": entry.Bytes,
	}
	data, err := json.MarshalIndent(map[string]any{
		"schema_version": "go_site_archive_receipt.v1",
		"receipt_id":     "goarch_" + stableID(correlation+opts.RunID+entry.CanonicalURL+entry.ContentHash),
		"run_id":         opts.RunID,
		"tool_version":   opts.ToolVersion,
		"correlation_id": correlation,
		"source":         "world_scout_archive",
		"source_url":     entry.CanonicalURL,
		"observed_at":    entry.FetchedAt,
		"content_hash":   entry.ContentHash,
		"capture_status": entry.CaptureStatus,
		"error_class":    entry.ErrorClass,
		"request": map[string]any{
			"method":        http.MethodGet,
			"url":           entry.URL,
			"canonical_url": entry.CanonicalURL,
			"user_agent":    archiveHTTPUserAgent,
			"started_at":    entry.StartedAt,
		},
		"response": map[string]any{
			"final_url":           entry.FinalURL,
			"final_canonical_url": entry.FinalCanonicalURL,
			"status_code":         entry.StatusCode,
			"content_type":        entry.ContentType,
			"fetched_at":          entry.FetchedAt,
		},
		"redirect_chain":  entry.RedirectChain,
		"duration_ms":     entry.DurationMS,
		"retry_count":     entry.RetryCount,
		"truncated":       entry.Truncated,
		"robots_decision": entry.RobotsDecision,
		"robots_reason":   entry.RobotsReason,
		"payload":         payload,
	}, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	file, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".*.tmp")
	if err != nil {
		return err
	}
	tmpName := file.Name()
	defer os.Remove(tmpName)
	if _, err := file.Write(append(data, '\n')); err != nil {
		file.Close()
		return err
	}
	if err := file.Sync(); err != nil {
		file.Close()
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	return os.Rename(tmpName, path)
}

func archiveURLAllowed(rawURL string, seedHosts map[string]bool, opts ArchiveOptions) bool {
	u, err := url.Parse(canonicalURL(rawURL))
	if err != nil || u.Scheme == "" || u.Host == "" {
		return false
	}
	if opts.SameDomain && !seedHosts[strings.ToLower(u.Hostname())] {
		return false
	}
	for _, pattern := range opts.Exclude {
		if pattern != "" && strings.Contains(rawURL, pattern) {
			return false
		}
	}
	if len(opts.Include) == 0 {
		return true
	}
	for _, pattern := range opts.Include {
		if pattern != "" && strings.Contains(rawURL, pattern) {
			return true
		}
	}
	return false
}

func canonicalURL(rawURL string) string {
	u, err := url.Parse(strings.TrimSpace(rawURL))
	if err != nil || u.Scheme == "" || u.Host == "" {
		return ""
	}
	u.Scheme = strings.ToLower(u.Scheme)
	if u.Scheme != "http" && u.Scheme != "https" {
		return ""
	}
	host := strings.ToLower(u.Hostname())
	port := u.Port()
	if port != "" && !((u.Scheme == "http" && port == "80") || (u.Scheme == "https" && port == "443")) {
		host = net.JoinHostPort(host, port)
	}
	u.Host = host
	u.Fragment = ""
	if u.Path == "" {
		u.Path = "/"
	}
	query := u.Query()
	for key := range query {
		if isTrackingParam(key) {
			query.Del(key)
		}
	}
	for key, values := range query {
		sort.Strings(values)
		query[key] = values
	}
	u.RawQuery = query.Encode()
	return u.String()
}

func isTrackingParam(key string) bool {
	key = strings.ToLower(key)
	if strings.HasPrefix(key, "utm_") {
		return true
	}
	switch key {
	case "fbclid", "gclid", "dclid", "msclkid", "gbraid", "wbraid", "mc_cid", "mc_eid", "igshid", "yclid":
		return true
	default:
		return false
	}
}

func contentHash(body []byte) string {
	sum := sha256.Sum256(body)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func fileSHA256(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return contentHash(data), nil
}

func safeArchiveName(rawURL, hash string) string {
	u, _ := url.Parse(rawURL)
	name := strings.Trim(u.Hostname()+u.EscapedPath(), "/")
	name = strings.NewReplacer("/", "_", ":", "_", "?", "_", "&", "_", "=", "_").Replace(name)
	name = regexp.MustCompile(`[^A-Za-z0-9._-]+`).ReplaceAllString(name, "_")
	if len(name) > 90 {
		name = name[:90]
	}
	if hash == "" {
		hash = contentHash([]byte(rawURL))
	}
	return name + "_" + strings.TrimPrefix(hash, "sha256:")[:12]
}

func archiveSourceKind(rawURL, contentType string) string {
	switch {
	case strings.HasSuffix(rawURL, "/llms.txt") || strings.HasSuffix(rawURL, "/llms-full.txt"):
		return "llms_txt"
	case strings.Contains(contentType, "markdown") || strings.HasSuffix(rawURL, ".md"):
		return "markdown"
	case strings.Contains(contentType, "plain") || strings.HasSuffix(rawURL, ".txt"):
		return "text"
	case strings.Contains(contentType, "json"):
		return "json"
	default:
		return inferKind(rawURL)
	}
}

func extensionFor(contentType, rawURL string) string {
	switch {
	case strings.Contains(contentType, "markdown") || strings.HasSuffix(rawURL, ".md"):
		return ".md"
	case strings.Contains(contentType, "plain") || strings.HasSuffix(rawURL, ".txt"):
		return ".txt"
	case strings.Contains(contentType, "json"):
		return ".json"
	case strings.Contains(contentType, "xml") || strings.HasSuffix(rawURL, ".xml"):
		return ".xml"
	case strings.Contains(contentType, "pdf") || strings.HasSuffix(rawURL, ".pdf"):
		return ".pdf"
	default:
		return ".html"
	}
}

func extractTitle(text string) string {
	patterns := []*regexp.Regexp{
		regexp.MustCompile(`(?is)<title[^>]*>(.*?)</title>`),
		regexp.MustCompile(`(?is)<h1[^>]*>(.*?)</h1>`),
		regexp.MustCompile(`(?m)^#\s+(.+)$`),
	}
	for _, pattern := range patterns {
		match := pattern.FindStringSubmatch(text)
		if len(match) > 1 {
			return trimArchiveText(stripTags(match[1]), 180)
		}
	}
	return ""
}

func extractLinks(baseURL, text string) []string {
	base, err := url.Parse(baseURL)
	if err != nil {
		return nil
	}
	seen := map[string]bool{}
	links := []string{}
	patterns := []*regexp.Regexp{
		regexp.MustCompile(`(?is)href=["']([^"']+)["']`),
		regexp.MustCompile(`(?m)\[[^\]]+\]\((https?://[^)]+)\)`),
	}
	for _, pattern := range patterns {
		for _, match := range pattern.FindAllStringSubmatch(text, -1) {
			if len(match) < 2 {
				continue
			}
			link := resolveLink(base, match[1])
			if link == "" || seen[link] {
				continue
			}
			seen[link] = true
			links = append(links, link)
		}
	}
	sort.Strings(links)
	return links
}

func resolveLink(base *url.URL, raw string) string {
	candidate := strings.TrimSpace(raw)
	if candidate == "" || strings.HasPrefix(candidate, "mailto:") || strings.HasPrefix(candidate, "javascript:") {
		return ""
	}
	u, err := url.Parse(candidate)
	if err != nil {
		return ""
	}
	return canonicalURL(base.ResolveReference(u).String())
}

func trimArchiveText(text string, max int) string {
	compact := strings.Join(strings.Fields(htmlUnescape(text)), " ")
	if len(compact) > max {
		return compact[:max]
	}
	return compact
}

func htmlUnescape(text string) string {
	replacer := strings.NewReplacer("&amp;", "&", "&lt;", "<", "&gt;", ">", "&quot;", "\"", "&#39;", "'")
	return replacer.Replace(text)
}

func sourceHashes(sources []Source) []SourceHash {
	out := []SourceHash{}
	for _, source := range sources {
		canonical := canonicalURL(source.URL)
		data := source.Name + "\x00" + canonical + "\x00" + source.Kind
		out = append(out, SourceHash{Name: source.Name, URL: canonical, Kind: source.Kind, Hash: contentHash([]byte(data))})
	}
	return out
}

func aggregateSourceHash(sources []Source) string {
	hashes := sourceHashes(sources)
	parts := []string{}
	for _, item := range hashes {
		parts = append(parts, item.Hash)
	}
	sort.Strings(parts)
	return contentHash([]byte(strings.Join(parts, "\n")))
}

func archiveStatusCounts(entries []ArchiveEntry) map[string]int {
	counts := map[string]int{}
	for _, entry := range entries {
		status := entry.CaptureStatus
		if status == "" {
			status = "unknown"
		}
		counts[status]++
	}
	return counts
}

func archiveErrorCounts(entries []ArchiveEntry, events []ArchiveDiscoveryEvent) map[string]int {
	counts := map[string]int{}
	for _, entry := range entries {
		if entry.ErrorClass != "" {
			counts[entry.ErrorClass]++
		}
	}
	for _, event := range events {
		if event.ErrorClass != "" {
			counts[event.ErrorClass]++
		}
	}
	return counts
}

func validateArchiveReplay(entries []ArchiveEntry, indexPath string, indexHash string) ReplayValidation {
	validation := ReplayValidation{Status: "passed"}
	if indexHash == "" {
		validation.Status = "failed"
		validation.Errors = append(validation.Errors, "missing_archive_index_hash")
	}
	if indexPath != "" {
		if hash, err := fileSHA256(indexPath); err != nil {
			validation.Status = "failed"
			validation.Errors = append(validation.Errors, err.Error())
		} else if indexHash != "" && hash != indexHash {
			validation.Status = "failed"
			validation.Errors = append(validation.Errors, "archive_index_hash_mismatch")
		}
	}
	for _, entry := range entries {
		if entry.CaptureStatus != CaptureCaptured && entry.CaptureStatus != CaptureTruncated {
			continue
		}
		if entry.BodyPath == "" {
			validation.Status = "failed"
			validation.Errors = append(validation.Errors, entry.CanonicalURL+": missing body_path")
			continue
		}
		data, err := os.ReadFile(entry.BodyPath)
		if err != nil {
			validation.Status = "failed"
			validation.Errors = append(validation.Errors, entry.CanonicalURL+": "+err.Error())
			continue
		}
		if contentHash(data) != entry.ContentHash {
			validation.Status = "failed"
			validation.Errors = append(validation.Errors, entry.CanonicalURL+": body hash mismatch")
		}
		if entry.ReceiptPath == "" {
			validation.Status = "failed"
			validation.Errors = append(validation.Errors, entry.CanonicalURL+": missing receipt_path")
		} else if _, err := os.Stat(entry.ReceiptPath); err != nil {
			validation.Status = "failed"
			validation.Errors = append(validation.Errors, entry.CanonicalURL+": "+err.Error())
		}
	}
	return validation
}

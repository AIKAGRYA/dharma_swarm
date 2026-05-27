package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type multiFlag []string

func (m *multiFlag) String() string { return fmt.Sprint([]string(*m)) }
func (m *multiFlag) Set(value string) error {
	*m = append(*m, value)
	return nil
}

func main() {
	stateDir := flag.String("state-dir", filepath.Join(os.Getenv("HOME"), ".dharma"), "Dharma state directory")
	output := flag.String("output", "", "JSONL output path")
	health := flag.String("health", "", "health JSON output path")
	fetch := flag.Bool("fetch", false, "perform public network fetches")
	archive := flag.Bool("archive", false, "write full-body archive index, payloads, and receipts")
	archiveDir := flag.String("archive-dir", "", "archive output directory")
	archiveMaxBytes := flag.Int64("archive-max-bytes", 2_000_000, "maximum bytes per archived response")
	archiveMaxDepth := flag.Int("archive-max-depth", 0, "maximum same-run link crawl depth")
	archiveMaxPages := flag.Int("archive-max-pages", 100, "maximum archived pages")
	archiveSameDomain := flag.Bool("archive-same-domain", true, "only archive URLs on seed domains")
	archiveRateLimitMS := flag.Int("archive-rate-limit-ms", 100, "minimum per-host delay between archive/discovery fetches")
	archiveRobots := flag.Bool("archive-robots", true, "enforce robots.txt for archive and discovery fetches")
	archiveDefaultCrawlDelayMS := flag.Int("archive-default-crawl-delay-ms", 0, "default per-host crawl delay when robots.txt does not specify one")
	archiveMaxRetries := flag.Int("archive-max-retries", 1, "maximum retry attempts for retryable archive/discovery fetches")
	archiveRetryBaseDelayMS := flag.Int("archive-retry-base-delay-ms", 250, "base retry delay for archive/discovery fetches")
	archiveRetryMaxDelayMS := flag.Int("archive-retry-max-delay-ms", 2000, "maximum retry delay for archive/discovery fetches")
	archiveMaxFetchDurationMS := flag.Int("archive-max-fetch-duration-ms", 30000, "maximum total fetch duration per archive/discovery URL")
	archiveWorkers := flag.Int("archive-workers", 6, "concurrent archive fetch workers")
	archiveDiscoverLLMS := flag.Bool("archive-discover-llms", false, "add /llms.txt and /llms-full.txt discovery URLs for seed domains")
	archiveDiscoverSitemap := flag.Bool("archive-discover-sitemap", false, "discover archive URLs from robots.txt sitemap declarations or /sitemap.xml")
	archiveSitemapMaxURLs := flag.Int("archive-sitemap-max-urls", 100, "maximum sitemap URLs to add per archive run")
	cascadeFor := flag.String("cascade-for", "", "movement id for cascade observations")
	var queries multiFlag
	var queryURLs multiFlag
	var queryURLFiles multiFlag
	var archiveInclude multiFlag
	var archiveExclude multiFlag
	flag.Var(&queries, "query", "cascade query to scan; repeatable")
	flag.Var(&queryURLs, "query-url", "explicit public URL to fetch/archive; repeatable")
	flag.Var(&queryURLFiles, "query-url-file", "file containing explicit public URLs, one per line; repeatable")
	flag.Var(&archiveInclude, "archive-include", "substring that archive URLs must include; repeatable")
	flag.Var(&archiveExclude, "archive-exclude", "substring that archive URLs must exclude; repeatable")
	flag.Parse()

	outPath := *output
	if outPath == "" {
		outPath = filepath.Join(*stateDir, "meta", "world_radar", "world_scout_observations.jsonl")
	}
	healthPath := *health
	if healthPath == "" {
		healthPath = filepath.Join(*stateDir, "meta", "world_radar", "world_scout_health.json")
	}

	result := ScoutResult{FetchEnabled: *fetch}
	var observations []Observation
	var err error
	runID := "world_scout_archive_" + stableID(strings.Join(os.Args[1:], "\x00")+time.Now().UTC().Format(time.RFC3339Nano))
	if *fetch {
		scoutSources, archiveSources, sourceErrors := resolveRunSources(*stateDir, []string(queries), *cascadeFor, []string(queryURLs), []string(queryURLFiles), *archive)
		if len(scoutSources) > 0 {
			observations, result, err = FetchSources(scoutSources)
			result.Errors = append(sourceErrors, result.Errors...)
			if err != nil {
				result.Errors = append(result.Errors, err.Error())
			}
		} else {
			result = ScoutResult{FetchEnabled: true}
			result.Errors = append(result.Errors, sourceErrors...)
		}
		if *archive {
			archiveResult := ArchiveSources(archiveSources, ArchiveOptions{
				StateDir: *stateDir, ArchiveDir: *archiveDir, MaxBytes: *archiveMaxBytes,
				MaxDepth: *archiveMaxDepth, MaxPages: *archiveMaxPages, SameDomain: *archiveSameDomain,
				RateLimitMS: *archiveRateLimitMS, Include: []string(archiveInclude), Exclude: []string(archiveExclude),
				Correlation: "world_scout_archive", Workers: *archiveWorkers,
				DiscoverLLMS: *archiveDiscoverLLMS, DiscoverSitemap: *archiveDiscoverSitemap,
				SitemapMaxURLs: *archiveSitemapMaxURLs, RunID: runID, ToolVersion: archiveToolVersion, Args: os.Args[1:],
				RobotsEnabled: *archiveRobots, RobotsDisabled: !*archiveRobots,
				DefaultCrawlDelayMS: *archiveDefaultCrawlDelayMS, MaxRetries: *archiveMaxRetries,
				RetryBaseDelayMS: *archiveRetryBaseDelayMS, RetryMaxDelayMS: *archiveRetryMaxDelayMS,
				MaxFetchDurationMS: *archiveMaxFetchDurationMS,
			})
			result.ArchiveEnabled = true
			result.ArchiveCount = archiveResult.ArchiveCount
			result.DedupeCount = archiveResult.DedupeCount
			result.ArchiveDir = archiveResult.ArchiveDir
			result.ArchiveIndexPath = archiveResult.IndexPath
			result.ArchiveManifestPath = archiveResult.ManifestPath
			result.ArchiveDiscoveredCount = archiveResult.DiscoveredCount
			result.ArchiveWorkers = archiveResult.WorkerCount
			result.ArchiveTotalBytes = archiveResult.TotalBytes
			result.ArchiveErrorCount = len(archiveResult.Errors)
			result.Errors = append(result.Errors, archiveResult.Errors...)
		}
	} else {
		result.Errors = append(result.Errors, "fetch disabled; set --fetch to scan public sources")
	}

	if err := writeJSONL(outPath, observations); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	result.ObservationCount = len(observations)
	if err := writeHealth(healthPath, result); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if len(result.Errors) > 0 && *fetch {
		fmt.Fprintf(os.Stderr, "world scout completed with errors: %v\n", result.Errors)
	}
}

func resolveRunSources(stateDir string, queries []string, cascadeFor string, queryURLs []string, queryURLFiles []string, archive bool) ([]Source, []Source, []string) {
	baseSources := LoadSources(stateDir)
	if len(queries) > 0 {
		baseSources = SourcesForQueries(queries, cascadeFor)
	}
	scoutSources := baseSources
	archiveSources := baseSources
	errors := []string{}
	allQueryURLs := append([]string{}, queryURLs...)
	fileURLs, fileErr := URLsFromFiles(queryURLFiles)
	if fileErr != nil {
		errors = append(errors, fileErr.Error())
	}
	allQueryURLs = append(allQueryURLs, fileURLs...)
	if len(allQueryURLs) == 0 {
		return scoutSources, archiveSources, errors
	}
	directSources := SourcesForURLs(allQueryURLs, cascadeFor)
	if archive {
		archiveSources = directSources
		if len(queries) == 0 {
			scoutSources = nil
		}
	} else {
		scoutSources = directSources
		archiveSources = directSources
	}
	return scoutSources, archiveSources, errors
}

func writeJSONL(path string, observations []Observation) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	file, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".*.tmp")
	if err != nil {
		return err
	}
	tmpName := file.Name()
	defer os.Remove(tmpName)
	enc := json.NewEncoder(file)
	for _, obs := range observations {
		if err := enc.Encode(obs); err != nil {
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
	return os.Rename(tmpName, path)
}

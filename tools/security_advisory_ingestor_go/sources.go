package main

import (
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/sourceprobe"
)

const (
	SourceName   = "security_advisory_ingestor_go"
	SourceURL    = "local://security-advisory-inventory"
	IngestSchema = "security_advisory_inventory.v0"
)

func TrustEnvelope() *receipt.TrustEnvelope {
	return &receipt.TrustEnvelope{
		OriginAttestation:      "mixed_unsigned_and_platform_curated",
		CorroborationCount:     1,
		FreshnessWindow:        "24h",
		LicenseCompatibility:   "mixed_review_required",
		HallucinationRiskClass: "raw_data",
		RoutingClass:           "review",
		HumanReviewRequired:    true,
	}
}

func DefaultSources() []sourceprobe.SourceDefinition {
	return []sourceprobe.SourceDefinition{
		{
			ID:                     "cisa_kev",
			Title:                  "CISA Known Exploited Vulnerabilities Catalog",
			URL:                    "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
			Kind:                   "json_feed",
			Publisher:              "CISA",
			TopicTags:              []string{"security", "kev", "exploited_vulnerabilities"},
			LicenseCompatibility:   "open_government_data_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "unsigned",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "go_vuln_db_index",
			Title:                  "Go Vulnerability Database Index",
			URL:                    "https://vuln.go.dev/index/vulns.json",
			Kind:                   "json_feed",
			Publisher:              "Go Security Team",
			TopicTags:              []string{"security", "go", "vulnerability_database"},
			LicenseCompatibility:   "open_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "unsigned",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "github_global_advisories",
			Title:                  "GitHub Global Security Advisories",
			URL:                    "https://api.github.com/advisories?per_page=100&sort=updated&direction=desc",
			Kind:                   "json_feed",
			Publisher:              "GitHub Advisory Database",
			TopicTags:              []string{"security", "github", "supply_chain"},
			LicenseCompatibility:   "mixed_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "platform_curated",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "osv_api_docs",
			Title:                  "OSV API Metadata",
			URL:                    "https://google.github.io/osv.dev/api/",
			Kind:                   "html_doc",
			Publisher:              "OSV",
			TopicTags:              []string{"security", "osv", "supply_chain"},
			LicenseCompatibility:   "open_review_required",
			FreshnessWindow:        "7d",
			OriginAttestation:      "unsigned",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			HumanReviewRequired:    true,
		},
	}
}

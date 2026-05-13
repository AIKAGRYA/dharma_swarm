package main

import (
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/sourceprobe"
)

const (
	SourceName   = "practitioner_signal_ingestor_go"
	SourceURL    = "local://practitioner-signal-inventory"
	IngestSchema = "practitioner_signal_inventory.v0"
)

func TrustEnvelope() *receipt.TrustEnvelope {
	return &receipt.TrustEnvelope{
		OriginAttestation:      "mixed_social_and_commentary_unsigned",
		CorroborationCount:     0,
		FreshnessWindow:        "24h",
		LicenseCompatibility:   "mixed_review_required",
		HallucinationRiskClass: "commentary",
		RoutingClass:           "human_only",
		SocialRaw:              true,
		HumanReviewRequired:    true,
	}
}

func DefaultSources() []sourceprobe.SourceDefinition {
	return []sourceprobe.SourceDefinition{
		{
			ID:                     "hacker_news_ai",
			Title:                  "Hacker News AI Search",
			URL:                    "https://hn.algolia.com/api/v1/search_by_date?query=ai&tags=story&hitsPerPage=25",
			Kind:                   "json_feed",
			Publisher:              "HN Algolia",
			TopicTags:              []string{"social", "practitioner", "ai"},
			LicenseCompatibility:   "social_terms_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "anonymous_or_pseudonymous",
			HallucinationRiskClass: "commentary",
			RoutingClass:           "human_only",
			CorroborationCount:     0,
			SocialRaw:              true,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "reddit_localllama",
			Title:                  "Reddit LocalLLaMA Top Daily",
			URL:                    "https://www.reddit.com/r/LocalLLaMA/top.json?t=day&limit=25",
			Kind:                   "json_feed",
			Publisher:              "Reddit",
			TopicTags:              []string{"social", "local_models", "open_weight"},
			LicenseCompatibility:   "social_terms_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "anonymous_or_pseudonymous",
			HallucinationRiskClass: "commentary",
			RoutingClass:           "human_only",
			CorroborationCount:     0,
			SocialRaw:              true,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "github_trending_ai",
			Title:                  "GitHub AI Repository Search",
			URL:                    "https://api.github.com/search/repositories?q=topic:artificial-intelligence&sort=updated&order=desc&per_page=25",
			Kind:                   "json_feed",
			Publisher:              "GitHub",
			TopicTags:              []string{"repos", "open_source", "ai"},
			LicenseCompatibility:   "repo_license_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "platform_curated",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "simon_willison_weblog",
			Title:                  "Simon Willison Weblog",
			URL:                    "https://simonwillison.net/atom/everything/",
			Kind:                   "atom_feed",
			Publisher:              "Simon Willison",
			TopicTags:              []string{"practitioner", "llm", "engineering"},
			LicenseCompatibility:   "web_content_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "self_reported",
			HallucinationRiskClass: "commentary",
			RoutingClass:           "human_only",
			CorroborationCount:     0,
			ClaimsSelfReported:     true,
			SocialRaw:              true,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "latent_space_podcast",
			Title:                  "Latent Space",
			URL:                    "https://www.latent.space/feed",
			Kind:                   "rss_feed",
			Publisher:              "Latent Space",
			TopicTags:              []string{"practitioner", "podcast", "ai"},
			LicenseCompatibility:   "show_notes_review_required",
			FreshnessWindow:        "7d",
			OriginAttestation:      "self_reported",
			HallucinationRiskClass: "commentary",
			RoutingClass:           "human_only",
			CorroborationCount:     0,
			ClaimsSelfReported:     true,
			SocialRaw:              true,
			HumanReviewRequired:    true,
		},
	}
}

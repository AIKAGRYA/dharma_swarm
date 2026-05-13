package main

import (
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/sourceprobe"
)

const (
	SourceName   = "ai_frontier_ingestor_go"
	SourceURL    = "local://ai-frontier-inventory"
	IngestSchema = "ai_frontier_inventory.v0"
)

func TrustEnvelope() *receipt.TrustEnvelope {
	return &receipt.TrustEnvelope{
		OriginAttestation:      "mixed_vendor_and_research_unsigned",
		CorroborationCount:     1,
		FreshnessWindow:        "24h",
		LicenseCompatibility:   "mixed_review_required",
		HallucinationRiskClass: "raw_data",
		RoutingClass:           "review",
		ClaimsSelfReported:     true,
		HumanReviewRequired:    true,
	}
}

func DefaultSources() []sourceprobe.SourceDefinition {
	return []sourceprobe.SourceDefinition{
		{
			ID:                     "arxiv_rv_alignment_query",
			Title:                  "arXiv R_V Alignment Query",
			URL:                    "https://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+AND+all:alignment&sortBy=submittedDate&sortOrder=descending&max_results=20",
			Kind:                   "atom_feed",
			Publisher:              "arXiv",
			TopicTags:              []string{"research", "alignment", "rv"},
			LicenseCompatibility:   "paper_license_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "unsigned",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "transformer_circuits",
			Title:                  "Transformer Circuits",
			URL:                    "https://transformer-circuits.pub/",
			Kind:                   "html_index",
			Publisher:              "Transformer Circuits",
			TopicTags:              []string{"research", "mechanistic_interpretability"},
			LicenseCompatibility:   "web_content_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "unsigned",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "openai_news",
			Title:                  "OpenAI News",
			URL:                    "https://openai.com/news/rss.xml",
			Kind:                   "rss_feed",
			Publisher:              "OpenAI",
			TopicTags:              []string{"vendor", "models", "docs"},
			LicenseCompatibility:   "vendor_terms_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "self_reported",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			ClaimsSelfReported:     true,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "anthropic_news",
			Title:                  "Anthropic News",
			URL:                    "https://www.anthropic.com/news/rss.xml",
			Kind:                   "rss_feed",
			Publisher:              "Anthropic",
			TopicTags:              []string{"vendor", "models", "research"},
			LicenseCompatibility:   "vendor_terms_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "self_reported",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			ClaimsSelfReported:     true,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "hugging_face_papers",
			Title:                  "Hugging Face Papers",
			URL:                    "https://huggingface.co/papers/rss",
			Kind:                   "rss_feed",
			Publisher:              "Hugging Face",
			TopicTags:              []string{"models", "papers", "open_weight"},
			LicenseCompatibility:   "mixed_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "platform_curated",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "nvidia_ai_blog",
			Title:                  "NVIDIA AI Blog",
			URL:                    "https://developer.nvidia.com/blog/category/generative-ai/feed/",
			Kind:                   "rss_feed",
			Publisher:              "NVIDIA",
			TopicTags:              []string{"vendor", "gpu", "models", "serving"},
			LicenseCompatibility:   "vendor_terms_review_required",
			FreshnessWindow:        "24h",
			OriginAttestation:      "self_reported",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "review",
			CorroborationCount:     1,
			ClaimsSelfReported:     true,
			HumanReviewRequired:    true,
		},
	}
}

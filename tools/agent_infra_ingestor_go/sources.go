package main

import (
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/sourceprobe"
)

const (
	SourceName   = "agent_infra_ingestor_go"
	SourceURL    = "local://agent-infra-inventory"
	IngestSchema = "agent_infra_inventory.v0"
)

func TrustEnvelope() *receipt.TrustEnvelope {
	return &receipt.TrustEnvelope{
		OriginAttestation:      "mixed_registry_and_vendor_unsigned",
		CorroborationCount:     1,
		FreshnessWindow:        "7d",
		LicenseCompatibility:   "mixed_review_required",
		HallucinationRiskClass: "raw_data",
		RoutingClass:           "human_only",
		ClaimsSelfReported:     true,
		HumanReviewRequired:    true,
	}
}

func DefaultSources() []sourceprobe.SourceDefinition {
	return []sourceprobe.SourceDefinition{
		{
			ID:                     "mcp_docs",
			Title:                  "Model Context Protocol Documentation",
			URL:                    "https://modelcontextprotocol.io/introduction",
			Kind:                   "html_doc",
			Publisher:              "Model Context Protocol",
			TopicTags:              []string{"mcp", "agents", "tools"},
			LicenseCompatibility:   "web_content_review_required",
			FreshnessWindow:        "7d",
			OriginAttestation:      "self_reported",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "human_only",
			CorroborationCount:     1,
			ClaimsSelfReported:     true,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "mcp_registry_repo",
			Title:                  "MCP Registry Repository",
			URL:                    "https://api.github.com/repos/modelcontextprotocol/registry",
			Kind:                   "github_repo_metadata",
			Publisher:              "Model Context Protocol",
			TopicTags:              []string{"mcp", "registry", "supply_chain"},
			LicenseCompatibility:   "repo_license_review_required",
			FreshnessWindow:        "7d",
			OriginAttestation:      "platform_curated",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "human_only",
			CorroborationCount:     1,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "a2a_protocol_repo",
			Title:                  "Agent2Agent Protocol Repository",
			URL:                    "https://api.github.com/repos/a2aproject/A2A",
			Kind:                   "github_repo_metadata",
			Publisher:              "A2A Project",
			TopicTags:              []string{"a2a", "agents", "protocol"},
			LicenseCompatibility:   "repo_license_review_required",
			FreshnessWindow:        "7d",
			OriginAttestation:      "platform_curated",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "human_only",
			CorroborationCount:     1,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "langgraph_durable_execution",
			Title:                  "LangGraph Durable Execution Documentation",
			URL:                    "https://docs.langchain.com/oss/python/langgraph/durable-execution",
			Kind:                   "html_doc",
			Publisher:              "LangChain",
			TopicTags:              []string{"agents", "durable_execution", "hitl"},
			LicenseCompatibility:   "vendor_terms_review_required",
			FreshnessWindow:        "7d",
			OriginAttestation:      "self_reported",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "human_only",
			CorroborationCount:     1,
			ClaimsSelfReported:     true,
			HumanReviewRequired:    true,
		},
		{
			ID:                     "openai_agents_docs",
			Title:                  "OpenAI Agents SDK Documentation",
			URL:                    "https://openai.github.io/openai-agents-python/",
			Kind:                   "html_doc",
			Publisher:              "OpenAI",
			TopicTags:              []string{"agents", "sdk", "tools"},
			LicenseCompatibility:   "vendor_terms_review_required",
			FreshnessWindow:        "7d",
			OriginAttestation:      "self_reported",
			HallucinationRiskClass: "raw_data",
			RoutingClass:           "human_only",
			CorroborationCount:     1,
			ClaimsSelfReported:     true,
			HumanReviewRequired:    true,
		},
	}
}

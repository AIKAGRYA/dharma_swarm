#!/usr/bin/env bash
# install_command_plane_stack.sh
#
# Installs the MCP servers required by docs/plans/COMMAND_PLANE_MULTIAGENT_PROTOCOL.md
# for the command-plane-redesign-2026-05 queued track.
#
# Idempotent. `claude mcp add` warns on duplicates but does not error.
# Run once per machine. Re-run safely after a `claude` upgrade.
#
# Requirements:
#   - claude >= 2.1.111 (for /goal, /ultraplan, /ultrareview built-ins)
#   - Node 20+ (for npx stdio MCPs)
#   - Network access for OAuth flows on first /mcp authentication
#
# After this script:
#   1. In Claude Code, run /mcp
#   2. Click each HTTP MCP that says "Needs authentication" and complete OAuth
#   3. Verify with: claude mcp list | grep -E "Connected|authentication"

set -u  # do not set -e — claude mcp add returns nonzero on duplicate; we want to continue

VERSION="1.0.0"
TRACK="command-plane-redesign-2026-05"

echo "════════════════════════════════════════════════════════════════"
echo "  Command-Plane Stack Installer v${VERSION}"
echo "  Track: ${TRACK} (queued)"
echo "════════════════════════════════════════════════════════════════"
echo

# ----------------------------------------------------------------------
# Safety: remove archived/CVE-flagged MCPs
# ----------------------------------------------------------------------
echo "▶ Safety pass: removing archived/CVE-flagged MCPs"
if claude mcp list 2>/dev/null | grep -q "^puppeteer:"; then
    echo "  · removing puppeteer (archived, open SSRF/sandbox-bypass advisories)"
    claude mcp remove puppeteer 2>&1 | tail -1
else
    echo "  · puppeteer not present ✓"
fi
echo

# ----------------------------------------------------------------------
# Priority-5 MCPs (from docs/plans/2026-05-21-command-plane-design-lock.md §V)
# ----------------------------------------------------------------------
echo "▶ Priority-5 MCPs (component, design, deploy, errors, project mgmt)"

add_stdio() {
    local name="$1"; shift
    echo "  · ${name}"
    claude mcp add "${name}" -- "$@" 2>&1 | tail -1
}

add_http() {
    local name="$1"; shift
    local url="$1"; shift
    echo "  · ${name} (HTTP, requires OAuth)"
    claude mcp add --transport http "${name}" "${url}" 2>&1 | tail -1
}

add_stdio  shadcn  npx -y shadcn@latest registry mcp
add_http   figma   https://mcp.figma.com/mcp
add_http   vercel  https://mcp.vercel.com
add_http   sentry  https://mcp.sentry.dev/mcp
add_http   linear  https://mcp.linear.app/mcp
echo

# ----------------------------------------------------------------------
# Phase 2 MCPs (added when cockpit moves toward Palantir-grade)
# ----------------------------------------------------------------------
echo "▶ Phase 2 MCPs (design-system intelligence, analytics)"
add_http  builder  https://mcp.builder.io/dsi
add_http  posthog  https://mcp.posthog.com/sse
echo

# ----------------------------------------------------------------------
# Foundation MCPs (the universal 10 — recommended for any project)
# ----------------------------------------------------------------------
echo "▶ Foundation MCPs (always-useful)"
add_stdio  playwright          npx -y @playwright/mcp@latest
add_stdio  context7            npx -y @upstash/context7-mcp@latest
add_stdio  tavily              npx -y tavily-mcp@latest
add_stdio  filesystem          npx -y @modelcontextprotocol/server-filesystem /Users/dhyana/dharma_swarm
add_stdio  github              npx -y @modelcontextprotocol/server-github
add_stdio  sequential-thinking npx -y @modelcontextprotocol/server-sequential-thinking
add_stdio  memory              npx -y @modelcontextprotocol/server-memory
add_stdio  fetch               npx -y @modelcontextprotocol/server-fetch
echo

# ----------------------------------------------------------------------
# Status report
# ----------------------------------------------------------------------
echo "════════════════════════════════════════════════════════════════"
echo "  Status"
echo "════════════════════════════════════════════════════════════════"
CONNECTED=$(claude mcp list 2>/dev/null | grep -c "✓ Connected" || echo 0)
NEEDS_AUTH=$(claude mcp list 2>/dev/null | grep -c "Needs authentication" || echo 0)
FAILED=$(claude mcp list 2>/dev/null | grep -c "✗" || echo 0)

echo "  Connected:      ${CONNECTED}"
echo "  Needs OAuth:    ${NEEDS_AUTH}"
echo "  Failed:         ${FAILED}"
echo
echo "▶ Next steps:"
echo "  1. In Claude Code: type /mcp"
echo "  2. Click each MCP that says 'Needs authentication' and complete OAuth"
echo "  3. Verify all green: claude mcp list | grep -E 'Connected|authentication'"
echo
echo "▶ Required Claude Code built-ins (no install needed):"
echo "  /goal        — set completion condition, work across turns until met"
echo "  /agents      — manage subagents/teams"
echo "  /ultraplan   — refine plan with remote-agent (in plan mode)"
echo "  /ultrareview — multi-agent cloud code review (bills Agent SDK pool)"
echo
echo "▶ Documentation:"
echo "  · Spec:      docs/plans/2026-05-21-command-plane-design-lock.md"
echo "  · Vision:    docs/plans/COMMAND_PLANE_VISION.md"
echo "  · Checklist: docs/plans/COMMAND_PLANE_CHECKLIST.md"
echo "  · Protocol:  docs/plans/COMMAND_PLANE_MULTIAGENT_PROTOCOL.md"
echo

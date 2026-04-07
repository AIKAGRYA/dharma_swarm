# DHARMA_VERIFY GitHub App - MVP Technical Specification

**Version:** 1.0  
**Date:** 2026-03-27  
**Status:** Technical Audit Complete - Ready for Implementation

---

## Executive Summary

The dharma_swarm codebase has a **functioning code review system** (dharma_verify) that can be exposed as a GitHub App with **minimal new code**. The existing infrastructure provides:

- ✅ Heuristic diff scoring (6 dimensions: correctness, clarity, safety, completeness, efficiency, governance)
- ✅ LLM-enhanced scoring with fallback
- ✅ GitHub-compatible markdown report generation
- ✅ FastAPI API with webhook endpoints
- ✅ Comprehensive test coverage
- ⚠️ Missing: GitHub API integration for posting comments
- ⚠️ Missing: Installation token management
- ⚠️ Missing: Dashboard UI for billing/plans

**Time to MVP: 3-5 days of focused development**

---

## 1. What Already Works TODAY

### 1.1 Existing Code Review Engine (`dharma_swarm/verify/`)

| Component | Status | Description |
|-----------|--------|-------------|
| `scorer.py` | ✅ Production-ready | Heuristic diff scoring + LLM enhancement with fallback |
| `reviewer.py` | ✅ Production-ready | PR review orchestration with comprehension tracking |
| `reporter.py` | ✅ Production-ready | GitHub-compatible markdown comment formatting |
| `github_app.py` | ⚠️ Partial | Webhook handler skeleton, missing API client |
| `api/routers/verify.py` | ✅ Complete | REST endpoints: `/review`, `/score`, `/stats`, `/webhook` |

### 1.2 Existing API Endpoints

```
POST /api/verify/review    - Review a diff (returns verdict, score, issues, suggestions)
POST /api/verify/score     - Score a diff (returns 6-dimension breakdown)
GET  /api/verify/stats     - Review statistics (count, avg score, comprehension debt)
POST /api/verify/webhook   - GitHub webhook receiver (HMAC verified)
GET  /api/verify/health    - Health check
```

### 1.3 Existing Scoring Dimensions (Immediate Value)

The heuristic scorer ALREADY detects:

- **Safety Issues:** `eval()`, `exec()`, hardcoded secrets, subprocess calls
- **Governance Violations:** Modifications to protected files (telos_gates.py)
- **Correctness:** Test coverage presence, error handling patterns
- **Clarity:** Docstrings, type hints, naming conventions
- **Completeness:** TODO/FIXME markers, incomplete implementations
- **Efficiency:** Nested loops, obvious performance anti-patterns

**Example output:**
```json
{
  "overall": 0.68,
  "dimensions": {
    "correctness": 0.5,
    "clarity": 0.8,
    "safety": 1.0,
    "completeness": 0.33,
    "efficiency": 0.8,
    "governance": 1.0
  },
  "issues": ["No tests accompany this change", "Contains eval() call"],
  "suggestions": ["Add tests covering new code paths"]
}
```

---

## 2. What's Missing for GitHub App MVP

### 2.1 Critical Path (Must Have for Charging)

| Component | Effort | Risk |
|-----------|--------|------|
| GitHub App registration & manifest | 2 hrs | Low |
| Installation token exchange | 4 hrs | Medium |
| PR comment posting | 4 hrs | Low |
| Diff fetching from GitHub API | 4 hrs | Low |
| Rate limiting / quota enforcement | 8 hrs | Medium |
| Database for usage tracking | 6 hrs | Low |
| Basic dashboard (read-only stats) | 8 hrs | Low |

**Total Critical Path: ~36 hours (4-5 days)**

### 2.2 Post-MVP (Can Defer)

| Component | Effort | Deferred To |
|-----------|--------|-------------|
| Billing integration (Stripe) | 16 hrs | v1.1 |
| Tiered pricing enforcement | 8 hrs | v1.1 |
| Team/organization management | 12 hrs | v1.2 |
| Advanced dashboard UI | 24 hrs | v1.2 |
| Custom rule configuration | 16 hrs | v1.3 |
| LLM model selection | 8 hrs | v1.3 |

---

## 3. Technical Architecture

### 3.1 GitHub App Permissions Required

```yaml
# GitHub App Settings
name: Dharma Verify
url: https://verify.dharma.swarm
webhook_url: https://api.dharma.swarm/api/verify/webhook

permissions:
  pull_requests: read        # Access PR metadata
  contents: read             # Access diff content
  issues: write              # Post PR review comments
  checks: write              # Post check runs (optional v2)
  metadata: read             # Basic repo info

events:
  - pull_request             # PR opened, synchronized, closed
  - pull_request_review      # Review submitted (optional)
  - installation             # App installed/uninstalled
```

### 3.2 Webhook Handler Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  GitHub Webhook │────▶│  Signature      │────▶│  Event Router   │
│  (POST)         │     │  Verification   │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
        ┌────────────────┬───────────────┬───────────────┘
        ▼                ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  PR Opened   │ │  PR Updated  │ │  Installation│
│  (synchronize│ │  (new commit)│ │  (setup DB)  │
└──────┬───────┘ └──────┬───────┘ └──────────────┘
       │                │
       ▼                ▼
┌──────────────────────────────────────────────┐
│ 1. Fetch diff from GitHub API                │
│ 2. Run heuristic scorer                      │
│ 3. Run LLM scorer (if enabled for account)   │
│ 4. Generate review comment                   │
│ 5. Post to PR via GitHub API                 │
│ 6. Log usage to database                     │
└──────────────────────────────────────────────┘
```

### 3.3 Database Schema (Minimal)

```sql
-- Installations
create table github_installations (
    id bigint primary key,
    account_login text not null,
    account_type text not null,  -- 'User' or 'Organization'
    sender_id bigint,            -- Who installed it
    created_at timestamptz default now(),
    plan_tier text default 'free',  -- free, pro, enterprise
    monthly_quota integer default 100,
    quota_reset_at timestamptz default now()
);

-- Usage tracking
create table review_usage (
    id serial primary key,
    installation_id bigint references github_installations(id),
    repository text not null,
    pr_number integer not null,
    commit_sha text,
    score_overall float,
    comprehension_debt float,
    verdict text,
    created_at timestamptz default now()
);

-- Create unique index for idempotency
create unique index idx_review_usage_unique 
on review_usage(installation_id, repository, pr_number, commit_sha);
```

### 3.4 API Integration Points

```python
# GitHub API Client (NEW - needs implementation)
class GitHubAPIClient:
    """Installation token-based GitHub API client."""
    
    async def get_installation_token(self, installation_id: int) -> str:
        """Exchange JWT for installation token."""
        
    async def fetch_diff(self, repo: str, pr_number: int) -> str:
        """Fetch PR diff from GitHub API."""
        
    async def post_review_comment(
        self, 
        repo: str, 
        pr_number: int, 
        body: str,
        commit_id: str,
        event: str = "COMMENT"  # or "APPROVE", "REQUEST_CHANGES"
    ) -> dict:
        """Post PR review comment."""

# Rate Limiter (NEW - needs implementation)        
class RateLimiter:
    """Enforce per-installation monthly quotas."""
    
    async def check_quota(self, installation_id: int) -> bool:
        """Check if installation has remaining quota."""
        
    async def record_usage(self, installation_id: int, pr_number: int) -> None:
        """Record a review in usage tracking."""
```

---

## 4. Implementation Plan

### Phase 1: Core GitHub Integration (Day 1-2)

**Day 1 - Morning (4 hrs):**
- [ ] Create `dharma_swarm/verify/github_api.py` - JWT + installation token client
- [ ] Implement `fetch_diff()` from GitHub API
- [ ] Implement `post_review_comment()` to GitHub API

**Day 1 - Afternoon (4 hrs):**
- [ ] Update `github_app.py` webhook handler to use real GitHub API
- [ ] Add installation token caching (Redis or in-memory)
- [ ] Test with GitHub App in dev mode

**Day 2 - Morning (4 hrs):**
- [ ] Create database schema for installations and usage
- [ ] Implement `RateLimiter` class
- [ ] Add quota enforcement to webhook flow

**Day 2 - Afternoon (4 hrs):**
- [ ] Create GitHub App manifest and register
- [ ] Configure webhook URL and permissions
- [ ] End-to-end test: PR opened → review posted

### Phase 2: Dashboard & Monitoring (Day 3-4)

**Day 3:**
- [ ] Create minimal dashboard page (`/dashboard/verify`)
- [ ] Display installation list
- [ ] Display usage statistics
- [ ] Add health check for webhook endpoint

**Day 4:**
- [ ] Add error handling and retries for GitHub API
- [ ] Implement webhook idempotency (skip duplicate events)
- [ ] Add logging for debugging
- [ ] Performance optimization (async where possible)

### Phase 3: Polish & Launch Prep (Day 5)

- [ ] Add documentation for users
- [ ] Create GitHub App listing content
- [ ] Set up monitoring alerts
- [ ] Test with real repositories
- [ ] Soft launch to beta users

---

## 5. Technical Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| GitHub API rate limits | Medium | High | Implement caching, respect headers, exponential backoff |
| LLM API costs | Medium | High | Default to heuristic-only for free tier; LLM for paid only |
| Webhook delivery failures | Low | Medium | Implement retry logic; expose manual trigger API |
| Token storage security | Low | High | Use encrypted at-rest; short-lived tokens only |
| Installation token expiry | Medium | Low | Auto-refresh 5 min before expiry |
| Database performance | Low | Medium | Start with SQLite/Postgres; add indices; shard if needed |

---

## 6. 3-Day vs 3-Week Split

### What Ships in 3 Days (MVP)

✅ **Day 1-2: Core Integration**
- GitHub App webhook receiving PR events
- Automatic diff fetching from GitHub API
- Heuristic scoring (no LLM costs)
- Review comments posted to PRs
- Basic quota enforcement (100 reviews/month free)

✅ **Day 3: Dashboard**
- Simple stats page showing usage
- Health check endpoint
- Installation list

**Value Proposition:** "Free AI code review for every PR - safety checks, style guidance, and governance enforcement."

### What Requires 3 Weeks (v1.0)

- Stripe billing integration ($19/mo Pro, $99/mo Team)
- LLM-enhanced scoring for paid tiers
- Custom rule configuration per repo
- Check runs (GitHub Checks API)
- Team management and permissions
- Advanced analytics dashboard
- Slack/Discord notifications

---

## 7. Code Changes Required

### New Files (~400 lines)

```
dharma_swarm/verify/github_api.py      # ~150 lines - GitHub API client
dharma_swarm/verify/rate_limiter.py    # ~100 lines - Quota enforcement
api/routers/billing.py                 # ~150 lines - Stripe webhooks (v2)
```

### Modified Files (~200 lines)

```
dharma_swarm/verify/github_app.py      # +100 lines - Integrate real API
api/routers/verify.py                  # +50 lines  - Add installation lookup
api/models.py                          # +50 lines  - Add billing models
```

### Configuration Changes

```bash
# Environment variables to add
export GITHUB_APP_ID=""
export GITHUB_APP_PRIVATE_KEY=""  # PEM format
export GITHUB_WEBHOOK_SECRET=""
export DATABASE_URL="postgresql://..."  # or sqlite
export FREE_TIER_MONTHLY_LIMIT=100
export LLM_ENABLED_FOR_FREE=false
```

---

## 8. Pricing Model (Technical Implications)

| Tier | Monthly Limit | Scoring | Price |
|------|--------------|---------|-------|
| **Free** | 100 PRs | Heuristic only | $0 |
| **Pro** | 500 PRs | Heuristic + LLM | $19/mo |
| **Team** | Unlimited | Heuristic + LLM + Custom rules | $99/mo |

**Technical enforcement:**
- Free tier: Skip LLM scorer, enforce limit in `RateLimiter`
- Pro tier: Enable LLM scorer, enforce limit, Stripe subscription check
- Team tier: No limits, all features enabled

---

## 9. Success Metrics

**Week 1 Targets:**
- 10 GitHub App installations
- 50 PRs reviewed
- Zero webhook failures

**Month 1 Targets:**
- 100 installations
- 1000 PRs reviewed
- 5% conversion to paid

---

## 10. Appendix: Existing Test Coverage

The codebase has comprehensive tests that reduce MVP risk:

```
tests/test_verify_api.py       - 12 test cases covering webhooks, scoring, error handling
tests/test_verify_scorer.py    - 15 test cases for heuristic scoring
tests/test_verify_reviewer.py  - 8 test cases for review orchestration
tests/test_verify_reporter.py  - 6 test cases for markdown formatting
```

**Confidence:** The core scoring engine is battle-tested. New code is primarily integration glue.

---

## Summary

The dharma_swarm codebase provides a **solid foundation** for a GitHub App MVP:

1. **Scoring engine:** ✅ Production-ready
2. **API framework:** ✅ FastAPI with tests
3. **Report formatting:** ✅ GitHub-compatible markdown
4. **Webhook handling:** ⚠️ Skeleton exists, needs GitHub API integration

**The 3-day MVP is achievable** because:
- Most of the "hard" AI/scoring code already works
- Only integration glue (GitHub API client, rate limiter) is needed
- Comprehensive test coverage reduces risk
- Dashboard can be minimal for launch

**Key technical decisions:**
- Start with heuristic-only scoring (no LLM costs = sustainable free tier)
- PostgreSQL for usage tracking (can start with SQLite for MVP)
- Async everywhere for webhook responsiveness
- Idempotent webhook processing for reliability

---

*Prepared for: dharma_swarm product team*  
*Next step: Approve MVP scope, allocate 3-5 dev-days, register GitHub App*

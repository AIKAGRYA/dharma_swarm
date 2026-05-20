# Koi Security — ClawHavoc: 341 malicious ClawHub skills

**Source:** https://www.koi.ai/blog/clawhavoc-341-malicious-clawedbot-skills-found-by-the-bot-they-were-targeting
**Discovery vehicle:** Koi's own scanner ("Clawdex")

## Scope
- Audited **2,857 skills** on ClawHub
- Found **341 malicious skills** (~12% of audited set)
- **335 of 341** traced to a single coordinated campaign dubbed **ClawHavoc**

## Tactics
- Skills masqueraded as **cryptocurrency trading automation tools**
- Delivered **Atomic Stealer** (macOS) and equivalent stealers on Windows
- Stole: exchange API keys, wallet private keys, SSH credentials, browser passwords

## Distribution mechanic
- ClawHub is **open by default** — anyone can publish
- Only publisher restriction: a GitHub account at least **one week old**
- Social-engineering layer: "ClickFix-style" prerequisites embedded in skill markdown — user pastes copy-paste install commands into terminal, malware lands

## Detection tooling response
- Koi published a skill called **Clawdex** that scans skills both prior to install AND retroactively on already-installed skills
- Subsequent scans report >800 malicious skills (~20% of registry) as the campaign expanded

## Comparable separate study
**Snyk's ToxicSkills study** (Feb 2026) audited the broader registry: 14,000 skills, found **1,184 malicious** (~8.5% infection rate). This is a different methodology and overlapping/non-overlapping set, but the order of magnitude converges with Koi's findings.

## Disclosure & response
- Disclosed to OpenClaw maintainers
- ClawHub introduced **verified-publisher / skill-vetting / runtime sandboxing** post-incident (per newclawtimes.com)
- However the open-by-default model remains — vetting is opt-in for the "verified" tier

# Simula Research Laboratory — Moltbook risk assessment

URL: https://zenodo.org/records/18444900
DOI: 10.5281/zenodo.18444900
Date: 2026-01-31 (within the 72-hour collection window)
Authors: Michael Riegler (Simula Research Laboratory), Sushant Gautam (Simula Metropolitan Center for Digital Engineering, SimulaMet)

## Dataset

- 19,802 posts + 2,812 comments
- Collection window: 2026-01-28 to 2026-01-31 (72 hours, immediately post-launch)
- Platform claimed 1.5M registered accounts at collection time

## Top-line findings (verbatim or near-verbatim)

1. **506 prompt-injection attacks** targeting AI readers (= 2.6% of the 19,802 posts; this is where the "2.6% of content contains hidden prompt injection" figure comes from).
2. **61% concentration**: a single malicious actor accounted for 61% of API-injection attempts and 86% of manipulation content.
3. **19.3% cryptocurrency content** — unregulated crypto promotion/spam as 19.3% of all content.
4. **Anti-human manifestos** receiving hundreds of thousands of upvotes.
5. **43% sentiment decline** in the three days post-launch.
6. Specific actor named: **"AdolfHitler"** account conducting social engineering campaigns against other agents, exploiting agents' helpfulness training to coerce harmful-code execution.

## Methodology

- Dual sentiment analysis: TextBlob + VADER.
- Behavioral clustering.
- Network analysis.
- Pattern matching for prompt-injection signatures (the 506 figure is from a signature pass over the 19,802 posts).

## Lane 5 read

The 2.6% figure is **cumulative over 72 hours**, not per-day. It is the result of a single signature-matching pass — not a longitudinal trend. It also undercounts: any injection that doesn't match the researchers' signature pattern is missed. The 506-number is a **floor**, not a ceiling.

The 61% / 86% concentration is the **most important** Simula finding for Lane 5: it means the "AI agent ecosystem" narrative is mostly the work of a small number of operators. Specifically, **one operator accounts for the majority of the prompt-injection problem.** Combined with the Wiz 88:1 ratio and the InfoQ "one user registered 500,000 agents" claim, this confirms the platform's power-law operator structure: a small group of humans is driving the lion's share of all observable behavior.

This is the cleanest single-paper deflation: peer-reviewable methodology, primary data collection, 72-hour fresh-launch window, public on Zenodo.

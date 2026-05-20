# Lane 5 — sources index

All accessed 2026-05-20. Failures (paywall/redirect/404) explicitly marked.

## Primary security audits

1. **Wiz blog** — https://www.wiz.io/blog/exposed-moltbook-database-reveals-millions-of-api-keys — 2026-02-02. Primary; the 1.5M / 35K / 17K / 88:1 source. Cached: `wiz_blog_key_facts.md` (this lane) + `wiz_blog_excerpt.md` (Lane 1).
2. **404 Media first report** — https://www.404media.co/exposed-moltbook-database-let-anyone-take-control-of-any-ai-agent-on-the-site/ — 2026-01-31. Matthew Gault, with researcher Jameson O'Reilly. Pre-Wiz public disclosure.
3. **Simula risk assessment** — https://zenodo.org/records/18444900 — 2026-01-31. Riegler + Gautam. The 506 prompt-injection / 2.6% / 61% / 86% / 19.3% / 43% sentiment-decline source. Cached: `simula_risk_assessment.md`.

## Press deflation pieces

4. **MIT Technology Review — "Moltbook was peak AI theater"** — https://www.technologyreview.com/2026/02/06/1132448/moltbook-was-peak-ai-theater/ — 2026-02-06. Will Douglas Heaven. Anchor source. Cached: `mittr_peak_ai_theater.md`.
5. **MIT Technology Review — "Why the Moltbook frenzy was like Pokémon"** — https://www.technologyreview.com/2026/02/09/1132537/a-lesson-from-pokemon/ — 2026-02-09. Same author.
6. **Fortune** — https://fortune.com/2026/02/02/moltbook-security-agents-singularity-disaster-gary-marcus-andrej-karpathy/ — 2026-02-02. Beatrice Nolan. Karpathy reversal verbatim + Gary Marcus quotes.
7. **Fortune — "live demo"** — https://fortune.com/2026/02/03/moltbook-ai-social-network-security-researchers-agent-internet/ — 2026-02-03. Beatrice Nolan. UCL + Wiz + Aikido + Willison quotes.
8. **Schneier on Security — "On Moltbook"** — https://www.schneier.com/blog/archives/2026/03/on-moltbook.html — 2026-03-03. Cached verbatim: `schneier_full.md`.

## Industry security analyses

9. **Palo Alto Networks Unit 42 (blog)** — https://www.paloaltonetworks.com/blog/network-security/the-moltbook-case-and-how-we-need-to-think-about-agent-security/ — 2026-02-05. Sailesh Mishra. IBC framework.
10. **Vectra.ai** — https://www.vectra.ai/blog/moltbook-and-the-illusion-of-harmless-ai-agent-communities — 2026-02-03 (original), updated 2026-05-12. Lucie Cardiet.
11. **Google Threat Intelligence Group (GTIG)** — https://cloud.google.com/blog/topics/threat-intelligence/ai-vulnerability-exploitation-initial-access — 2026-05 (week of May 8-11 per news cycle). UNC5673 / UNC6201 / Claude-Relay-Service / CLIProxyAPI / OpenClaw skill supply-chain. **Does NOT mention Moltbook directly.** Cached: `gtig_unc5673.md`.
12. **Mandiant M-Trends 2026** — https://cloud.google.com/blog/topics/threat-intelligence/m-trends-2026 — 2026. 22-second hand-off finding; not Moltbook-specific.

## Karpathy primary

13. **Karpathy's "sci-fi takeoff-adjacent" X post** — https://x.com/karpathy/status/2017296988589723767 — 2026-01-30. **PAYWALLED to WebFetch** (HTTP 402). Cited verbatim via Wikipedia + AICerts + Bloomberg + Fortune. Cached reasoning: `karpathy_reversal.md`.
14. **Harlan Stewart fake-screenshot thread** — https://x.com/HumanHarlan/status/2017424289633603850 — early Feb 2026. **PAYWALLED to WebFetch** (HTTP 402). Cited via 36kr.

## Chinese-language retrospective

15. **36kr — "Stop FOMO: The Human Terminator Moltbook Is Dead"** — https://eu.36kr.com/en/p/3670315867923075 — 2026-02-05 (per metadata; specific datetime: see article). Yishu Team / Yifan author. Machine-translated to English via 36kr's own EU portal.
16. **36kr — "Shocking Revelation: 99% of Moltbook's 1.5M Users Are Fake Accounts"** — https://eu.36kr.com/en/p/3665797324039042 — 2026-02-02 16:34 GMT+8. InfoQ / Geekbang Technology. Machine-translated. **Important: this is the source for "one researcher registered 500,000 fake accounts" and the 17,000-verified-owners claim picked up by Chinese press.**

## Other corroborating press

17. **Wikipedia** — https://en.wikipedia.org/wiki/Moltbook — secondary index of Karpathy quotes + Meta acquisition + count chain.
18. **moltbookstatus.com** — https://moltbookstatus.com/ — 2026-03-09 snapshot. Showed the 193,912 relabel + the silent change between 2026-03-02 and 2026-03-09.
19. **CNBC** — https://www.cnbc.com/2026/03/10/meta-social-networks-ai-agents-moltbook-acquisition.html — 2026-03-10. Meta acquisition.
20. **Axios** — https://www.axios.com/2026/03/10/meta-facebook-moltbook-agent-social-network — 2026-03-10. Same.
21. **AI CERTs / aicerts.ai** — https://www.aicerts.ai/news/moltbook-sparks-fresh-singularity-debate/ — 2026 (post-Jan-30). Independent corroboration of "sci-fi takeoff-adjacent."
22. **InfoSecurity Magazine** — https://www.infosecurity-magazine.com/news/moltbook-exposes-user-data-api/ — 2026-02. Re-reports Wiz.
23. **Neowin** — https://www.neowin.net/news/moltbook-had-an-exposed-database-with-over-20000-emails-15-million-api-keys-and-more/ — 2026-02. Re-reports Wiz, slightly different framing ("20,000+ emails" vs Wiz's 35,000 — this is the `owners`-only count).
24. **SiliconANGLE** — https://siliconangle.com/2026/02/02/ai-agent-social-network-moltbook-left-millions-credentials-publicly-exposed/ — 2026-02-02.
25. **Tech Buzz AI — "Humans Hijack AI-Only Social Network Moltbook"** — https://www.techbuzz.ai/articles/humans-hijack-ai-only-social-network-moltbook — early 2026. Strong puppetry framing.

## arXiv companion papers (deflation evidence, not deflation source)

26. **"The Moltbook Illusion: Separating Human Influence from Emergent Behavior in AI Agent Societies"** — https://arxiv.org/abs/2602.07432 — Feb 2026.
27. **"Agents in the Wild: Safety, Society, and the Illusion of Sociality on Moltbook"** — https://arxiv.org/pdf/2602.13284 — Feb 2026.
28. **"Social Simulacra in the Wild: AI Agent Communities on Moltbook"** — https://arxiv.org/pdf/2603.16128 — Mar 2026.
29. **"Large-Scale Analysis of Persuasive Content on Moltbook"** — https://arxiv.org/pdf/2603.18349 — Mar 2026.

## Failures / paywalled

- Karpathy X posts (HTTP 402; cited via secondary sources)
- Harlan Stewart X thread (HTTP 402)
- Bloomberg articles (paywall — cited via Reuters / valuesense / press)

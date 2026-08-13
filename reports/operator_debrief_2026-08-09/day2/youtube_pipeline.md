# Headless YouTube Pipeline for a Solo Agent-Infra Operator

**Deliverable date:** 2026-08-09 · **Operator context:** solo dev running `dharma_swarm` (self-improving multi-agent organism). Everything below assumes **no GUI editor, no screen, no manual timeline work** — the whole pipeline is scripts, cron, and one human review gate before publish.

---

## 1. Tool landscape (researched Aug 2026)

### 1.1 Script → Voice (TTS)

| Tool | Notes | Cost signal | URL |
|---|---|---|---|
| **ElevenLabs** | Still the quality benchmark for static narration. Lowered API pricing in 2026 + introduced pay-as-you-go; Flash model ≈ $0.05/1K chars on Creator tier (down from $0.11). Creator plan = 30K credits/mo ≈ 30 min Multilingual or 60 min Flash. | $5–22/mo covers a solo channel | https://elevenlabs.io/blog/weve-lowered-api-agents-pricing-and-introduced-pay-as-you-go · pricing breakdowns: https://www.cekura.ai/blogs/elevenlabs-pricing, https://flexprice.io/blog/elevenlabs-pricing-breakdown |
| **OpenAI TTS** (`gpt-4o-mini-tts` family) | Cheapest hosted option; strongest for realtime/translation, fine for narration. Good fallback voice. | ~$0.015/min class | https://www.aipricing.guru/ai-voice-tts-api-pricing/ |
| **Cartesia Sonic** | Streaming-first, ~90 ms latency; built for voice agents more than narration, but API is clean and headless. | usage-based | https://www.forasoft.com/blog/article/elevenlabs-alternatives |
| **Fish Audio** | The 2026 value pick; near-ElevenLabs quality at a fraction of the cost. | low | https://fish.audio/vs/pricing/elevenlabs/ |
| **Open source: Chatterbox (Resemble, MIT), Kokoro, XTTS, Piper** | Zero per-character cost, run locally/GPU-box. Kokoro is the current small-model favorite; Chatterbox is MIT-licensed and competitive. Good for iteration drafts even if you publish with ElevenLabs. | $0 + compute | https://techiehub.blog/elevenlabs-alternatives/ |

**Verdict:** ElevenLabs for the published voice (consistent channel identity matters), Kokoro/Chatterbox locally for fast draft renders during script iteration.

### 1.2 Voice → Visual (rendering)

| Tool | Role in a headless pipeline | URL |
|---|---|---|
| **Remotion** | React → MP4. THE core of this pipeline: videos are code, rendered via Node (`@remotion/renderer`) locally, in CI, or on Lambda. **License:** free for individuals/companies ≤3 people (this operator qualifies); Company License $100/mo minimum otherwise. Source-available, not OSI open source. | https://www.remotion.dev/ · SSR: https://www.remotion.dev/docs/ssr · license: https://www.remotion.dev/docs/license/faq |
| **Motion Canvas / Revideo** | OSS alternatives if Remotion licensing ever becomes a problem; Revideo is the Remotion-API-compatible fork. | https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026 |
| **ffmpeg** | The glue: mux VO onto renders, concat segments, loudness-normalize (`loudnorm`), burn subtitles, 9:16 crops, thumbnails from frames. Zero cost, fully headless. | https://ffmpeg.org/ |
| **Manim (Community)** | Python math/technical animation — perfect for explaining graph topologies, MAP-Elites grids, feedback loops. Renders headless to MP4; drop clips into Remotion as assets. | https://www.manim.community/ |
| **VHS (charmbracelet)** | **Killer tool for this operator:** terminal demos as code. Write a `.tape` file (commands, timing, theme), `vhs demo.tape` → MP4/GIF/frames — deterministic, re-renderable "screen capture" with no screen. | https://github.com/charmbracelet/vhs · guide: https://tenthirtyam.org/dispatches/2026/04/16/how-to-create-terminal-demos-as-code-with-vhs-by-charm/ |
| **asciinema + agg** | Quick one-off terminal recordings → GIF; VHS is better for scripted, repeatable takes. | https://docs.asciinema.org/manual/agg/ |

### 1.3 AI video generation APIs (state of play, mid-2026)

Use sparingly — for 3–8s B-roll flourishes, not the backbone. Current field: Veo 3.1, Kling 3.0, Sora 2, Runway Gen-4.5, Seedance 2.0.

- **Veo 3.1** — ~$0.40/s standard; via Vertex AI / Gemini API, gated by region/account tier. Best quality, priciest.
- **Kling 3.0** — $0.09–0.14/s; self-serve via fal.ai / ModelsLab, no waitlist. **Best price/quality for a solo dev.**
- **Sora 2** — $0.10/s base ($0.30–0.50/s Pro) on the OpenAI API, generally available to paying customers.
- **Runway Gen-4.5** — ~$0.12/s but direct API is enterprise-waitlist restricted; not practical for headless solo use.
- **Pika** — consumer app focus; no serious self-serve API story vs the above; skip.

Sources: https://www.buildmvpfast.com/api-costs/ai-video · https://modelslab.com/blog/api/veo-3-1-vs-kling-3-sora-2-ai-video-api-cost-2026 · https://apiframe.ai/blog/ai-video-api-pricing-2026 · https://devtk.ai/en/blog/ai-video-generation-pricing-2026/

### 1.4 Captions & shorts repurposing (headless, open source)

- **faster-whisper / whisper.cpp** — word-level timestamps → ASS/SRT; burn with ffmpeg (`subtitles=` filter) or render word-by-word "CapCut-style" captions natively in Remotion (better, since captions become code).
- **OpenShorts** (MIT) — self-hosted Opus Clip alternative: AI moment detection, MediaPipe+YOLOv8 face tracking for 9:16 reframe, faster-whisper word captions, ffmpeg effects; **ships an MCP server + API for agents**. https://github.com/mutonby/openshorts
- **autoclip** — local-first, fully offline (Whisper + Ollama), speaker-tracked 9:16 caption-burned clips. https://github.com/artbyjazi/autoclip
- **AI-Youtube-Shorts-Generator** — LLM highlight detection + Whisper + auto vertical crop. https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator
- **yt-short-clipper** — single-command long-form → shorts with highlighted captions + SEO metadata. https://github.com/jipraks/yt-short-clipper

Note: for THIS operator, auto-crop face-tracking matters less (content is terminal/diagram, not talking-head). Shorts are better authored natively at 1080×1920 in Remotion than cropped from 16:9.

### 1.5 Thumbnails (headless)

- **Best fit: render thumbnails in Remotion** — `renderStill()` from a `Thumbnail` composition. Same design system as the video, versioned as code, deterministic. (Alternative: `satori` + `sharp`, or node-canvas.)
- AI-image thumbnails (gpt-image-1, Flux via fal.ai/Replicate) for background art only; composite title text programmatically — AI text rendering is still not thumbnail-grade.
- API constraint: thumbnails must be JPEG/PNG ≤ 2 MB (https://developers.google.com/youtube/v3/docs/thumbnails/set).

### 1.6 YouTube Data API v3 — upload flow, quota, verification

- **Flow:** OAuth 2.0 (installed-app flow; one-time browser consent → refresh token, then headless forever) → `videos.insert` (resumable upload) → `thumbnails.set` → optionally `playlistItems.insert`.
  - Docs: https://developers.google.com/youtube/v3/getting-started · https://developers.google.com/youtube/v3/guides/auth/installed-apps · sample: https://github.com/youtube/api-samples/blob/master/python/upload_thumbnail.py
- **Quota:** default 10,000 units/day per project. `videos.insert` was historically ~1,600 units (~6 uploads/day); **reduced to ~100 units in Dec 2025** (~100 uploads/day possible), though docs lag — verify against the live quota page. `thumbnails.set` ≈ 50 units. Reads are 1 unit; `search.list` is 100 (avoid in loops). Sources: https://developers.google.com/youtube/v3/determine_quota_cost · https://www.socialcrawl.dev/blog/youtube-data-api-2026 · https://outlierkit.com/resources/youtube-api-quota/
- **Channel (phone) verification** — done once at https://www.youtube.com/verify — unlocks: uploads **>15 minutes**, **custom thumbnails**, live streaming. Without it the API rejects long uploads and `thumbnails.set`. https://support.google.com/youtube/answer/71673
- **OAuth app verification / API audit** — the sharp edge: unverified OAuth apps are limited to 100 test users and show a warning screen (fine for personal use — add your own email as a test user). BUT for API projects created after 2020-07-28 that haven't passed YouTube's **API compliance audit**, `videos.insert` uploads are **locked to private**. Two paths: (a) request the audit/exemption via the YouTube API compliance form (personal-use exemptions are routinely granted; plan 2–4 weeks), or (b) upload private via API and flip to public/scheduled — note scheduling itself uses `status.publishAt` + `privacyStatus: private`, which composes fine once audited. Sources: https://postproxy.dev/blog/youtube-upload-api-guide/ · https://posteverywhere.ai/blog/post-to-youtube-api · https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps
- **Scheduling:** set `status.privacyStatus = "private"` + `status.publishAt` (ISO 8601); YouTube flips to public at that time. Shorts are just ≤3 min vertical videos — same endpoint, `#Shorts` in title/description helps classification.

### 1.7 MCP servers (agent-native hooks)

- **video-audio-mcp** (misbahsy) — ffmpeg editing ops via MCP: trim, overlay, transitions, format conversion. https://github.com/misbahsy/video-audio-mcp
- **VFX MCP Server** — similar ffmpeg-family toolset. https://mcpservers.org/servers/conneroisu/vfx-mcp
- **Remotion MCP is deprecated** → replaced by **Remotion Agent Skills** (install skills into Claude Code rather than run a server). https://www.remotion.dev/docs/ai/mcp
- **Claude Code Video Toolkit** — skills + MCP servers covering Remotion, Manim, screen recording, YouTube clipping, ffmpeg post. Directly relevant starting kit. https://github.com/wilwaldon/Claude-Code-Video-Toolkit
- **mcp-youtube** (anaisbetts) — YouTube metadata/subtitles fetching. https://github.com/anaisbetts/mcp-youtube
- **OpenShorts MCP** — shorts generation as an agent tool (see 1.4).
- Practical note: for a pipeline-as-code repo, plain CLI scripts beat MCP servers for the render path (deterministic, cron-able); MCP earns its keep for interactive "edit this video" sessions in Claude Code.

---

## 2. Recommended headless stack

**Backbone: markdown script → ElevenLabs TTS → Remotion render (VHS/Manim clips as assets) → ffmpeg mux/normalize → Remotion still for thumbnail → YouTube API scheduled upload.** No GUI at any stage.

```
script.md ──llm/hand──► script.json (VO lines + scene cues, timed)
script.json ──ElevenLabs API──► vo/*.mp3 + per-word timestamps
demo.tape ──vhs──► assets/term/*.mp4        (terminal "screen capture" as code)
scene.py ──manim──► assets/anim/*.mp4       (technical diagrams)
Remotion comp (React) ◄─ consumes vo + timestamps + assets ──► render/video.mp4
ffmpeg: loudnorm −14 LUFS, faststart, H.264 yuv420p
Remotion renderStill ──► render/thumb.png (≤2MB)
review gate (human) ──► approved/
uploader.py ──YouTube Data API──► private + publishAt schedule
```

**Why this backbone:** every artifact is reproducible from text in git; a bad take is a re-render, not a re-record; and the same Remotion project emits 16:9 long-form and 1080×1920 shorts from shared components. This is the only video approach that matches how this operator already works (receipts, determinism, citation-or-silence).

### Credentials / accounts map

| Stage | Account/credential | Where it lives |
|---|---|---|
| TTS | ElevenLabs account + `ELEVENLABS_API_KEY` | env / secret store — **never in git** (gitleaks blocks anyway) |
| Optional AI b-roll | fal.ai key (Kling 3.0) | env |
| Render | none (Remotion free tier for ≤3-person co; ffmpeg/VHS/Manim are free) | — |
| Upload | Google Cloud project → YouTube Data API v3 enabled → OAuth client (Desktop) → `client_secret.json` + one-time consent → `token.json` (refresh token) | `~/.dharma-yt/` or similar, chmod 600, never in git |
| Channel | YouTube channel, phone-verified (once, manual) | — |
| Publish-public | YouTube API compliance audit approval (once, form) | — |

### Rough monthly cost (solo, ~4 long-form + 8 shorts/mo)

| Item | Cost |
|---|---|
| ElevenLabs Creator (~60 min Flash VO) | $22 |
| YouTube API / quota | $0 |
| Remotion (individual/≤3-person) | $0 |
| ffmpeg, VHS, Manim, whisper | $0 |
| Optional Kling 3.0 b-roll (~60 s @ $0.10/s) | ~$6 |
| Optional GPU box for local TTS/whisper | $0 (existing hardware) |
| **Total** | **~$22–30/mo** |

---

## 3. Pipeline-as-code sketch

Lives outside the dharma_swarm repo (a hard rule there is no new root files and receipts never enter git; also this is a separate venture surface — if it's folded in later it belongs under the Darshan track, which owns the publication cell).

```
yt-pipeline/
├── channel.yaml              # channel constants: voice_id, brand colors, upload defaults
├── videos/
│   └── 001-organism-reviews-own-prs/
│       ├── script.md         # human/LLM-authored source of truth
│       ├── script.json       # compiled: [{scene, vo, visual_cue, est_secs}]
│       ├── tapes/*.tape      # VHS terminal-demo scripts
│       ├── manim/*.py        # diagram animations
│       ├── assets/           # generated: vo/, term/, anim/  (gitignored)
│       ├── render/           # video.mp4, thumb.png          (gitignored)
│       └── meta.yaml         # title, description, tags, publishAt, shorts refs
├── remotion/                 # one Remotion project, comps: LongForm, Short, Thumbnail
│   └── src/{LongForm.tsx, Short.tsx, Thumbnail.tsx, components/}
├── stages/
│   ├── 10_compile.py         # script.md → script.json (LLM-assisted beat timing)
│   ├── 20_tts.py             # ElevenLabs per-line → mp3 + alignment JSON; cache by text-hash
│   ├── 30_assets.sh          # vhs tapes/*.tape; manim -qh manim/*.py
│   ├── 40_render.ts          # npx remotion render <Comp> --props=script.json
│   ├── 50_post.sh            # ffmpeg loudnorm -14 LUFS, faststart, checksum receipt
│   ├── 60_thumb.ts           # remotion still Thumbnail → thumb.png (assert ≤2MB)
│   ├── 70_review.py          # builds review manifest; BLOCKS until approved
│   └── 80_upload.py          # videos.insert (resumable) + thumbnails.set + publishAt
├── bin/produce               # runs 10→60 for one video dir; idempotent, hash-cached
├── bin/publish               # runs 70→80
└── receipts/                 # per-stage JSON receipts (duration, LUFS, sha256, video_id)
```

**Review gate (the one human touchpoint):** `70_review.py` writes `review.html` (embedded video, thumbnail, title/description/publishAt) and exits nonzero until `approved: true` + checksum of the reviewed mp4 appears in `meta.yaml`. `80_upload.py` refuses to run if the file hash doesn't match the approved hash — nothing unreviewed can ship, even from cron. Uploads go up `private` with `publishAt`, so there's a second undo window on YouTube itself.

**Cron/agent wiring:** `bin/produce` is safe to run autonomously (agents can draft scripts, cut tapes, render nightly). `bin/publish` runs only after human approval; a weekly cron can *check* for approved-but-unpublished videos and upload them, e.g. `0 9 * * 1 bin/publish --all-approved`. Receipts mirror the dharma_swarm pattern: every stage emits JSON evidence, uploader records `video_id` + quota spent.

---

## 4. Scripts for the first three videos

Grounded in the actual repo: `scripts/runtime/pr_merge_control.py` (3,130 lines, HOT_PATH_PATTERNS gate), `dharma_swarm/task_board.py` (SQLite status FSM + dependency tracking), `dharma_swarm/telos_gates.py` (TelosGatekeeper, AHIMSA tier-A gate), `dharma_swarm/dharma_kernel.py` (25 SHA-256-signed axioms), `dharma_swarm/stigmergy.py` (append-only marks), `dharma_swarm/skills/*.skill.md` (8 named agent roles: archeologist, architect, builder, cartographer, jagat_kalyan, researcher, surgeon, validator).

### Video A (long-form, 10–14 min): "I made an AI organism that reviews its own PRs"

**Hook (0:00–0:35):** Cold open on a real terminal: a PR opened by an agent, then a second agent — "Merge Master Mike" — blocking it. VO: *"This pull request was written by an AI agent. And it's about to get rejected... by another AI agent. Same codebase, same team, zero humans in this loop — and that's exactly the point. I run a repo where the merge queue is an AI with veto power over other AIs, including the one that built it. Here's why that's the only way this doesn't collapse."*

**Section outline:**
1. **The problem (0:35–2:30)** — agent swarms produce plausible garbage at scale; fluent ≠ true. Introduce the repo's core rule: *citation-or-silence* — every claim needs a `file:line` or a runnable command. B-roll: VHS tape scrolling CLAUDE.md hard-rules section; Manim animation of "claims" nodes turning red without evidence edges.
2. **Meet the organism (2:30–4:30)** — quick anatomy: SwarmManager (agent pool + task board), DharmaKernel (25 immutable axioms, SHA-256 signed — show `dgc dharma status` verifying signatures), TelosGatekeeper safety gates (AHIMSA = do-no-harm is tier A). B-roll: Manim organism diagram; VHS `dgc status`, `dgc health`.
3. **Merge Master Mike (4:30–8:00)** — the star. A persistent merge agent whose gate (`pr_merge_control.py` — 3,130 lines of "no") blocks even green-CI PRs on: conflicts, requested-changes reviews, unresolved threads, missing agent-review receipts, HIGH/CRITICAL risk without human sign-off. Show HOT_PATH_PATTERNS: touching hot paths triggers packet ceremony (preflight → closeout). B-roll: VHS of the gate rejecting a PR with reasons; screen-capture of the automerge workflow YAML.
4. **Why gates don't strangle the swarm (8:00–11:00)** — the ensemble principle: `E_ensemble = E_mean − E_diversity` (Krogh–Vedelsby). Every new gate is paid for in diversity; selection is MAP-Elites, diversity-preserving by construction. Manim: error-cancellation animation — correlated agents fail together, decorrelated agents cancel.
5. **What actually happened (11:00–13:00)** — honest results segment: what the gates caught, what slipped, the broken-register tally, the 13 cybernetic loops and which are actually closed. VO stance: "the interesting number isn't PRs merged, it's PRs *refused*."
6. **Outro (13:00–end)** — "next video: what happened when I gave the agents a task board." Subscribe CTA, link to repo/shorts.

**B-roll/capture plan:** entirely VHS tapes (`dgc` commands, gate rejection, pytest run) + 3 Manim sequences (organism anatomy, evidence graph, ensemble math) + Remotion-native diagrams for section cards. Zero AI-generated video needed.

### Video B (short, ~45 s, 1080×1920): "What happens when AI agents get a task board"

**Hook (0–3 s):** Big kinetic text over terminal: **"I gave 8 AI agents a shared to-do list. It got weird."**

**Beats + VO lines:**
- (3–10 s) *"No manager. No meetings. Just a SQLite task board with a strict state machine — pending, claimed, done — and dependency tracking baked in."* Visual: VHS of tasks appearing; Remotion overlay of the status FSM.
- (10–20 s) *"Each agent has a role — architect, builder, surgeon, validator — and they claim tasks like devs grabbing tickets. A task with unfinished dependencies? The board won't even show it to them."* Visual: skill roster cards animating in from actual `.skill.md` names; dependency edges lighting up.
- (20–32 s) *"The weird part: they coordinate without talking. Finished work leaves stigmergy marks — pheromone trails in a JSONL file — and the next agent reads the trail instead of asking questions."* Visual: Manim ant-trail metaphor morphing into `marks.jsonl` lines appending.
- (32–42 s) *"That's called stigmergy. It's how termites build cathedrals with no blueprint. Turns out it works on software agents too."* Visual: termite mound → dependency graph match-cut.
- (42–45 s) *"Full breakdown of the organism on my channel."* End card.

**Capture notes:** one VHS tape (task create → claim → done with dependency block shown), one short Manim trail animation, everything else native Remotion text/cards. Word-by-word captions from ElevenLabs alignment timestamps.

### Video C (short, ~50 s, 1080×1920): "The one AI agent pattern that actually worked"

**Hook (0–3 s):** **"I tried every multi-agent pattern. One survived."** (hard cut, red stamp animation: FAILED × 4)

**Beats + VO lines:**
- (3–12 s) *"Not the debate club — agents arguing burns tokens and converges on confident nonsense. Not the boss agent — one planner becomes one bottleneck with hallucinations."* Visual: pattern diagrams stamped FAILED in sequence.
- (12–24 s) *"What worked: citation-or-silence. Every claim an agent makes must carry a file-and-line citation or a runnable command. No receipt? The claim carries zero weight. Doesn't matter how fluent it sounded."* Visual: agent output with claims highlighted; uncited line literally dissolves; cited line gets a green lock.
- (24–38 s) *"This one rule changes everything downstream. Reviews become mechanical — run the command, check the line. My merge agent enforces it automatically: a PR whose claims don't verify gets blocked, no human needed. Trust stops being a vibe and becomes a checksum."* Visual: VHS of a verification script pass/fail; Mike blocking a PR.
- (38–48 s) *"The meta-lesson: don't make agents smarter. Make lying mechanically impossible, and average agents get you world-class output."* Visual: ensemble-error equation flash.
- (48–50 s) End card: "Long version + repo on the channel."

**Capture notes:** 2 VHS tapes (claim-verification run; merge gate refusal), rest is Remotion kinetic type. Reuses Video A's Mike footage — shorts should strip-mine long-form assets.

---

## 5. Honest constraints — what CANNOT be done from this sandbox

**Cannot be done by the agent, period:**
1. **Create Google/YouTube/ElevenLabs accounts** — signup requires phone/CAPTCHA/payment and violates ToS if automated.
2. **Complete the OAuth consent screen** — the installed-app flow requires a real browser login as the channel owner, once. No headless bypass that isn't a ToS violation.
3. **YouTube channel phone verification** (unlocks >15 min uploads + custom thumbnails) — SMS to a human phone.
4. **YouTube API compliance audit** — a human-submitted form; until approved, API uploads on a post-2020 project are forced private (fine for the review-gate workflow, blocking for auto-publish-public).
5. **Actually publish** — by design: the review gate exists so nothing ships without the operator's eyes; this constraint is a feature, keep it.
6. **Taste** — hooks, pacing, and thumbnail judgment need human A/B iteration; the pipeline makes iteration cheap, it doesn't replace it.

**Exact operator setup checklist (~1–2 hours human time + wait):**
1. YouTube channel exists → visit https://www.youtube.com/verify, phone-verify (unlocks >15 min + custom thumbnails).
2. https://console.cloud.google.com → new project `yt-pipeline` → enable **YouTube Data API v3**.
3. OAuth consent screen → External → Testing → add your own Gmail as a **test user** (personal use never needs full verification).
4. Credentials → OAuth client ID → **Desktop app** → download `client_secret.json` to the pipeline box (chmod 600, outside any git repo).
5. Run the pipeline's one-time `auth.py`; it prints a URL — open it in any browser, consent with the channel account, paste the code back; `token.json` (refresh token) is written. Headless from then on.
6. Submit the **YouTube API compliance audit / exemption form** (personal use case, link from https://developers.google.com/youtube/v3/getting-started) so API uploads can go public. Expect 2–4 weeks; until then, upload private via API and flip visibility in Studio at publish time (~30 s/video of human work).
7. ElevenLabs: create account → pick/design one channel voice, note `voice_id` → API key into the env/secret store.
8. Optional: fal.ai account + key for Kling b-roll.
9. First-run sanity: `bin/produce videos/001-*` → open `review.html` → mark approved → `bin/publish` → confirm the private video + thumbnail + `publishAt` landed in YouTube Studio.

Total recurring human effort once running: **script approval + review gate + thumbnail glance — roughly 20 minutes per video.**

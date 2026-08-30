"use strict";

const regions = [
  { id: "intent", label: "Direction", owner: "ACTIVE_TRACK.yaml", meaning: "Outcomes, priorities, limits, and non-goals" },
  { id: "runtime_truth", label: "What is actually running", owner: "RuntimeStateStore", meaning: "Runs, leases, receipts, and observed effects" },
  { id: "dispatch", label: "How work moves", owner: "Runtime spine", meaning: "Identity, dispatch, and delivery boundaries" },
  { id: "projections", label: "What we can see", owner: "Named projectors", meaning: "Cockpits, reports, cards, and briefings" },
  { id: "governance", label: "Rules and boundaries", owner: "Governance doctrine", meaning: "Policy, ownership, and safety rules" },
  { id: "work_control", label: "Work and attention", owner: "TaskBoard + Control Surface", meaning: "Tasks, dependencies, and decisions" },
  { id: "value", label: "Real-world result", owner: "External outcome owners", meaning: "Measured value beyond the repository" },
];

const quests = [
  {
    id: "runtime",
    code: "QUEST-RUNTIME-17",
    title: "Runtime Spine Hardening",
    primaryRegion: "runtime_truth",
    regions: ["runtime_truth", "governance", "work_control"],
    summary: "A live run exists, but its proof is old and one source disputes the claimed result.",
    attention: "Decide whether a fresh verification proposal should be prepared.",
    changed: "A retry entered the running state at 09:37 JST.",
    importance: "A stale seal can make active work look safer than it is.",
    known: "The run and retry are directly observed in the fixture snapshot.",
    unknown: "Whether the current output satisfies the latest obligation.",
    owner: "RuntimeStateStore; verification owned separately",
    safe: "Inspect, compare, or prepare a local proposal. Nothing can be dispatched here.",
    receipt: "A fresh receipt bound to run digest 7b4d and obligation verify-runtime/v3.",
    warning: "stale",
    brief: [
      ["Attention", "One permission boundary needs judgment."],
      ["Why / freshness", "The run is observed; supporting proof is stale and contradicted."],
      ["Your judgment", "Choose only what should become a local proposal draft."],
      ["Agent limits", "No agent may grant, dispatch, publish, merge, or spend here."],
      ["Proof", "A fresh independently bound receipt would close the named obligation."],
    ],
    facets: [
      { label: "Specification", literal: "Specified · v3", tone: "current", symbol: "S", metaphor: "Route surveyed" },
      { label: "Permission", literal: "Expired · proposal only", tone: "caution", symbol: "L", metaphor: "Gate locked" },
      { label: "Execution", literal: "Running · retry 2", tone: "current", symbol: "R", metaphor: "Unit moving" },
      { label: "Verification", literal: "Passed · stale · contradicted", tone: "conflict", symbol: "V", metaphor: "Weathered seal under dispute" },
      { label: "Outcome", literal: "Not observed", tone: "unknown", symbol: "?", metaphor: "Land beyond the fog" },
    ],
    decision: {
      question: "Should we prepare a fresh verification proposal?",
      why: "The last passing receipt predates the retry and a second source contradicts it.",
      suggested: "Prepare the proposal, but do not authorize or dispatch it.",
      risk: "Reversible local draft. It has no effect outside this browser tab.",
      choices: ["Prepare a local proposal", "Keep watching", "Ask the owner for context"],
    },
    journey: [
      { time: "09:31", title: "Mission selected", detail: "Operator pin; no system mutation", kind: "Intent" },
      { time: "09:34", title: "Slice entered runtime", detail: "Observed run run_7b4d", kind: "Observed" },
      { time: "09:36", title: "Attempt 1 failed", detail: "Child step timed out", kind: "Failure", className: "is-failed" },
      { time: "09:37", title: "Retry 2 started", detail: "Currently running", kind: "Retry", className: "is-retry" },
      { time: "09:42", title: "Old proof disputed", detail: "Verification remains passed, but stale and contradicted", kind: "Conflict" },
    ],
    claims: [
      { predicate: "run.state", value: "running", basis: "observed", coherence: "supported", evidence: "available", temporal: "current", owner: "RuntimeStateStore", observed: "09:42 JST", scope: "fixture/worktree-A/host-demo/runtime-7b4d", ref: "receipt://run/7b4d/retry-2" },
      { predicate: "verification.decision", value: "passed", basis: "verified", coherence: "contradicted", evidence: "bound but old", temporal: "stale", owner: "Verifier v2", observed: "08:11 JST", scope: "fixture/worktree-A/run-7b4d-pre-retry", ref: "receipt://verify/old-a91c" },
      { predicate: "outcome.observed", value: "unknown", basis: "unknown", coherence: "unresolved", evidence: "missing", temporal: "unknown", owner: "External outcome owner", observed: "never", scope: "external/not-connected", ref: "missing://outcome/runtime" },
    ],
  },
  {
    id: "radar",
    code: "QUEST-RADAR-04",
    title: "World Radar Intake",
    primaryRegion: "projections",
    regions: ["projections", "dispatch", "work_control"],
    summary: "Three sources describe the intake, but their host and observation times cannot be safely joined.",
    attention: "Do not rank or reconcile until the snapshot scopes match.",
    changed: "One source reappeared with a different runtime instance.",
    importance: "A polished composite would falsely imply one coherent world.",
    known: "Each source returned a fixture record.",
    unknown: "Whether the records describe the same checkout, host, and runtime.",
    owner: "Three source owners; no joined owner",
    safe: "Inspect each source separately or request a scope-aligned snapshot.",
    receipt: "An atomic snapshot proof, or aligned source scope and observation identities.",
    warning: "mixed",
    brief: [
      ["Attention", "No justified priority can be produced from these sources."],
      ["Why / freshness", "The snapshot is mixed-time and runtime scopes disagree."],
      ["Your judgment", "Choose whether to request a scope-aligned observation."],
      ["Agent limits", "No join, bottleneck, completion, or action may be inferred."],
      ["Proof", "Matching source identities and scope would permit comparison."],
    ],
    facets: [
      { label: "Specification", literal: "Unknown", tone: "unknown", symbol: "?", metaphor: "Unsurveyed route" },
      { label: "Permission", literal: "Proposal only", tone: "caution", symbol: "L", metaphor: "Gate has no key" },
      { label: "Execution", literal: "Unknown · sources disagree", tone: "unknown", symbol: "?", metaphor: "Units hidden by fog" },
      { label: "Verification", literal: "Untested", tone: "unknown", symbol: "U", metaphor: "No seal exists" },
      { label: "Outcome", literal: "Unknown", tone: "unknown", symbol: "?", metaphor: "No terrain reading" },
    ],
    decision: {
      question: "Should we request a scope-aligned snapshot?",
      why: "The current records come from different hosts and runtime instances.",
      suggested: "Request alignment; do not merge or rank the current records.",
      risk: "Reversible local draft. No probe is launched by this prototype.",
      choices: ["Draft an alignment request", "Inspect sources separately", "Defer"],
    },
    journey: [
      { time: "08:58", title: "Intent source observed", detail: "worktree-A · commit 12ab", kind: "Observed" },
      { time: "09:17", title: "Runtime source observed", detail: "host-B · runtime 44", kind: "Observed", className: "is-child" },
      { time: "09:41", title: "Projection source observed", detail: "host-A · runtime 51", kind: "Observed", className: "is-child" },
      { time: "09:42", title: "Join refused", detail: "Scope and time do not establish one world", kind: "Safety" },
    ],
    claims: [
      { predicate: "snapshot.consistency", value: "mixed_time", basis: "observed", coherence: "supported", evidence: "three source records", temporal: "current", owner: "Prototype adapter", observed: "09:42 JST", scope: "multiple incompatible scopes", ref: "fixture://snapshot/mixed-04" },
      { predicate: "attention.ranking", value: "insufficient_evidence", basis: "inferred", coherence: "supported", evidence: "scope mismatch", temporal: "current", owner: "Attention policy demo/v1", observed: "09:42 JST", scope: "fixture only", ref: "fixture://policy/refusal-04" },
    ],
  },
  {
    id: "contact",
    code: "QUEST-CONTACT-03",
    title: "External Contact Loop",
    primaryRegion: "value",
    regions: ["value", "intent", "work_control"],
    summary: "The outcome was measured honestly: the target was not met, and causality remains unestablished.",
    attention: "Choose what to learn next without relabeling the result as success.",
    changed: "The measurement window closed with zero verified replies.",
    importance: "A measured miss is useful evidence; hiding it would corrupt strategy.",
    known: "Zero of three target replies were observed in the fixture window.",
    unknown: "Which intervention, if any, caused the miss.",
    owner: "External outcome ledger",
    safe: "Review the measurement and draft a learning question.",
    receipt: "A future externally sourced reply receipt bound to the next measurement window.",
    warning: "missed",
    brief: [
      ["Attention", "The measured target was not met."],
      ["Why / freshness", "The external measurement window closed at 09:40 JST."],
      ["Your judgment", "Choose the next learning question, not a cosmetic status change."],
      ["Agent limits", "Agents cannot self-report external value or causal attribution."],
      ["Proof", "External replies in a versioned future window would change the result."],
    ],
    facets: [
      { label: "Specification", literal: "Specified · target 3 replies", tone: "current", symbol: "S", metaphor: "Route surveyed" },
      { label: "Permission", literal: "Not applicable in prototype", tone: "caution", symbol: "—", metaphor: "No expedition launched" },
      { label: "Execution", literal: "Window closed", tone: "current", symbol: "E", metaphor: "Expedition returned" },
      { label: "Verification", literal: "Passed · measurement bound", tone: "current", symbol: "V", metaphor: "Measurement seal intact" },
      { label: "Outcome", literal: "Measured 0 of 3 · target not met", tone: "missed", symbol: "0", metaphor: "Target remains unmet" },
    ],
    decision: {
      question: "Which learning question should guide the next proposal?",
      why: "The miss is verified, but no causal explanation has been established.",
      suggested: "Investigate message/recipient fit before changing the target.",
      risk: "A local note only. It cannot send outreach or alter the outcome ledger.",
      choices: ["Study message fit", "Study recipient fit", "Revisit the premise"],
    },
    journey: [
      { time: "01 Aug", title: "Target registered", detail: "Three externally verified replies", kind: "Declared" },
      { time: "02–08 Aug", title: "Measurement window", detail: "External owner observed replies", kind: "Observed" },
      { time: "09:40", title: "Window closed", detail: "0 of 3 replies observed", kind: "Measured" },
      { time: "09:42", title: "Target evaluated", detail: "Not met; causal attribution unknown", kind: "Verified" },
    ],
    claims: [
      { predicate: "outcome.observed_count", value: "0 of 3", basis: "verified", coherence: "supported", evidence: "external ledger receipt", temporal: "current", owner: "External outcome ledger", observed: "09:40 JST", scope: "fixture/window-2026-08-01..08", ref: "fixture://outcome/contact-03" },
      { predicate: "target.met", value: "false", basis: "verified", coherence: "supported", evidence: "0 < 3", temporal: "current", owner: "Target evaluator/v1", observed: "09:42 JST", scope: "fixture/window-2026-08-01..08", ref: "fixture://target/contact-03" },
      { predicate: "outcome.causally_attributed", value: "unknown", basis: "unknown", coherence: "unresolved", evidence: "missing", temporal: "unknown", owner: "No owner established", observed: "never", scope: "not established", ref: "missing://causality/contact-03" },
    ],
  },
];

const state = {
  selected: quests[0].id,
  lens: "world",
  view: "map",
  mode: "neutral",
  motion: "running",
  following: true,
  tourStep: 0,
  drafts: {},
};

const panel = document.querySelector("#lens-panel");
const announcer = document.querySelector("#announcer");
const tourDialog = document.querySelector("#tour-dialog");

function selectedQuest() {
  return quests.find((quest) => quest.id === state.selected) || quests[0];
}

function announce(message) {
  announcer.textContent = "";
  window.setTimeout(() => { announcer.textContent = message; }, 20);
}

function facetMarkup(facet) {
  const moving = facet.label === "Execution" && facet.tone === "current" ? "moving-unit" : "";
  return `<div class="facet tone-${facet.tone}">
    <span class="facet-label">${facet.label}</span>
    <strong class="facet-literal"><span class="facet-symbol ${moving}" aria-hidden="true">${facet.symbol}</span>${facet.literal}</strong>
    <span class="metaphor">Gameful metaphor: ${facet.metaphor}</span>
  </div>`;
}

function facetsMarkup(quest) {
  return `<div class="facet-grid" aria-label="Independent quest facets">${quest.facets.map(facetMarkup).join("")}</div>`;
}

function inspectorMarkup(quest) {
  const questions = [
    ["What is it?", `${quest.title} (${quest.code})`],
    ["What changed?", quest.changed],
    ["Why does it matter?", quest.importance],
    ["What is known?", quest.known],
    ["What is unknown?", quest.unknown],
    ["Who owns it?", quest.owner],
    ["What can I safely do?", quest.safe],
    ["What receipt would prove it?", quest.receipt],
  ];
  return `<aside class="inspector-card" aria-labelledby="inspector-title">
    <p class="card-kicker">Selection inspector</p>
    <h3 id="inspector-title">Read before acting</h3>
    <p>Literal answers remain identical in Neutral and Gameful modes.</p>
    <details class="inspector-details" open>
      <summary>Eight ownership questions</summary>
      <dl class="question-list">${questions.map(([key, value]) => `<div><dt>${key}</dt><dd>${value}</dd></div>`).join("")}</dl>
    </details>
  </aside>`;
}

function journeyMarkup(quest, compact = false) {
  const middle = quest.journey.slice(0, compact ? 3 : quest.journey.length);
  return `<section class="journey-strip-card" aria-labelledby="journey-title">
    <div class="journey-heading"><div><p class="card-kicker">Journey</p><h3 id="journey-title">Intent → run → proof → outcome</h3></div><span>Run finish never means mission complete</span></div>
    <div class="journey-strip">
      ${middle.map((event, index) => `<div class="journey-node"><span>${event.kind}</span><strong>${event.title}</strong><small>${event.time}</small></div>${index < middle.length - 1 ? '<span class="journey-arrow" aria-hidden="true">→</span>' : ""}`).join("")}
    </div>
    <p class="journey-note">${quest.receipt}</p>
  </section>`;
}

function lensIntro(title, copy) {
  return `<header class="lens-intro"><div><p class="eyebrow">${state.lens} lens</p><h2>${title}</h2><p>${copy}</p></div><div class="literal-safety">Literal state · fixture only · read-only</div></header>`;
}

function attentionMarkup(quest) {
  const warning = quest.warning === "mixed" ? "Scope mismatch" : quest.warning === "missed" ? "Measured miss" : "Judgment requested";
  return `<article class="attention-card">
    <p class="card-kicker"><span>Your attention</span><span>${warning}</span></p>
    <h3>${quest.attention}</h3>
    <p class="attention-reason">${quest.summary}</p>
    <p class="queue-line"><span>Queue</span><strong>3 local priority fixtures · 1 expanded</strong></p>
    ${facetsMarkup(quest)}
  </article>`;
}

function questButtonMarkup(quest) {
  const selected = quest.id === state.selected;
  return `<button class="quest-pin" type="button" data-quest="${quest.id}" aria-pressed="${selected}">
    <span class="pin-symbol" aria-hidden="true"><span>◇</span></span><strong>${quest.title}</strong><small>${quest.code}</small>
  </button>`;
}

function renderWorld() {
  const quest = selectedQuest();
  const map = `<div class="world-map-wrap" ${state.view === "list" ? "hidden" : ""}>
    <p class="map-summary">Seven stable regions. Quest pins are overlays, not permanent organs.</p>
    <div class="world-map" aria-label="Seven stable regions and three local quest pins">
      ${regions.map((region, index) => {
        const related = quest.regions.includes(region.id);
        const pins = quests.filter((item) => item.primaryRegion === region.id).map(questButtonMarkup).join("");
        return `<section class="region-card ${related ? "is-linked" : ""} ${quest.primaryRegion === region.id ? "is-primary" : ""}" data-region="${region.id}">
          <span class="region-number">0${index + 1}</span><h3>${region.label}</h3><p>${region.meaning}</p><span class="region-owner">Owner: ${region.owner}</span>
          ${related ? `<span class="region-touch">Selected quest touches this region</span>` : ""}${pins}
        </section>`;
      }).join("")}
    </div>
  </div>`;
  const list = `<div class="world-list" ${state.view === "map" ? "hidden" : ""}>
    <table><caption>Complete structured equivalent of the World map</caption><thead><tr><th>Region</th><th>Meaning and owner</th><th>Priority quest</th></tr></thead>
    <tbody>${regions.map((region) => {
      const pin = quests.find((item) => item.primaryRegion === region.id);
      return `<tr><td><strong>${region.label}</strong></td><td>${region.meaning}<br><span class="list-related">Owner: ${region.owner}</span></td><td>${pin ? `<button class="list-quest-button" type="button" data-quest="${pin.id}" aria-pressed="${pin.id === state.selected}"><strong>${pin.title}</strong><span>${pin.code}</span></button>` : "No priority pin"}</td></tr>`;
    }).join("")}</tbody></table>
  </div>`;
  panel.innerHTML = `${lensIntro("A calm map of what exists", "Stable terrain stays put while three local priority quests move across it.")}
    <div class="world-layout"><div>${attentionMarkup(quest)}</div>${inspectorMarkup(quest)}</div>${map}${list}${journeyMarkup(quest, true)}`;
}

function renderDecide() {
  const quest = selectedQuest();
  const draft = state.drafts[quest.id];
  panel.innerHTML = `${lensIntro("One judgment at a time", "Choices become local proposal notes only. They cannot grant permission or execute an effect.")}
    <div class="lens-single-column"><div class="projection-only-banner"><span class="banner-symbol" aria-hidden="true">◇</span><div><strong>Proposal-only boundary</strong><span>Queue: 3 · this page has no command route, credentials, or live action.</span></div></div>
    <article class="decision-card"><p class="card-kicker">Decision for ${quest.code}</p><div class="decision-core">
      <div class="decision-question"><span class="question-label">Question</span><h3>${quest.decision.question}</h3><p><strong>Why now:</strong> ${quest.decision.why}</p></div>
      <div class="suggested-option"><span class="question-label">Suggested option <span class="ai-label">AI conclusion</span></span><p>${quest.decision.suggested}</p></div>
      <form id="decision-form"><fieldset class="choice-fieldset"><legend>Choose what to save as a local draft</legend><div class="choice-list">
        ${quest.decision.choices.map((choice, index) => `<label class="choice-option"><input type="radio" name="choice" value="${choice}" ${index === 0 ? "checked" : ""}><span><strong>${choice}</strong><span>No external effect</span></span></label>`).join("")}
      </div></fieldset><p class="risk-line"><strong>Risk / reversibility:</strong> ${quest.decision.risk}</p>
      <div class="draft-note"><label for="draft-note">Optional reasoning note</label><textarea id="draft-note" rows="3" placeholder="What would you want the real owner to know?"></textarea></div>
      <div class="draft-actions"><button class="primary-button" type="submit">Save local draft</button><button class="quiet-button" type="button" disabled title="No live command surface in this prototype">Live action unavailable</button></div>
      <p class="draft-status" id="draft-status" role="status">${draft ? `Saved locally in memory: ${draft.choice}` : "Nothing has been proposed in this tab."}</p></form>
    </div></article>${inspectorMarkup(quest)}</div>`;
}

function renderRun() {
  const quest = selectedQuest();
  panel.innerHTML = `${lensIntro("A human-readable journey", "Observed run events are separate from verification and real-world outcome.")}
    <div class="lens-single-column"><div class="${quest.warning === "mixed" ? "mixed-time-banner" : "safe-banner"}"><span class="banner-symbol" aria-hidden="true">${quest.warning === "mixed" ? "?" : "●"}</span><div><strong>${quest.warning === "mixed" ? "Mixed-time run view" : "Observed fixture journey"}</strong><span>${quest.warning === "mixed" ? "Events remain separate because scopes do not safely join." : "Following can pause without changing the underlying fixture."}</span></div></div>
    <article class="run-card"><div class="run-header"><div><p class="card-kicker">${quest.code}</p><h3>${quest.title}</h3><p>${quest.summary}</p></div><div class="run-controls"><button class="quiet-button" id="follow-toggle" type="button" aria-pressed="${state.following}">${state.following ? "Pause following" : "Resume following"}</button><span class="run-status">${state.following ? "Following latest" : "View paused"}</span></div></div>
      <ol class="run-timeline">${quest.journey.map((event) => `<li class="run-event ${event.className || ""}"><time class="event-time">${event.time}</time><span class="event-marker" aria-hidden="true"></span><div class="event-copy"><strong>${event.title}</strong><span>${event.detail}</span><span class="event-kind">${event.kind}</span></div></li>`).join("")}</ol>
      <div class="run-legend"><strong>Literal rule</strong><span>A finished run is only a process event. It does not prove task completion, verification, or outcome.</span></div>
      <section class="resumption-packet"><h4>If you return later</h4><ul><li>Last selected: ${quest.title}</li><li>Next irreversible boundary: none in prototype</li><li>Unknown: ${quest.unknown}</li><li>Proof needed: ${quest.receipt}</li></ul></section>
    </article>${inspectorMarkup(quest)}</div>`;
}

function renderEvidence() {
  const quest = selectedQuest();
  const bannerClass = quest.warning === "mixed" ? "mixed-time-banner" : quest.warning === "stale" ? "stale-banner" : "safe-banner";
  panel.innerHTML = `${lensIntro("Claims you can challenge", "Every claim keeps its basis, coherence, evidence, time, scope, and owner separate.")}
    <div class="lens-single-column"><div class="${bannerClass}"><span class="banner-symbol" aria-hidden="true">${quest.warning === "mixed" ? "?" : quest.warning === "stale" ? "!" : "●"}</span><div><strong>${quest.warning === "mixed" ? "Cannot safely join sources" : quest.warning === "stale" ? "Some proof is stale or contradicted" : "Measurement is current"}</strong><span>No score or color compresses these dimensions.</span></div></div>
    <article class="evidence-card"><div class="evidence-summary"><div><p class="card-kicker">Evidence packet</p><h3>${quest.title}</h3></div><span class="scope-chip">Fixture-only snapshot</span></div>
      <div class="claim-stack">${quest.claims.map((claim) => `<section class="claim-card"><h3>${claim.predicate}</h3><p class="claim-value">${claim.value}</p><div class="claim-meta"><span>Basis: ${claim.basis}</span><span class="${claim.coherence === "contradicted" ? "meta-conflict" : "meta-current"}">Coherence: ${claim.coherence}</span><span class="${claim.temporal === "stale" || claim.temporal === "unknown" ? "meta-caution" : "meta-current"}">Time: ${claim.temporal}</span></div>
        <dl class="evidence-dl"><div><dt>Evidence status</dt><dd>${claim.evidence}</dd></div><div><dt>Truth owner</dt><dd>${claim.owner}</dd></div><div><dt>Observed</dt><dd>${claim.observed}</dd></div><div><dt>Scope</dt><dd>${claim.scope}</dd></div></dl><div class="evidence-refs"><span class="evidence-ref">${claim.ref}</span></div></section>`).join("")}</div>
      <div class="provenance-chain"><div><strong>Owner</strong><span>Named per claim</span></div><span class="provenance-arrow" aria-hidden="true">→</span><div><strong>Projection</strong><span>World Deck fixture adapter</span></div><span class="provenance-arrow" aria-hidden="true">→</span><div><strong>Transport</strong><span>Local JavaScript only</span></div></div>
    </article>${inspectorMarkup(quest)}</div>`;
}

function updateBrief(quest) {
  document.querySelector(".brief-lines").innerHTML = quest.brief.map(([label, copy]) => `<li><span>${label}</span><strong>${copy}</strong></li>`).join("");
  document.querySelector("#selection-ribbon-title").textContent = quest.title;
  document.querySelector("#selection-ribbon-code").textContent = quest.code;
}

function bindDynamicEvents() {
  document.querySelectorAll("[data-quest]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selected = button.dataset.quest;
      render();
      announce(`${selectedQuest().title} selected. ${state.lens} lens updated.`);
    });
  });
  document.querySelector("#decision-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    state.drafts[state.selected] = { choice: form.get("choice"), note: form.get("draft-note") || "" };
    document.querySelector("#draft-status").textContent = `Saved locally in memory: ${form.get("choice")}. No command was sent.`;
    announce("Local proposal draft saved. No command was sent.");
  });
  document.querySelector("#follow-toggle")?.addEventListener("click", () => {
    state.following = !state.following;
    renderRun();
    bindDynamicEvents();
    announce(state.following ? "Following latest fixture event." : "Run view paused. Selection preserved.");
  });
}

function render() {
  const quest = selectedQuest();
  updateBrief(quest);
  document.querySelector("#world-view-switch").hidden = state.lens !== "world";
  document.querySelectorAll(".lens-tab").forEach((tab) => {
    const active = tab.dataset.lens === state.lens;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  if (state.lens === "world") renderWorld();
  if (state.lens === "decide") renderDecide();
  if (state.lens === "run") renderRun();
  if (state.lens === "evidence") renderEvidence();
  panel.setAttribute("aria-labelledby", `tab-${state.lens}`);
  bindDynamicEvents();
}

document.querySelectorAll(".lens-tab").forEach((tab, index, tabs) => {
  tab.addEventListener("click", () => { state.lens = tab.dataset.lens; render(); announce(`${tab.textContent.trim()} lens selected.`); });
  tab.addEventListener("keydown", (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    tabs[next].focus(); tabs[next].click();
  });
});

document.querySelectorAll(".view-button").forEach((button) => {
  button.addEventListener("click", () => {
    state.view = button.dataset.view;
    document.querySelectorAll(".view-button").forEach((item) => {
      const active = item === button; item.classList.toggle("is-active", active); item.setAttribute("aria-pressed", String(active));
    });
    render(); announce(`${state.view === "map" ? "Map" : "List"} view selected.`);
  });
});

document.querySelectorAll(".mode-button").forEach((button) => {
  button.addEventListener("click", () => {
    state.mode = button.dataset.mode;
    document.body.dataset.mode = state.mode;
    document.querySelectorAll(".mode-button").forEach((item) => {
      const active = item === button; item.classList.toggle("is-active", active); item.setAttribute("aria-pressed", String(active));
    });
    announce(`${state.mode} presentation selected. Facts and permissions are unchanged.`);
  });
});

document.querySelector("#motion-toggle").addEventListener("click", (event) => {
  state.motion = state.motion === "running" ? "paused" : "running";
  document.body.dataset.motion = state.motion;
  event.currentTarget.setAttribute("aria-pressed", String(state.motion === "paused"));
  event.currentTarget.lastChild.textContent = state.motion === "paused" ? " Motion: paused" : " Motion: on";
  announce(`Motion ${state.motion}.`);
});

document.querySelector("#orientation-dismiss").addEventListener("click", () => {
  document.querySelector("#orientation-hint").hidden = true;
  announce("Quick orientation dismissed.");
});

const tourSteps = [
  ["Start with the three quest pins", "They are local priorities laid over seven stable regions. Selecting one never changes the underlying system."],
  ["Change the lens, keep the object", "World, Decide, Run, and Evidence answer different questions about the same selected quest."],
  ["Read status as separate facts", "Permission, execution, verification, freshness, contradiction, and outcome never collapse into one score."],
  ["Nothing here can execute", "Decisions save only in this browser tab. The prototype has no live APIs, credentials, or command route."],
];

function updateTour() {
  const [title, copy] = tourSteps[state.tourStep];
  document.querySelector("#tour-progress").textContent = `Step ${state.tourStep + 1} of ${tourSteps.length}`;
  document.querySelector("#tour-title").textContent = title;
  document.querySelector("#tour-copy").textContent = copy;
  document.querySelector("#tour-back").disabled = state.tourStep === 0;
  document.querySelector("#tour-next").textContent = state.tourStep === tourSteps.length - 1 ? "Finish" : "Next";
}

document.querySelector("#tour-open").addEventListener("click", () => {
  state.tourStep = 0; updateTour();
  if (typeof tourDialog.showModal === "function") tourDialog.showModal(); else tourDialog.setAttribute("open", "");
});
document.querySelector("#tour-close").addEventListener("click", () => tourDialog.close());
document.querySelector("#tour-back").addEventListener("click", () => { state.tourStep = Math.max(0, state.tourStep - 1); updateTour(); });
document.querySelector("#tour-next").addEventListener("click", () => {
  if (state.tourStep === tourSteps.length - 1) { tourDialog.close(); announce("Tour complete."); return; }
  state.tourStep += 1; updateTour();
});
tourDialog.addEventListener("click", (event) => { if (event.target === tourDialog) tourDialog.close(); });

if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  state.motion = "paused";
  document.body.dataset.motion = "paused";
  const motionButton = document.querySelector("#motion-toggle");
  motionButton.setAttribute("aria-pressed", "true");
  motionButton.lastChild.textContent = " Motion: paused";
}

render();

import type {OutlineItem, TabSpec, TranscriptLine} from "./types";

function line(id: string, kind: TranscriptLine["kind"], text: string): TranscriptLine {
  return {id, kind, text};
}

export function buildInitialTabs(): TabSpec[] {
  return [
    {
      id: "chat",
      title: "Chat",
      kind: "chat",
      lines: [
        // FACE-1 zen-pure welcome: at most 2 short dim lines (thinking kind = dim).
        line("boot-1", "thinking", "Dharma Helm · Quiet Field"),
        line("boot-2", "thinking", "Type a message below · F2 unfolds the Whole Helm"),
      ],
    },
    {
      id: "mission",
      title: "Mission",
      kind: "mission",
      lines: [
        line("mission-1", "system", "?[?] UNKNOWN · Mission Control projection not observed."),
        line("mission-2", "thinking", "No live mission, task, or execution state is claimed in this frame."),
      ],
    },
    {
      id: "repo",
      title: "Repo",
      kind: "repo",
      lines: [
        line("repo-1", "system", "?[?] UNKNOWN · workspace owner projection not observed."),
        line("repo-2", "thinking", "Path labels are local context; Git state awaits an authoritative snapshot."),
      ],
    },
    {
      id: "commands",
      title: "Commands",
      kind: "commands",
      lines: [
        line("commands-1", "system", "STATIC GUIDE · local command catalog; execution state UNKNOWN."),
        line("commands-2", "thinking", "A listed command grants no authority and proves no effect."),
      ],
    },
    {
      id: "models",
      title: "Models",
      kind: "models",
      lines: [
        line("models-1", "system", "?[?] UNVERIFIED · route policy owner projection not observed."),
      ],
    },
    {
      id: "ontology",
      title: "Ontology",
      kind: "ontology",
      lines: [
        line("ontology-1", "system", "?[?] UNKNOWN · ontology owner projection not observed."),
        line("ontology-2", "thinking", "No concept freshness or authority is inferred from local labels."),
      ],
    },
    {
      id: "runtime",
      title: "Runtime",
      kind: "runtime",
      lines: [
        line("runtime-1", "system", "?[?] UNKNOWN · runtime owner projection not observed."),
        line("runtime-2", "thinking", "Bridge presence alone is not executor liveness."),
      ],
    },
    {
      id: "sessions",
      title: "Sessions",
      kind: "sessions",
      lines: [
        line("sessions-1", "system", "?[?] UNKNOWN · session catalog owner projection not observed."),
        line("sessions-2", "thinking", "No session is resumed or active from this placeholder."),
      ],
    },
    {
      id: "approvals",
      title: "Approvals",
      kind: "approvals",
      lines: [
        line("approvals-1", "system", "?[?] UNKNOWN · permission owner projection not observed."),
        line("approvals-2", "thinking", "An empty view grants no permission and authorizes no effect."),
      ],
    },
    {
      id: "control",
      title: "Control",
      kind: "control",
      lines: [
        line("control-1", "system", "?[?] UNKNOWN · control owner projection not observed."),
      ],
    },
    {
      id: "agents",
      title: "Agents",
      kind: "agents",
      lines: [
        line("agents-1", "system", "?[?] UNKNOWN · agent-route owner projection not observed."),
      ],
    },
    {
      id: "evolution",
      title: "Evolution",
      kind: "evolution",
      lines: [
        line("evolution-1", "system", "?[?] UNKNOWN · evolution owner projection not observed."),
      ],
    },
  ];
}

export function buildInitialOutline(): OutlineItem[] {
  return [
    {id: "toc-chat", label: "Live Chat", depth: 1, targetTabId: "chat"},
    {id: "toc-mission", label: "Mission", depth: 1, targetTabId: "mission"},
    {id: "toc-goal", label: "Goal", depth: 2, targetTabId: "mission"},
    {id: "toc-principles", label: "Principles", depth: 2, targetTabId: "mission"},
    {id: "toc-repo", label: "Repo", depth: 1, targetTabId: "repo"},
    {id: "toc-commands", label: "Commands", depth: 1, targetTabId: "commands"},
    {id: "toc-models", label: "Models", depth: 1, targetTabId: "models"},
    {id: "toc-ontology", label: "Ontology", depth: 1, targetTabId: "ontology"},
    {id: "toc-runtime", label: "Runtime", depth: 1, targetTabId: "runtime"},
    {id: "toc-sessions", label: "Sessions", depth: 1, targetTabId: "sessions"},
    {id: "toc-approvals", label: "Approvals", depth: 1, targetTabId: "approvals"},
    {id: "toc-control", label: "Control", depth: 1, targetTabId: "control"},
    {id: "toc-agents", label: "Agents", depth: 1, targetTabId: "agents"},
    {id: "toc-evolution", label: "Evolution", depth: 1, targetTabId: "evolution"},
  ];
}

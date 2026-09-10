# Omarchy patterns and an OpenCode-backed Helm workbench

```yaml
document_role: reference
status: DATED_RESEARCH_SNAPSHOT
date: 2026-09-10
scope: Omarchy interaction patterns and OpenCode v1.18.30 integration research
authority: none of its own
subordinate_to:
  - CLAUDE.md
  - docs/governance/SOVEREIGN_MANIFEST.md
  - docs/governance/CANONICAL_DOC_STACK.md
  - docs/plans/helm_legone/HELM_LEGONE_SPEC.md
supports:
  - docs/plans/helm_legone/HELM_WAYFINDER_E2E_PROTOTYPE_PLAN_20260901.md
replaces: nothing
```

This dated research reference supports the operator-directed usability correction in
[the working plan, §11.10](HELM_WAYFINDER_E2E_PROTOTYPE_PLAN_20260901.md#1110-usability-correction--2026-09-10).
It preserves the completed source and screenshot review; it does not introduce a
second implementation plan or change repository canon. Upstream defaults below are
research observations, distinct from the Helm-specific bindings in that plan.

The original report, source archives, downloaded screenshots, and provenance
receipts remain under `~/.dharma/helm-usability/research/`. Artifact filenames and
`screenshots/` paths below refer to that external directory, not files in this
checkout. Runtime and GUI acceptance evidence remain outside this reference.

Research date: 2026-09-10. Primary-source inspection only. Downloaded source and official screenshot assets were inspected without running installers, agent commands, or changing the repository, macOS settings, or window manager.

**Recommendation:** compose a usable coding workbench around the installed OpenCode executable, with Helm/Dharma providing project context, coordination, and diagnostics. Preserve OpenCode's coding session identity across model switches and window reopening. Keep the current Helm cockpit as a separate diagnosable surface. This is an implementation recommendation, not an assertion that a custom Dharma backend already satisfies OpenCode's protocol.

## What Omarchy actually contributes

The old `basecamp/omarchy` URL redirects to `omacom/omarchy`; the current source branch is `quattro`. The current manual lives at omarchy.org/manual. The older learn.omacom.io manual is explicitly for Omarchy 3, so it should not drive current defaults. [Canonical source](https://github.com/omacom/omarchy), [current manual](https://omarchy.org/manual/), [older manual](https://learn.omacom.io/2/the-omarchy-manual).

Omarchy composes established applications behind consistent launch, focus, theme, and discovery controls. Its agent launcher chooses an installed coding CLI, supplies a dedicated app identity, and opens it in the preferred terminal. The default-agent choice and stable launch shortcut survive changes in the selected tool. That is a closer match to the user's immediate need than rebuilding an entire coding UI. [AI manual](https://omarchy.org/manual/ai/), [agent launcher](https://github.com/omacom/omarchy/blob/8ea51516390320f8e768808b230098e67bdaa82c/bin/omarchy-agent), [default-agent selector](https://github.com/omacom/omarchy/blob/8ea51516390320f8e768808b230098e67bdaa82c/bin/omarchy-default-agent).

| Observed interaction | Concrete Helm application |
| --- | --- |
| Super+Space main menu and Super+K shortcut discovery | One visible command palette; retain an always-findable shortcuts entry. |
| Focus-or-launch resolves an existing window before launching | Reopen the exact managed workbench window/seat; avoid duplicate owners. |
| Stable terminal/browser/agent keys despite alternative applications | Bind semantic actions such as Open Coding Workspace, Models, Sessions, and Cancel. |
| tmux session persistence and editor/agent/shell layouts | Keep coding dominant, diagnostics/context secondary; preserve an exact session receipt when the window closes. |
| Scratchpad and floating/tiled/fullscreen controls | Make focus and recovery available without trapping the user inside a borderless window. |

These mappings are design inferences from the [navigation manual](https://omarchy.org/manual/navigation/), [hotkeys manual](https://omarchy.org/manual/hotkeys/), [terminal manual](https://omarchy.org/manual/terminal/), and [tmux layout functions](https://github.com/omacom/omarchy/blob/8ea51516390320f8e768808b230098e67bdaa82c/default/bash/fns/tmux). Their literal Linux global shortcuts should not be copied onto macOS without checking conflicts.

Omarchy's focus script uses Hyprland window metadata, and its launcher uses evaluated shell text. Copy the identity-based interaction, not its platform-specific matching/evaluation mechanism. For Helm, retain typed argv and an explicit managed socket/session/window identity. [Focus implementation](https://github.com/omacom/omarchy/blob/8ea51516390320f8e768808b230098e67bdaa82c/bin/omarchy-launch-or-focus), [TUI identity wrapper](https://github.com/omacom/omarchy/blob/8ea51516390320f8e768808b230098e67bdaa82c/bin/omarchy-launch-or-focus-tui).

The current agent script passes automatic-approval options to several CLIs, including OpenCode's `--auto`. Those are Omarchy's operational choices. A static review or matching theme does not grant Dharma execution authority; the new launcher should not silently inherit that mode. [Exact launcher flags](https://github.com/omacom/omarchy/blob/8ea51516390320f8e768808b230098e67bdaa82c/bin/omarchy-agent), [OpenCode CLI auto option](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/opencode/src/cli/cmd/tui.ts).

## The mature coding interface

OpenCode already supplies a searchable model picker, provider grouping, recent/favorite models, persistent sessions, external-editor prompts, file mentions, shell/tool output, diffs, and interruption. Its picker changes the selected provider/model. The prompt sender then passes that choice with the existing `sessionID`; it creates a new session only when no session exists. That directly supports conversation continuity while changing models. [Model picker](https://github.com/anomalyco/opencode/blob/a9a6fad0fae42af99b9f4b1d4ff519a979f16c90/packages/tui/src/component/dialog-model.tsx), [v1.18.30 prompt sender](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/tui/src/component/prompt/index.tsx), [TUI manual](https://opencode.ai/docs/tui/).

| User action | OpenCode v1.18.30 default |
| --- | --- |
| Commands | Ctrl+P |
| Model picker | Ctrl+X, then M |
| Next/previous recent model | F2 / Shift+F2 |
| Sessions | Ctrl+X, then L |
| New session | Ctrl+X, then N |
| Interrupt current request | Escape |
| External editor | Ctrl+X, then E |
| Reasoning/model variant | Ctrl+T |
| Agent mode | Tab / Shift+Tab |
| Newline without submission | Ctrl+J; also Shift/Ctrl/Alt+Enter where terminal encoding supports it |
| Exit application | Ctrl+C, Ctrl+D, or Ctrl+X then Q |

Defaults are from the [pinned keybind definitions](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/tui/src/config/keybind.ts), not guessed key handling. On a Mac, the launcher or UI may need to show the function-key modifier required by the user's keyboard settings; that needs actual GUI verification.

Use the provider registry and connected account state to populate frontier choices. A marketing label should never substitute for the actual `providerID/modelID`. Recent and favorite models are persisted independently of chat messages. Selecting another model does not itself erase a transcript. [Model state](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/tui/src/context/local.tsx), [model/provider docs](https://opencode.ai/docs/models/).

## Exact installed-version configuration

The GitHub tag `v1.18.30` resolves to commit `3104c1428ec91f809e5ab86631300de41eb6952e`. The initially downloaded development archive is a different, newer commit; the version-specific files cited below were downloaded separately. [Release tag](https://github.com/anomalyco/opencode/tree/v1.18.30), local `opencode-v1.18.30-tag.json` and `opencode-v1.18.30-selected-source.json` record the resolution/downloads.

**Runtime configuration is merged, not replaced.** Source order is remote well-known defaults → global files → `OPENCODE_CONFIG` → project files → discovered `.opencode` directories/custom config directory → `OPENCODE_CONFIG_CONTENT` → active organization configuration → managed files → macOS managed preferences. Global files merge `config.json`, `opencode.json`, then `opencode.jsonc`. `OPENCODE_CONFIG_DIR` is appended to the discovered config directories. `OPENCODE_DISABLE_PROJECT_CONFIG=1` disables project-file discovery, but does not disable the global or home `.opencode` paths. [Runtime loader](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/opencode/src/config/config.ts), [discovery](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/opencode/src/config/paths.ts), [flags](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/core/src/flag/flag.ts).

**TUI configuration has its own precedence.** Global `tui.json` then `tui.jsonc` → `OPENCODE_TUI_CONFIG` → project TUI files root-first → discovered `.opencode` directories → `OPENCODE_CONFIG_DIR` TUI files. Therefore the explicit TUI filename is not the highest-priority override. Invalid TUI config is logged and skipped, so a zero process exit alone does not prove the desired configuration loaded. [Exact TUI loader](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/opencode/src/config/tui.ts).

**Isolation:** `OPENCODE_CONFIG` and `OPENCODE_CONFIG_DIR` do not replace the global XDG paths. Set subprocess-scoped `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, and `XDG_STATE_HOME` to private runtime directories when reproducibility is wanted. Choose `XDG_DATA_HOME` intentionally: a private value gives a separate data/session/auth store; sharing it retains existing OpenCode identity/history. Do not copy secrets into generated config. Custom `Global.Path` values are fixed from XDG at process initialization. [Global paths](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/core/src/global.ts).

A minimal compatible TUI file (explicit defaults shown for review):

```json
{
  "$schema": "https://opencode.ai/tui.json",
  "theme": "tokyonight",
  "mouse": true,
  "diff_style": "auto",
  "keybinds": {
    "leader": "ctrl+x",
    "command_list": "ctrl+p",
    "model_list": "<leader>m",
    "model_cycle_recent": "f2",
    "model_cycle_recent_reverse": "shift+f2",
    "session_list": "<leader>l",
    "session_interrupt": "escape"
  }
}
```

Theme/keybind settings belong here, not inside `opencode.json`. Key overrides accept simple strings, comma-separated alternatives, arrays/structured bindings, and `"none"`/`false` for disabling a binding. The leader timeout defaults to 2000 ms. [TUI schema](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/tui/src/config/index.tsx), [binding schema](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/tui/src/config/keybind.ts).

Runtime config uses `$schema: https://opencode.ai/config.json`; `model` and `small_model` are `provider-id/model-id` strings, and `provider` is an object keyed by provider ID. Built-in providers do not need to be redeclared merely to select one of their models. Custom provider entries support `npm`, `name`, `options.baseURL`, `options.apiKey`, and a `models` map. Model entries can declare display names, options, variants, limits, modalities, and tool support. Populate these only from a verified backend contract. `enabled_providers` is an allowlist; `disabled_providers` suppresses automatic providers. [Runtime schema](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/core/src/v1/config/config.ts), [provider schema](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/core/src/v1/config/provider.ts), [official providers guide](https://opencode.ai/docs/providers/).

Illustrative custom-provider shape, with deliberate placeholders rather than fabricated model availability:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "verified-provider/verified-model-id",
  "provider": {
    "verified-provider": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Verified compatible endpoint",
      "options": {
        "baseURL": "https://verified-endpoint.example/v1",
        "apiKey": "{env:VERIFIED_PROVIDER_API_KEY}"
      },
      "models": {
        "verified-model-id": { "name": "Verified model display name" }
      }
    }
  }
}
```

The endpoint above is not runnable configuration. The launcher should enumerate or verify real configured provider IDs before selecting its default, and visibly preserve an unavailable-provider error instead of silently falling back to an unrelated model. [Provider guide](https://opencode.ai/docs/providers/), [model guide](https://opencode.ai/docs/models/).

## Theme and visual assets

Omarchy keeps semantic colors in `themes/<name>/colors.toml` and adapts them to applications. Theme updates separate fast visible changes from slower external hooks. This suggests one Helm palette feeding WezTerm, OpenCode, and the companion view without restarting the coding owner. [Theme application](https://github.com/omacom/omarchy/blob/8ea51516390320f8e768808b230098e67bdaa82c/bin/omarchy-theme-set), [theme manual](https://omarchy.org/manual/themes/).

| Omarchy palette | Background | Foreground | Accent |
| --- | --- | --- | --- |
| Tokyo Night | `#1a1b26` | `#a9b1d6` | `#7aa2f7` |
| Osaka Jade | `#111c18` | `#C1C497` | `#509475` |
| Everforest | `#2d353b` | `#d3c6aa` | `#7fbbb3` |

Values come from the pinned [Tokyo Night](https://github.com/omacom/omarchy/blob/8ea51516390320f8e768808b230098e67bdaa82c/themes/tokyo-night/colors.toml), [Osaka Jade](https://github.com/omacom/omarchy/blob/8ea51516390320f8e768808b230098e67bdaa82c/themes/osaka-jade/colors.toml), and [Everforest](https://github.com/omacom/omarchy/blob/8ea51516390320f8e768808b230098e67bdaa82c/themes/everforest/colors.toml) source files. OpenCode's built-in `tokyonight` shares the Tokyo Night base background but has a different full semantic palette; it is a quick compatible choice, not an exact palette clone. [Built-in OpenCode theme](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/tui/src/theme/assets/tokyonight.json).

Custom OpenCode theme files use `$schema: https://opencode.ai/theme.json`, optional reusable `defs`, and a `theme` object with semantic roles. Values can be hex colors, ANSI indexes, dark/light mappings, or references. In v1.18.30 the native theme source scans `Global.Path.config/themes/*.json` and `.opencode/themes` directories along cwd ancestry; it does **not** directly add `OPENCODE_CONFIG_DIR`. Put an isolated custom theme under `$XDG_CONFIG_HOME/opencode/themes/`. Avoid duplicate theme filenames across ancestors because source iteration defines the winner. [Theme discovery](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/tui/src/context/theme.tsx), [theme format](https://opencode.ai/docs/themes/).

Official screenshots downloaded from the manual:

- `screenshots/tokyo-night-preview.webp` — [original](https://omarchy.org/manual/images/tokyo-night-preview.webp).
- `screenshots/osaka-jade-preview.webp` — [original](https://omarchy.org/manual/images/osaka-jade-preview.webp).
- `screenshots/everforest-preview.webp` — [original](https://omarchy.org/manual/images/everforest-preview.webp).

The inspected Tokyo Night preview has a dominant editor on the left, diagnostics above a supporting file view on the right, and a consistent background/accent. Its translucency reduces code contrast. Recommendation: preserve that composition and palette while making the Helm coding window opaque with normal title/close controls. This is a visual judgment, not an Omarchy requirement. Asset URLs, byte sizes, and SHA-256 digests are in `screenshot-downloads.json`.

## Build versus integrate

| Route | Assessment |
| --- | --- |
| Launch OpenCode as the coding seat, Dharma as companion | Recommended now. Uses existing model/session/editor mechanics with the smallest integration surface. Store an explicit harness name, project, and OpenCode session ID; label history ownership truthfully. |
| OpenCode TUI against a Dharma compatibility gateway | Feasible research direction, not a drop-in. Requires OpenCode-compatible endpoints/events and lifecycle semantics, not merely chat completions. |
| Continue rebuilding a full coding UI inside Helm | Highest immediate implementation burden. Justified only by specific workflows that mature clients cannot support; keep urgent recovery/model/session fixes regardless. |

OpenCode's TUI is a client of its HTTP API and event stream. `opencode attach URL` connects to an existing OpenCode server; starting a separate `serve` process creates another server, not an attachment to a running TUI owner. The API covers sessions, messages, parts, aborts, permissions, providers, files, diffs, and events. [Server docs](https://opencode.ai/docs/server/), [attach CLI](https://opencode.ai/docs/cli/).

The standalone TUI's SDK provider can accept custom `fetch` and event implementations, providing a real transport seam. Its stores still assume OpenCode session/message/permission/provider schemas, and hydration reconciles streaming events with loaded history. UI events are batched around 16 ms. These are architecture observations, not an end-to-end latency benchmark. It uses OpenTUI/Solid, so transplanting the package into Helm's current React/Ink UI is not a trivial component import. [SDK transport](https://github.com/anomalyco/opencode/blob/a9a6fad0fae42af99b9f4b1d4ff519a979f16c90/packages/tui/src/context/sdk.tsx), [sync stores](https://github.com/anomalyco/opencode/blob/a9a6fad0fae42af99b9f4b1d4ff519a979f16c90/packages/tui/src/context/sync.tsx), [TUI package](https://github.com/anomalyco/opencode/blob/a9a6fad0fae42af99b9f4b1d4ff519a979f16c90/packages/tui/package.json).

OpenCode's ACP command exposes OpenCode as an agent subprocess to compatible editor clients. It does not establish that the OpenCode TUI can consume an arbitrary ACP backend. Plugins offer tool and event hooks, but blanket coverage of every effect path must be verified before calling a custom integration authority-enforcing. [ACP docs](https://opencode.ai/docs/acp/), [plugin docs](https://opencode.ai/docs/plugins/).

Acceptance checks for the implementation: launch/focus without duplicate owner; move/resize/close via ordinary controls; reopen the same recorded session; switch provider/model without losing draft or history; interrupt a streaming turn promptly; reconnect without duplicated messages; show unavailable authentication/model states truthfully; read a repository file, propose/edit code, inspect a diff, and run a bounded check. Measure actual startup and interaction latency rather than inferring performance from a theme or framework.

## Provenance and limits

Downloaded Omarchy archive: commit `8ea51516390320f8e768808b230098e67bdaa82c`, 71,266,484 bytes, SHA-256 `656fbecd08b096519cbc3d9922f3c6917e1ebd7be0bf4421be84ec4362bfb9f4`.

Downloaded OpenCode development archive: commit `a9a6fad0fae42af99b9f4b1d4ff519a979f16c90`, 81,487,357 bytes, SHA-256 `485d351f1ded322211adacacbe526a5092205fb65efb71e963bab620735e232c`. Exact installed-version configuration was subsequently checked against the separate `v1.18.30` source files described above. `source-downloads.json` records original codeload URLs and extraction directories.

Both repositories include permissive license texts. Preserve their notices when reusing covered source; screenshot downloads here are inspection assets, not a claim that every wallpaper/brand asset has the same reuse terms. [Omarchy license](https://github.com/omacom/omarchy/blob/8ea51516390320f8e768808b230098e67bdaa82c/LICENSE), [OpenCode license](https://github.com/anomalyco/opencode/blob/a9a6fad0fae42af99b9f4b1d4ff519a979f16c90/LICENSE).

This lane did not authenticate providers, execute coding requests, or verify the local binary's reported non-TTY stdout truncation. Those are implementation/runtime checks owned by the root task. No claims of successful live coding, session migration, GUI usability, or measured latency are made by this report.

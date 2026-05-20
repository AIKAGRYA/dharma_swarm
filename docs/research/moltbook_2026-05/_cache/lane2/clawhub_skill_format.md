# ClawHub Skill Manifest Format

**Source:** https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md (skill-format.md in clawhub repo)

## Minimum required file
A skill is a folder containing `SKILL.md` (or `skill.md`).

## Required frontmatter fields
- `name` — skill identifier
- `description` — short summary
- `version` — semantic version

## Capability declarations (under `metadata.openclaw`)
- `requires.env` — required environment variables
- `requires.bins` — CLI binaries that must exist
- `requires.anyBins` — at least one of these binaries must exist
- `requires.config` — config file paths the skill reads
- `primaryEnv` — main credential variable
- `envVars` — per-variable metadata with `required` flag
- `os` — OS restrictions (e.g., `["macos"]`)
- `install` — dependency specs: `brew`, `node`, `go`, `uv`

## What is NOT in the manifest
- **No sandboxing model.** The format declares what a skill *needs* (env vars, binaries, packages) but does not restrict what a skill *can do* at runtime.
- **No code-execution capability declaration.** A skill that runs `curl … | sh` looks the same to ClawHub as a skill that doesn't.
- **No signing.** Publisher requirement is "a GitHub account at least one week old."
- **No provenance.** No supply-chain attestation, no SBOM, no reproducible-build hash.

## Example
```yaml
---
name: skill-id
description: What it does
version: 1.0.0
metadata:
  openclaw:
    requires:
      env: [VAR_NAME]
      bins: [binary]
    primaryEnv: VAR_NAME
    envVars:
      - name: VAR_NAME
        required: true
        description: Purpose
---
```

## Install path
`npm i -g clawhub` → `clawhub install <slug>` → installs into `./skills` under cwd → records versions in `.clawhub/lock.json`.

---
name: issue-to-product-tech-spec
description: Use when turning a GitHub issue, user request, or research insight into DS PRODUCT.md and TECH.md specs before implementation.
---

# Issue To Product/Tech Spec

## Purpose

Convert a substantial request into behavior-first and implementation-first specs that agents can execute safely.

## Inputs

- Issue number, user request, or research report
- Relevant current code paths
- Known non-goals and no-touch zones
- Expected tests or acceptance criteria

## Procedure

1. Create `specs/<work-id>/PRODUCT.md` from the template.
2. Describe user/operator-visible behavior as numbered invariants.
3. Create `specs/<work-id>/TECH.md` from the template.
4. Read current code before proposing implementation paths.
5. List exact files likely to change, tests to run, risks, rollback, and out-of-scope areas.
6. If the work is too small for both specs, write a no-spec rationale in the PR or report.

## Stop Conditions

- The issue lacks enough detail to define testable behavior.
- The requested implementation conflicts with canonical DS substrates.
- The work would require touching protected dharma boundary files without explicit approval.

## Required Final Report

- Spec directory created
- Product invariants
- Technical plan summary
- Non-goals
- Open questions
- Recommended implementation slice

## Non-Goals

- No implementation
- No runtime writes
- No issue closure
- No broad architecture rewrite

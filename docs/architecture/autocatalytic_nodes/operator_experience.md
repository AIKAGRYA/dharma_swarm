---
title: Operator Experience Membrane
status: active_reference
authority: projection_only
---

# Operator Experience Membrane

Producer: the shipped Helm JSON bridge and terminal approval store project runtime truth to the operator. This candidate node is bound to `organism-rewire-2026-07`, which retains the operator-facing organism membrane after the Helm track retired.

Contract: consume `verified_release`; apply `request_operator_authority`; emit `authorized_action` to [External Value Delivery](external_value_delivery.md).

Proof surfaces: [`terminal_bridge.py`](../../../dharma_swarm/terminal_bridge.py) and [`test_terminal_bridge.py`](../../../tests/test_terminal_bridge.py).

Current adapter projection: `helm.read_only_authorization_projection` reads a bounded terminal-control projection plus the Helm work packet. It emits `authorization_not_observed`; no correlated approval identity, scope, or action is synthesized.

Promotion obligations:

- define a fresh measurable operator-experience delta rather than reopening a shipped label;
- persist approval identity and scope before consequential action;
- prove the view projects owner truth without becoming a second authority.

Forbidden claim: a visible button, terminal render, or local approval fixture is not operator authorization.

Operator page: `/dashboard/organism/operator_experience`.

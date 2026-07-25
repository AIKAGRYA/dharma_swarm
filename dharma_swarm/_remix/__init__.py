"""Experimental, non-canonical "remix" artifacts.

Nothing in this package is imported by production code. Each module here is a
principled re-architecture of an existing large module, kept side-by-side with
its original (which stays untouched) so the operator can judge the pattern
before any of it is adopted. See the per-module scorecard files for the design
rationale and the validation evidence.

Status: experiment (per docs/AGENTS.md document-role taxonomy). Zero blast
radius by construction — production never imports `dharma_swarm._remix`.
"""

"""Uninterpreted-function axioms for cryptographic primitives.

We do NOT reason about the internal structure of HMAC, SHA-256, or
Ed25519. Instead, each primitive enters the SMT model as an uninterpreted
function with axiomatic collision-resistance and unforgeability, per
[Rogaway & Shrimpton 2004](https://eprint.iacr.org/2004/035).

This module is imported by future contract-checking passes. Purity
verification does not need these axioms.
"""
from __future__ import annotations

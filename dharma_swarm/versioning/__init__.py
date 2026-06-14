"""Daemon versioning: read-only version identity + recommend-only promotion gate.

This package never mutates the evolution archive, never switches the running
daemon, and never opens a new authority surface. It only learns to read the
existing truth stores per-version and say PROMOTE / HOLD / REJECT.
"""

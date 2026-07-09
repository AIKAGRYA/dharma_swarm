"""Thin front-door package for the Dharma holon system.

This package intentionally re-exports existing canonical organs instead of
creating new runtime primitives. Sarathi is an occupant under
``holon_system.sarathi``; the substrate remains in the existing modules until an
organ-by-organ migration is warranted.
"""

__all__ = [
    "identity", "runtime", "kernel", "authority", "orchestration",
    "transport", "responders", "gateway", "observability", "cli", "api",
    "sarathi",
]

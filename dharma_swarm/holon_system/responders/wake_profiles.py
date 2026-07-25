"""Facade over the existing governed wake-loop profiles."""

from scripts.runtime.codex_composer_wake_loop import WAKE_PROFILES, WakeProfile, resolve_profile

__all__ = ["WAKE_PROFILES", "WakeProfile", "resolve_profile"]

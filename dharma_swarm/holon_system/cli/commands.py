"""Holon-system CLI command inventory; command wiring remains in dgc."""


def command_names() -> tuple[str, ...]:
    return ("holon-system status", "sarathi brief", "sarathi pulse")


__all__ = ["command_names"]

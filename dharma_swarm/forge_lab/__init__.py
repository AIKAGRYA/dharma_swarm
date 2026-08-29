"""Forge Lab primitives.

This package holds the explicit contracts for the Forge Lab v0.1 target.
It remains fail-closed: live campaign mutation is not implemented in Packet A.
"""

from dharma_swarm.forge_lab.version import PACKAGE_VERSION

__all__ = ["__version__"]

__version__ = PACKAGE_VERSION

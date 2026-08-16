"""One public product root for the repo-owned Sarathi persistent-agent seat.

Importing this package is inert: it starts no provider, process, socket, loop,
or state store. Call :func:`handle_turn` or construct :class:`SarathiShell`.
"""

from .contracts import (
    CognitionPort,
    CognitionRequest,
    CognitionResult,
    EffectIntent,
    EffectReport,
    EffectStatus,
    SarathiTurnRequest,
    SarathiTurnResult,
    TurnStatus,
    TurnStorePort,
)
from .identity import DEFAULT_SARATHI_IDENTITY, SarathiIdentity
from .shell import SarathiShell, build_sarathi_shell, handle_turn

__all__ = [
    "CognitionPort",
    "CognitionRequest",
    "CognitionResult",
    "DEFAULT_SARATHI_IDENTITY",
    "EffectIntent",
    "EffectReport",
    "EffectStatus",
    "SarathiIdentity",
    "SarathiShell",
    "SarathiTurnRequest",
    "SarathiTurnResult",
    "TurnStatus",
    "TurnStorePort",
    "build_sarathi_shell",
    "handle_turn",
]

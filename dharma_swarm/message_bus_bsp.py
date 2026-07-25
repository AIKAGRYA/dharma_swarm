"""BSP staged-send helpers for :mod:`dharma_swarm.message_bus`.

Kept outside ``message_bus.py`` so the core transport stays under the module
line-budget gate while exposing the same ``MessageBus.send_staged`` method.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from dharma_swarm.message_bus import _stable_operation_hash
from dharma_swarm.spine.adapters import identity_metadata
from dharma_swarm.spine.identity import ExecutionIdentity

if TYPE_CHECKING:
    from dharma_swarm.message_bus import MessageBus
    from dharma_swarm.models import Message


async def send_staged_impl(
    bus: "MessageBus",
    message: "Message",
    *,
    deliver_at_superstep: int = 0,
    execution_identity: ExecutionIdentity | None = None,
    require_identity: bool | None = None,
) -> str:
    """Insert a message that becomes visible at ``deliver_at_superstep``."""
    effective_require = bus._require_identity if require_identity is None else require_identity
    identity = bus._resolve_message_identity(
        message,
        require_identity=effective_require,
        execution_identity=execution_identity,
    )
    side_effect_key = ""

    async def _send_staged() -> str:
        async with bus._connect() as db:
            await db.execute(
                "INSERT INTO messages "
                "(id, from_agent, to_agent, subject, body, priority, status, "
                "created_at, reply_to, metadata, superstep_visible)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    message.id,
                    message.from_agent,
                    message.to_agent,
                    message.subject,
                    message.body,
                    message.priority.value,
                    message.status.value,
                    message.created_at.isoformat(),
                    message.reply_to,
                    json.dumps(message.metadata),
                    deliver_at_superstep,
                ),
            )
            await db.commit()
        return message.id

    if identity is not None:
        metadata = {
            **dict(message.metadata or {}),
            **identity_metadata(identity, surface="message_bus"),
        }
        message = message.model_copy(update={"metadata": metadata})
        if bus._runtime_state is not None:
            side_effect_key = f"message_bus.send_staged:{identity.idempotency_key}"
            should_execute = await bus._runtime_state.try_begin_idempotent_side_effect(
                identity,
                side_effect_key,
                metadata={
                    "message_id": message.id,
                    "to_agent": message.to_agent,
                    "deliver_at_superstep": deliver_at_superstep,
                    "operation_hash": _stable_operation_hash(
                        {
                            "from_agent": message.from_agent,
                            "to_agent": message.to_agent,
                            "subject": message.subject,
                            "body": message.body,
                            "priority": message.priority.value,
                            "reply_to": message.reply_to,
                            "deliver_at_superstep": deliver_at_superstep,
                        }
                    ),
                },
            )
            if not should_execute:
                # An unfinished prior attempt must be resumed, never reported
                # as delivered with a fabricated receipt.
                return await bus._resume_unfinished_send(
                    identity, side_effect_key, message, _send_staged
                )
            await bus._runtime_state.record_execution_identity(
                identity,
                source="message_bus.send_staged",
                metadata={"surface": "message_bus"},
            )

    message_id = await bus._run_with_lock_retry(_send_staged)
    if identity is not None and bus._runtime_state is not None:
        await bus._runtime_state.complete_idempotent_side_effect(
            identity,
            side_effect_key,
            result_receipt_id=message_id,
            metadata={
                "message_id": message_id,
                "deliver_at_superstep": deliver_at_superstep,
            },
        )
    return message_id

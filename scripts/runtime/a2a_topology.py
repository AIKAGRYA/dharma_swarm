#!/usr/bin/env python3
"""Shared A2A topology constants: stream names, subject patterns, and defaults.

This module is the single source of truth for the crash-safe A2A delivery
topology.  It keeps the *live compatibility* stream (``DHARMA_A2A``) explicitly
distinct from the *target* streams (``DS_TASKS`` / ``DS_DLQ``) so that runtime
scripts cannot accidentally conflate the backward-compatible bus with the
forward-looking task/dlq streams.

All three delivery scripts — ``a2a_inbox_bridge``, ``a2a_reply_capture``, and
``a2a_domain_reply_worker`` — import their default ``--stream`` value from here
instead of hard-coding ``DHARMA_FLEET`` (which was a legacy fleet-bus name that
predates the dedicated A2A stream).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Stream names
# ---------------------------------------------------------------------------

#: Legacy / live compatibility stream that existing fleet consumers still read.
#: Kept as the *default* so that deployed bridges continue to drain the same
#: durable they always have until an operator explicitly opts into the target
#: streams.
LIVE_COMPATIBILITY_STREAM = "DHARMA_A2A"

#: Target task stream — the forward-looking stream A2A envelopes *should* land
#: on once the fleet is fully migrated.
TARGET_TASK_STREAM = "DS_TASKS"

#: Target dead-letter stream for messages that exhaust delivery attempts.
TARGET_DLQ_STREAM = "DS_DLQ"

# ---------------------------------------------------------------------------
# Default stream selection
# ---------------------------------------------------------------------------

#: The stream the delivery scripts use when the operator does not pass
#: ``--stream``.  This is the *compatibility* stream, **not** the target task
#: stream, so live behaviour is unchanged until an explicit migration.
DEFAULT_COMPATIBILITY_STREAM = LIVE_COMPATIBILITY_STREAM

#: Convenience alias for the default DLQ stream used by inbox_bridge when the
#: operator does not override it.
DEFAULT_DLQ_STREAM = TARGET_DLQ_STREAM

# ---------------------------------------------------------------------------
# Subject patterns
# ---------------------------------------------------------------------------

#: Prefix for agent inbox subjects: ``dharma.agent.<uid>.inbox``
INBOX_SUBJECT_PREFIX = "dharma.agent."

#: Suffix for agent inbox subjects.
INBOX_SUBJECT_SUFFIX = ".inbox"

#: Compatibility A2A subject prefix: ``dharma.a2a.<recipient>``
COMPATIBILITY_SUBJECT_PREFIX = "dharma.a2a."

#: DLQ subject template: ``dharma.dlq.<stream>.<consumer>``
DLQ_SUBJECT_TEMPLATE = "dharma.dlq.{stream}.{consumer}"

#: Reply subject prefix used by send receipts: ``dharma.a2a.reply.<packet_id>``
REPLY_SUBJECT_PREFIX = "dharma.a2a.reply."

# ---------------------------------------------------------------------------
# Durable consumer naming
# ---------------------------------------------------------------------------

#: Prefix for inbox bridge durable consumers.
INBOX_CONSUMER_PREFIX = "inbox_bridge_"

#: Prefix for reply-capture durable consumers (hash suffix follows).
REPLY_CONSUMER_PREFIX = "reply_capture_"

# ---------------------------------------------------------------------------
# Compatibility → target mapping
# ---------------------------------------------------------------------------

#: Maps a live compatibility stream to its target task stream.  Operators or
#: migration tooling can consult this to know where envelopes on the legacy
#: stream *should* be republished.
COMPATIBILITY_TO_TARGET: dict[str, str] = {
    LIVE_COMPATIBILITY_STREAM: TARGET_TASK_STREAM,
}

#: Maps a task stream to its companion DLQ stream.
TASK_TO_DLQ: dict[str, str] = {
    TARGET_TASK_STREAM: TARGET_DLQ_STREAM,
}
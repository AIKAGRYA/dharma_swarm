"""Transport organ — A2A NATS transport.

NO importable repo library facade yet: the live transport owners are runtime
scripts, not a package. Canonical owners:
  scripts/runtime/a2a_send.py
  scripts/runtime/a2a_inbox_bridge.py
  scripts/runtime/a2a_domain_reply_worker.py
  scripts/runtime/a2a_reply_capture.py
  dharma_swarm/a2a/  (contact_registry, a2a_client, nats_transport, ...)

Status: SCATTERED (runtime scripts + dharma_swarm/a2a). Promote to a package
facade only when a real import surface is agreed; do not fabricate one here.
"""

from __future__ import annotations

__all__: list[str] = []

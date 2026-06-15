"""BoardStore adapters — bridge existing stores behind the facade."""

from dharma_swarm.board.adapters.a2a_send_adapter import (
    A2ASendBoardAdapter,
    a2a_domain_reply_receipt_to_card,
    a2a_inbox_bridge_receipt_to_card,
    a2a_reply_capture_receipt_to_card,
    a2a_send_receipt_to_card,
    load_a2a_send_cards,
)
from dharma_swarm.board.adapters.agentops_adapter import (
    AgentOpsBoardAdapter,
    load_agentops_cards,
    work_packet_to_card,
)
from dharma_swarm.board.adapters.ds_goal_adapter import (
    DsGoalBoardAdapter,
    ds_goal_task_to_card,
    load_ds_goal_cards,
    mission_cards,
)
from dharma_swarm.board.adapters.semantic_receipt_adapter import (
    SemanticReceiptBoardAdapter,
    load_semantic_receipt_cards,
    semantic_receipt_to_card,
)

__all__ = [
    "A2ASendBoardAdapter",
    "AgentOpsBoardAdapter",
    "DsGoalBoardAdapter",
    "SemanticReceiptBoardAdapter",
    "a2a_domain_reply_receipt_to_card",
    "a2a_inbox_bridge_receipt_to_card",
    "a2a_reply_capture_receipt_to_card",
    "a2a_send_receipt_to_card",
    "ds_goal_task_to_card",
    "load_a2a_send_cards",
    "load_agentops_cards",
    "load_ds_goal_cards",
    "load_semantic_receipt_cards",
    "mission_cards",
    "semantic_receipt_to_card",
    "work_packet_to_card",
]

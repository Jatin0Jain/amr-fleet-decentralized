"""
message_broker.py — Message Type Definitions & Routing
[P2P PERSON] — Typed message helpers so everyone uses the same format.
"""

import json
import time


# ---------------------------------------------------------------------------
# Message type constants
# ---------------------------------------------------------------------------
MSG_STATE = "state"           # robot broadcasting its position/status
MSG_CONFLICT = "conflict"     # "I'm about to enter cell X,Y — who has priority?"
MSG_HANDOFF = "handoff"       # "I can't finish task T — can someone else take it?"
MSG_PRIORITY = "priority"     # "I claim priority at this intersection"
MSG_ACK = "ack"               # acknowledgement


def make_state_msg(robot_state_json: str) -> str:
    """Wrap a robot state dict in the standard message envelope."""
    inner = json.loads(robot_state_json)
    return json.dumps({"type": MSG_STATE, "payload": inner, "ts": time.time()})


def make_conflict_msg(robot_id: str, cell_x: int, cell_y: int) -> str:
    """Alert peers that robot_id wants to enter cell (x,y) and needs priority check."""
    return json.dumps({
        "type": MSG_CONFLICT,
        "payload": {"robot_id": robot_id, "cell": [cell_x, cell_y]},
        "ts": time.time(),
    })


def make_handoff_msg(robot_id: str, task: dict) -> str:
    """Signal that robot_id cannot complete its task and needs someone to take over."""
    return json.dumps({
        "type": MSG_HANDOFF,
        "payload": {"from_robot": robot_id, "task": task},
        "ts": time.time(),
    })


def make_priority_msg(robot_id: str, cell: tuple, priority_score: float) -> str:
    """Claim priority at an intersection based on battery/urgency score."""
    return json.dumps({
        "type": MSG_PRIORITY,
        "payload": {
            "robot_id": robot_id,
            "cell": list(cell),
            "score": priority_score,
        },
        "ts": time.time(),
    })


def parse_message(raw: str) -> tuple[str, dict]:
    """
    Parse an incoming raw WebSocket message.

    Returns:
        (msg_type, payload_dict)

    Usage:
        msg_type, payload = parse_message(raw)
        if msg_type == MSG_STATE:
            update_peer_state(payload)
        elif msg_type == MSG_CONFLICT:
            handle_conflict_alert(payload)
    """
    data = json.loads(raw)
    return data.get("type", "unknown"), data.get("payload", {})

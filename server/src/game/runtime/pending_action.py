from typing import Any

from src.game.domain.action import Action


def build_pending_action_payload(action: Action) -> dict[str, Any]:
    return {
        "kind": "graph_action",
        "action": action.model_dump(mode="json", by_alias=True),
    }


def load_pending_action(
    pending: dict[str, Any],
    *,
    error_type: type[Exception] = ValueError,
) -> Action:
    payload = pending.get("payload")
    if not isinstance(payload, dict) or payload.get("kind") != "graph_action":
        raise error_type("pending graph action missing")
    action_data = payload.get("action")
    if not isinstance(action_data, dict):
        raise error_type("pending action missing")
    return Action.model_validate(action_data)

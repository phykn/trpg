from .apply import (
    GraphRuntimeApplyError,
    GraphRuntimeApplyResult,
    apply_runtime_graph_changes,
)
from .combat import (
    GraphCombatDispatchError,
    GraphCombatDispatchResult,
    dispatch_graph_combat_action,
)
from src.game.domain.content import RuntimeContent
from .load import load_runtime_state
from .state import GameRuntimeState

__all__ = [
    "GameRuntimeState",
    "GraphActionDispatchError",
    "GraphActionDispatchResult",
    "GraphCombatDispatchError",
    "GraphCombatDispatchResult",
    "GraphRuntimeApplyError",
    "GraphRuntimeApplyResult",
    "RuntimeContent",
    "apply_runtime_graph_changes",
    "dispatch_graph_action",
    "dispatch_graph_combat_action",
    "load_runtime_state",
]


def __getattr__(name: str):
    if name in {
        "GraphActionDispatchError",
        "GraphActionDispatchResult",
        "dispatch_graph_action",
    }:
        from . import dispatch

        return getattr(dispatch, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

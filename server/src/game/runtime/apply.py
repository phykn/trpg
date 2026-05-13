from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from src.db.repo import GraphRepo
from src.game.domain.graph import (
    AddEdgeChange,
    AddNodeChange,
    GraphChange,
    GraphInvariantError,
    RemoveEdgeChange,
    SetEdgePropertyChange,
    SetNodePropertyChange,
    apply_graph_changes,
    parse_graph_change,
)

from .state import GameRuntimeState


class GraphRuntimeApplyError(ValueError):
    pass


class GraphRuntimeApplyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    applied: int
    changed_node_ids: list[str]
    changed_edge_ids: list[str]
    removed_edge_ids: list[str]


class GraphRuntimeDirty:
    def __init__(
        self,
        *,
        changed_node_ids: set[str] | None = None,
        changed_edge_ids: set[str] | None = None,
        removed_edge_ids: set[str] | None = None,
    ) -> None:
        self.changed_node_ids = changed_node_ids or set()
        self.changed_edge_ids = changed_edge_ids or set()
        self.removed_edge_ids = removed_edge_ids or set()

    @classmethod
    def from_apply_result(
        cls,
        result: GraphRuntimeApplyResult,
    ) -> "GraphRuntimeDirty":
        dirty = cls()
        dirty.add_apply_result(result)
        return dirty

    def add_apply_result(self, result: GraphRuntimeApplyResult) -> None:
        self.changed_node_ids.update(result.changed_node_ids)
        self.changed_edge_ids.update(result.changed_edge_ids)
        self.removed_edge_ids.update(result.removed_edge_ids)

    async def save(self, repo: GraphRepo, game_id: str, graph) -> None:
        await repo.save_graph_changes(
            game_id,
            graph,
            changed_node_ids=sorted(self.changed_node_ids),
            changed_edge_ids=sorted(self.changed_edge_ids),
            removed_edge_ids=sorted(self.removed_edge_ids),
        )


def apply_runtime_graph_changes(
    runtime: GameRuntimeState,
    changes: list[GraphChange | dict[str, Any]],
) -> GraphRuntimeApplyResult:
    parsed = [_parse_change(change) for change in changes]
    graph = runtime.graph
    changed_node_ids: set[str] = set()
    changed_edge_ids: set[str] = set()
    removed_edge_ids: set[str] = set()

    for change in parsed:
        _track_changed_ids(
            change,
            changed_node_ids,
            changed_edge_ids,
            removed_edge_ids,
        )
    try:
        graph = apply_graph_changes(graph, parsed)
    except GraphInvariantError as exc:
        raise GraphRuntimeApplyError(str(exc)) from exc

    next_runtime = GameRuntimeState(
        graph=graph,
        progress=runtime.progress,
        content=runtime.content,
        log_entries=list(runtime.log_entries),
        turn_log=list(runtime.turn_log),
        recent_dialogue=list(runtime.recent_dialogue),
    )
    return GraphRuntimeApplyResult(
        runtime=next_runtime,
        applied=len(parsed),
        changed_node_ids=sorted(changed_node_ids),
        changed_edge_ids=sorted(changed_edge_ids),
        removed_edge_ids=sorted(removed_edge_ids),
    )


def _parse_change(change: GraphChange | dict[str, Any]) -> GraphChange:
    if isinstance(change, dict):
        try:
            return parse_graph_change(change)
        except ValidationError as exc:
            raise GraphRuntimeApplyError(_format_validation_error(exc)) from exc
    return change


def _track_changed_ids(
    change: GraphChange,
    changed_node_ids: set[str],
    changed_edge_ids: set[str],
    removed_edge_ids: set[str],
) -> None:
    if isinstance(change, AddNodeChange):
        changed_node_ids.add(change.node.id)
    elif isinstance(change, SetNodePropertyChange):
        changed_node_ids.add(change.node_id)
    elif isinstance(change, AddEdgeChange):
        changed_edge_ids.add(change.edge.id)
    elif isinstance(change, SetEdgePropertyChange):
        changed_edge_ids.add(change.edge_id)
    elif isinstance(change, RemoveEdgeChange):
        removed_edge_ids.add(change.edge_id)


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"]) or "<root>"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)

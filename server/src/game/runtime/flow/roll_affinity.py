from src.game.domain.content import node_label
from src.game.domain.graph import Graph
from src.game.domain.graph import AddEdgeChange, GraphChange, SetEdgePropertyChange
from src.game.domain.memory import NarrationCue
from src.locale.render import render

from ..state import GameRuntimeState


def affinity_change_cues(
    runtime: GameRuntimeState,
    changes: list[GraphChange],
) -> list[NarrationCue]:
    cues: list[NarrationCue] = []
    player_id = runtime.progress.player_id
    for change in changes:
        delta = _affinity_delta(runtime.graph, change)
        if delta == 0:
            continue
        npc_id = _relation_npc_id(runtime.graph, change, player_id)
        if npc_id is None:
            continue
        npc = runtime.graph.nodes.get(npc_id)
        if npc is None:
            continue
        cues.append(
            NarrationCue(
                kind="change",
                label=render("runtime.roll.affinity_label", runtime.progress.locale),
                text=_affinity_cue_text(
                    node_label(runtime.content, npc),
                    delta,
                    runtime.progress.locale,
                ),
                scope="delta",
            )
        )
    return cues


def _affinity_delta(graph: Graph, change: GraphChange) -> int:
    if isinstance(change, AddEdgeChange):
        if change.edge.type != "relation":
            return 0
        affinity = change.edge.properties.get("affinity")
        return affinity if isinstance(affinity, int) else 0
    if isinstance(change, SetEdgePropertyChange):
        if change.path != "affinity":
            return 0
        edge = graph.edges.get(change.edge_id)
        if edge is None or edge.type != "relation":
            return 0
        current = edge.properties.get("affinity")
        old_value = current if isinstance(current, int) else 0
        new_value = change.value if isinstance(change.value, int) else old_value
        return new_value - old_value
    return 0


def _relation_npc_id(
    graph: Graph,
    change: GraphChange,
    player_id: str,
) -> str | None:
    if isinstance(change, AddEdgeChange):
        edge = change.edge
    elif isinstance(change, SetEdgePropertyChange):
        edge = graph.edges.get(change.edge_id)
    else:
        return None
    if edge is None or edge.type != "relation":
        return None
    if edge.from_node_id == player_id:
        return edge.to_node_id
    if edge.to_node_id == player_id:
        return edge.from_node_id
    return None


def _affinity_cue_text(npc_name: str, delta: int, locale: str) -> str:
    if delta >= 10:
        key = "runtime.roll.affinity_strong_positive"
    elif delta > 0:
        key = "runtime.roll.affinity_positive"
    elif delta <= -10:
        key = "runtime.roll.affinity_strong_negative"
    else:
        key = "runtime.roll.affinity_negative"
    return render(key, locale, npc=npc_name)

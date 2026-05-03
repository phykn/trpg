"""Server-side template chips for the SSE `suggestions` event.

Replaces the LLM-derived suggestions (from narrate/extract) with a deterministic
builder that reads the player's surroundings (NPCs / connections / inventory)
and emits at most 3 chips, one per category, no padding.
"""

from ..domain.state import GameState
from ..ontology.queries import connections_of, inhabitants_of, inventory_of
from .josa import eu_ro, eul_reul

# Fixed detour chips shown after a free-path judge rejection to break dead-ends.
# Rotated so that repeated rejections surface different paths.
_DETOUR_CHIPS = [
    "다른 방법으로 설득한다",
    "증거나 아이템을 제시한다",
    "위협하거나 협상을 시도한다",
]


def _has_recent_judge_rejection(state: GameState) -> bool:
    """True if a judge_rejected event appears in the last 3 engine events."""
    recent = state.recent_engine_events[-3:]
    return any(e.get("type") == "judge_rejected" for e in recent)


def _detour_chip(state: GameState) -> str:
    """Pick one detour chip based on how many rejections have accumulated."""
    count = sum(
        1 for e in state.recent_engine_events if e.get("type") == "judge_rejected"
    )
    return _DETOUR_CHIPS[(count - 1) % len(_DETOUR_CHIPS)]


def build_suggestion_chips(state: GameState) -> list[str]:
    """Server-side template chips: NPC / adjacent location / inventory.
    One per category, max 3. No padding — empty surroundings yield [].

    After a free-path judge rejection the first chip is replaced by a detour
    suggestion to prevent charisma-fail dead-ends.
    """
    if state.combat_state is not None:
        return []
    if state.previous_phase_signal == "downed_recovered":
        return []
    graph = state.graph()
    player = state.characters.get(state.player_id)
    if player is None:
        return []
    loc_id = player.location_id
    chips: list[str] = []

    dead_end = _has_recent_judge_rejection(state)

    if dead_end:
        chips.append(_detour_chip(state))
    elif loc_id is not None and loc_id in state.locations:
        for cid in inhabitants_of(graph, loc_id):
            if cid == state.player_id:
                continue
            char = state.characters.get(cid)
            if char is not None and char.alive:
                chips.append(f"{char.name}에게 말을 건다")
                break

    if loc_id is not None and loc_id in state.locations:
        for edge in connections_of(graph, loc_id):
            adj = state.locations.get(edge.to_id)
            if adj is not None:
                chips.append(f"{adj.name}{eu_ro(adj.name)} 이동한다")
                break

    for item_id in inventory_of(graph, state.player_id):
        item = state.items.get(item_id)
        if item is not None:
            chips.append(f"{item.name}{eul_reul(item.name)} 살펴본다")
            break

    return chips

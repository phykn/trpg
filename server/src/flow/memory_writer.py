from ..domain.memory import Memory
from ..llm.calls.narrate import NarrateOutput
from ..rules import RULES
from ..domain.state import GameState


def write_memories(
    state: GameState,
    output: NarrateOutput,
    turn: int,
    dirty: set[tuple[str, str]] | None = None,
) -> int:
    """When memorable=true, append one line to each entity's memories[].

    On cap overflow, evict the lowest-importance entry; ties broken by lowest turn.
    If `dirty` is given, add any character whose memories actually changed.
    Returns: number of memories actually added (after cap eviction).
    """
    if not output.memorable or not output.memory or not output.memory_targets:
        return 0

    cap = RULES.memory.cap
    importance = output.importance or 1
    written = 0

    for entity_id in output.memory_targets:
        if entity_id not in state.characters:
            continue
        memories = state.characters[entity_id].memories
        content = output.memory.get(entity_id)
        if not content:
            continue
        memories.append(
            Memory(
                content=content,
                importance=importance,
                turn=turn,
                target_id=output.memory_links.get(entity_id),
            )
        )
        while len(memories) > cap:
            evict_idx = min(
                range(len(memories)),
                key=lambda i: (memories[i].importance, memories[i].turn),
            )
            memories.pop(evict_idx)
        if dirty is not None:
            dirty.add(("characters", entity_id))
        written += 1
    return written

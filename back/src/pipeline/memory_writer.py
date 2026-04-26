from ..domain.memory import Memory
from ..llm_client.agents.narrate import NarrateOutput
from ..rules import RULES
from ..state.models import GameState


def write_memories(state: GameState, output: NarrateOutput, turn: int) -> int:
    """memorable=true 일 때 각 entity 의 memories[] 에 한 줄 append.

    cap 도달 시 importance 낮은 항목 → 같으면 turn 작은 항목부터 evict.
    Returns: 실제 추가된 memory 수 (cap evict 후에도 살아남은 것 기준).
    """
    if not output.memorable or not output.memory or not output.memory_targets:
        return 0

    cap = RULES.memory.cap
    importance = output.importance or 1
    written = 0

    for entity_id in output.memory_targets:
        memories = _get_memories(state, entity_id)
        if memories is None:
            continue
        memories.append(Memory(
            content=output.memory,
            importance=importance,
            turn=turn,
            target_id=output.memory_links.get(entity_id),
        ))
        while len(memories) > cap:
            evict_idx = min(
                range(len(memories)),
                key=lambda i: (memories[i].importance, memories[i].turn),
            )
            memories.pop(evict_idx)
        written += 1
    return written


def _get_memories(state: GameState, entity_id: str) -> list[Memory] | None:
    if entity_id in state.characters:
        return state.characters[entity_id].memories
    return None

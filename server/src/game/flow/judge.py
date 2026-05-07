import json

from pydantic import ValidationError

from ..domain.errors import JudgeMalformed
from src.llm.calls.classify import classify
from src.llm.calls.classify.errors import ModifierValidationError
from src.llm.calls.classify.schema import JudgeInput, JudgeOutput
from src.llm.client import LLMClient
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from src.llm.context import build_surroundings


async def run_judge(
    client: LLMClient,
    state: GameState,
    player_input: str,
    *,
    graph: GameGraph | None = None,
) -> JudgeOutput:
    """Call the classify LLM and return a JudgeOutput. After self-correction
    retries inside the runner, schema/modifier failures raise JudgeMalformed —
    callers absorb (turn.py) or surface as SSE error (combat_phase.py).

    `graph` is the relational SSOT — flow entry points pass the turn-start
    graph so build_surroundings doesn't rebuild. Test/ad-hoc callers can omit.
    """
    surroundings = build_surroundings(state, state.player_id, graph)
    history = [
        {"turn": e.turn, "target": e.target, "summary": e.summary}
        for e in state.turn_log[-5:]
    ]
    recent_dialogue = [
        {"turn": d.turn, "player": d.player, "narrator": d.narrator}
        for d in state.recent_dialogue[-2:]
    ]
    try:
        return await classify(
            client,
            JudgeInput(
                player_input=player_input,
                surroundings=surroundings,
                history=history,
                recent_dialogue=recent_dialogue,
            ),
            state.locale,
        )
    except (ValidationError, ModifierValidationError, json.JSONDecodeError) as e:
        raise JudgeMalformed(str(e)) from e

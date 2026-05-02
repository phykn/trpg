from pydantic import ValidationError

from ..domain.errors import JudgeMalformed
from ..llm_calls.classify import JudgeSemanticError, classify
from ..llm_calls.classify.schema import JudgeInput, JudgeOutput, RollAction
from ..llm.client import LLMClient
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from ..context import build_surroundings


async def run_judge(
    client: LLMClient,
    state: GameState,
    player_input: str,
    *,
    graph: GameGraph | None = None,
) -> JudgeOutput:
    """Call the classify LLM. After 5 self-correction retries inside the runner:
    - schema-only failure (ValidationError) → raise JudgeMalformed.
    - semantic failure (JudgeSemanticError) → fall back to a roll on the
      player's current location (docs/02-runtime §2.3 step 3).

    `graph` is the relational SSOT — flow entry points pass the turn-start
    graph so build_surroundings doesn't rebuild. Test/ad-hoc callers can omit.
    """
    surroundings = build_surroundings(state, state.player_id, graph)
    try:
        return await classify(
            client,
            JudgeInput(player_input=player_input, surroundings=surroundings),
        )
    except ValidationError as e:
        raise JudgeMalformed(str(e)) from e
    except JudgeSemanticError as e:
        loc_id = state.characters[state.player_id].location_id
        if loc_id is None:
            raise JudgeMalformed(
                f"semantic fallback impossible: no location ({e})"
            ) from e
        return RollAction(action="roll", tier="보통", stat="WIS", targets=[loc_id])

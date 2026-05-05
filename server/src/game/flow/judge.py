from dataclasses import dataclass
from typing import Literal, TypedDict

from pydantic import ValidationError

from ..domain.errors import JudgeMalformed
from ..domain.types import StatKey, Tier
from src.llm.calls.classify import JudgeSemanticError, classify
from src.llm.calls.classify.schema import JudgeInput, JudgeOutput, Verb
from src.llm.client import LLMClient
from src.locale import render
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from src.llm.context import build_surroundings
from src.locale.labels import ROLL_REASON_DEFAULT


@dataclass(frozen=True)
class PendingCheckTrigger:
    """Signal that a pending_check should be emitted immediately, from
    semantic fallback or verb-driven uncertainty. Distinct type from
    JudgeOutput — turn.py branches on isinstance.

    Today only the semantic fallback emits this (triggering_verb=None);
    the later uncertainty rule will let verb dispatch construct the same
    trigger and call emit_roll_pending_from_trigger."""
    tier: Tier
    stat: StatKey
    targets: list[str]
    reason: str
    triggering_verb: Verb | None = None


class JudgeResult(TypedDict):
    outcome: Literal["satisfied", "partial", "rejected"]
    reason: str
    progress_delta: int | None


def _call_judge_llm(prompt: str, schema: type) -> dict:
    """LLM call wrapper — override in tests via monkeypatch."""
    # not yet wired; callers catch NotImplementedError.
    raise NotImplementedError(
        "Judge LLM integration not wired (test-only stub)."
    )


def judge_quest_progress(
    quest: dict,
    history: list[dict],
    claim: str | None,
    npc_context: dict | None,
) -> JudgeResult:
    """Free-path quest evaluation. LLM judges if player satisfied the objective.

    Args:
        quest: dict with at least id, objective_text
        history: recent engine event summaries
        claim: player's assertion if in dialogue (None for auto turn-end check)
        npc_context: {npc_id, favor} for NPC dialogue context (None for auto check)
    """
    history_text = (
        "\n".join(f"- {h.get('summary', str(h))}" for h in history)
        or render("prompt.judge.empty_history", "ko")
    )
    npc_block = (
        render(
            "prompt.judge.npc_block", "ko",
            npc_id=npc_context.get("npc_id"),
            favor=npc_context.get("favor", 0),
        )
        if npc_context
        else render("prompt.judge.no_npc", "ko")
    )
    prompt = render(
        "prompt.judge.quest_evaluator", "ko",
        objective=quest.get("objective_text", render("prompt.judge.empty_objective", "ko")),
        history=history_text,
        claim=claim or render("prompt.judge.empty_claim", "ko"),
        npc_block=npc_block,
    )
    return _call_judge_llm(prompt, schema=JudgeResult)


async def run_judge(
    client: LLMClient,
    state: GameState,
    player_input: str,
    *,
    graph: GameGraph | None = None,
) -> JudgeOutput | PendingCheckTrigger:
    """Call the classify LLM. After 5 self-correction retries inside the runner:
    - schema-only failure (ValidationError) → raise JudgeMalformed.
    - semantic failure (JudgeSemanticError) → return PendingCheckTrigger
      (WIS roll on player's current location — preserves prior behavior).

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
        )
    except ValidationError as e:
        raise JudgeMalformed(str(e)) from e
    except JudgeSemanticError as e:
        loc_id = state.characters[state.player_id].location_id
        if loc_id is None:
            raise JudgeMalformed(
                f"semantic fallback impossible: no location ({e})"
            ) from e
        return PendingCheckTrigger(
            tier="normal",
            stat="WIS",
            targets=[loc_id],
            reason=ROLL_REASON_DEFAULT,
            triggering_verb=None,
        )

import asyncio
import json

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.content import node_label
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph import GraphNode
from src.game.domain.graph_query import characters_at, location_of
from src.game.domain.memory import GMLogEntry
from src.llm.calls._runner import get_prompt
from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import ClassifyInput
from src.llm.client import LLMClient
from src.llm.context.graph_surroundings import build_graph_surroundings
from src.llm.diag import engine_diag, llm_diag, set_diag_context
from src.locale.render import render
from src.wire.graph_to_front import graph_to_front_state

from .confirmation import GraphActionRequestResult, run_graph_action_request
from .load import load_runtime_state
from .roll import start_graph_roll


class GraphInputError(ValueError):
    pass


_GRAPH_INPUT_NARRATION_TIMEOUT_SECONDS = 6.0


async def run_graph_input_turn(
    client: LLMClient,
    repo: GraphRepo,
    game_id: str,
    player_input: str,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("input:start", chars=len(player_input))
    output = await classify(
        client,
        ClassifyInput(
            player_input=player_input,
            surroundings=build_graph_surroundings(runtime),
        ),
        locale=runtime.progress.locale,
    )

    if output.refuse is not None:
        raise GraphInputError(output.refuse.message_hint)
    actions = output.actions or []
    if len(actions) != 1:
        raise GraphInputError("graph input requires exactly one action")

    action = actions[0]
    engine_diag("input:classified", action=action.verb)
    if action.verb == "perceive":
        return await start_graph_roll(
            repo, game_id, action, scenario_repo=scenario_repo
        )

    if action.verb in {"speak", "pass"}:
        return await _run_graph_narrative_input(
            client,
            repo,
            runtime,
            player_input,
            action,
        )

    return await run_graph_action_request(
        repo,
        game_id,
        action,
        llm=client,
        scenario_repo=scenario_repo,
    )


async def _run_graph_narrative_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime,
    player_input: str,
    action,
) -> GraphActionRequestResult:
    subject_id = _resolve_narrative_subject(runtime, action)
    text = await _generate_graph_input_narration(
        client,
        runtime,
        player_input,
        action,
        subject_id,
    )
    if not text:
        text = render("runtime.input.quiet", runtime.progress.locale)
    entry = GMLogEntry(
        id=runtime.progress.next_log_id,
        kind="gm",
        text=text,
    )
    progress = runtime.progress.model_copy(
        update={
            "turn_count": runtime.progress.turn_count + 1,
            "next_log_id": entry.id + 1,
            "active_subject_id": subject_id or runtime.progress.active_subject_id,
        }
    )
    next_runtime = runtime.model_copy(
        update={
            "progress": progress,
            "log_entries": [*runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(runtime.progress.game_id, [entry])
    await repo.save_progress(progress)
    engine_diag("input:done", status="executed", action=action.verb)
    return GraphActionRequestResult(
        runtime=next_runtime,
        status="executed",
        front_state=graph_to_front_state(next_runtime),
    )


async def _generate_graph_input_narration(
    client: LLMClient,
    runtime,
    player_input: str,
    action,
    subject_id: str | None,
) -> str:
    surroundings = build_graph_surroundings(runtime)
    subject = runtime.graph.nodes.get(subject_id or "")
    subject_state = (
        "same_place"
        if subject_id is not None and _is_at_player_location(runtime, subject_id)
        else None
    )
    try:
        llm_diag("llm:call", agent="graph_narrate")
        result = await asyncio.wait_for(
            client.chat(
                [
                    {
                        "role": "system",
                        "content": get_prompt("graph_narrate", runtime.progress.locale),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "player_input": player_input,
                                "classified_action": action.model_dump(
                                    mode="json",
                                    by_alias=True,
                                ),
                                "dialogue_target": {
                                    "id": subject_id,
                                    "name": _node_name(runtime, subject),
                                    "state": subject_state,
                                }
                                if subject_id is not None
                                else None,
                                "surroundings": surroundings,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                think=False,
                agent="graph_narrate",
                temperature=0.2,
            ),
            timeout=_GRAPH_INPUT_NARRATION_TIMEOUT_SECONDS,
        )
    except (LLMUnavailable, OSError, TimeoutError) as exc:
        llm_diag("llm:fail", agent="graph_narrate", err=type(exc).__name__)
        return ""
    llm_diag("llm:done", agent="graph_narrate")
    answer = result.get("answer")
    if not isinstance(answer, str):
        return ""
    return _clean_narration(answer)


def _resolve_narrative_subject(runtime, action) -> str | None:
    target_id = _single(action.what) or _single(action.to)
    if isinstance(target_id, str) and _is_at_player_location(runtime, target_id):
        return target_id
    if action.verb != "speak":
        return None
    location_id = location_of(runtime.graph, runtime.progress.player_id)
    if location_id is None:
        return None
    for character_id in characters_at(runtime.graph, location_id):
        if character_id == runtime.progress.player_id:
            continue
        node = runtime.graph.nodes.get(character_id)
        if node is None or node.type != "character":
            continue
        if _node_hp(node) > 0:
            return character_id
    return None


def _is_at_player_location(runtime, node_id: str) -> bool:
    player_location = location_of(runtime.graph, runtime.progress.player_id)
    return (
        player_location is not None
        and location_of(runtime.graph, node_id) == player_location
    )


def _node_name(runtime, node: GraphNode | None) -> str:
    if node is None:
        return render("runtime.none", runtime.progress.locale)
    return node_label(runtime.content, node)


def _node_hp(node: GraphNode) -> int:
    hp = node.properties.get("hp")
    return hp if isinstance(hp, int) else 0


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None


def _clean_narration(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= 220:
        return cleaned
    return cleaned[:220].rstrip()

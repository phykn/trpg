from __future__ import annotations

import random
import secrets
from collections.abc import AsyncIterator
from typing import Literal

from src.db.repo import SaveRepo, ScenarioRepo
from src.game.domain.entities import ConsumableEffect
from src.game.domain.errors import PendingConfirmationExpected
from src.game.domain.state import GameState
from src.game.domain.verb import Verb
from src.llm.client import LLMClient
from src.wire.emit import emit_confirmation_required

from .dirty import Dirty, ToFrontFn, finalize, flush_deferred_act_cards, persist_on_exit


Decision = Literal["confirm", "cancel"]


def build_quest_confirmation(
    state: GameState,
    *,
    action: Literal["accept", "abandon"],
    quest_id: str,
) -> dict[str, object]:
    quest = state.quests[quest_id]
    if action == "accept":
        kind = "quest_accept"
        title = "퀘스트를 시작하시겠습니까?"
        body = f"{quest.title} 퀘스트를 시작합니다."
        confirm_label = "시작"
    else:
        kind = "quest_abandon"
        title = "퀘스트를 포기하시겠습니까?"
        body = f"{quest.title} 퀘스트를 포기합니다."
        confirm_label = "포기"
    return {
        "id": f"confirm_{secrets.token_hex(4)}",
        "kind": kind,
        "title": title,
        "body": body,
        "confirm_label": confirm_label,
        "cancel_label": "취소",
        "target_label": quest.title,
        "payload": {
            "kind": "quest_action",
            "action": action,
            "quest_id": quest_id,
        },
    }


def build_verb_confirmation(
    state: GameState,
    *,
    verb: Verb,
    player_input: str,
) -> dict[str, object] | None:
    if verb.name == "attack" and state.combat_state is None:
        if _has_invalid_attack_target(state, list(verb.target_ids)):
            return None
        target_label = _target_label(state, list(verb.target_ids))
        return {
            "id": f"confirm_{secrets.token_hex(4)}",
            "kind": "attack_start",
            "title": "공격하시겠습니까?",
            "body": f"{target_label} 공격해 전투를 시작합니다.",
            "confirm_label": "공격",
            "cancel_label": "취소",
            "target_label": target_label,
            "payload": {
                "kind": "verb",
                "verb": verb.model_dump(mode="json"),
                "player_input": player_input,
            },
        }

    modifiers = verb.modifiers or {}
    if verb.name == "transfer" and modifiers.get("mode") == "steal":
        target_id = modifiers.get("from_id")
        target_label = (
            state.characters[target_id].name
            if isinstance(target_id, str) and target_id in state.characters
            else str(target_id or "")
        )
        return {
            "id": f"confirm_{secrets.token_hex(4)}",
            "kind": "steal",
            "title": "훔치시겠습니까?",
            "body": f"{target_label}에게서 몰래 훔치려 합니다.",
            "confirm_label": "시도",
            "cancel_label": "취소",
            "target_label": target_label,
            "payload": {
                "kind": "verb",
                "verb": verb.model_dump(mode="json"),
                "player_input": player_input,
            },
        }

    if verb.name == "rest":
        player = state.characters[state.player_id]
        location = state.locations.get(player.location_id or "")
        if location is not None and location.sleep_risk != "safe":
            return {
                "id": f"confirm_{secrets.token_hex(4)}",
                "kind": "dangerous_rest",
                "title": "위험한 곳에서 쉬시겠습니까?",
                "body": "쉬는 동안 습격을 받을 수 있습니다.",
                "confirm_label": "쉬기",
                "cancel_label": "취소",
                "target_label": location.name,
                "payload": {
                    "kind": "verb",
                    "verb": verb.model_dump(mode="json"),
                    "player_input": player_input,
                },
            }

    if verb.name == "use" and state.combat_state is None:
        pending = _build_dangerous_use_confirmation(state, verb, player_input)
        if pending is not None:
            return pending

    return None


def _build_dangerous_use_confirmation(
    state: GameState,
    verb: Verb,
    player_input: str,
) -> dict[str, object] | None:
    modifiers = verb.modifiers or {}
    item_id = modifiers.get("item_id")
    if not isinstance(item_id, str):
        return None
    player = state.characters[state.player_id]
    if item_id not in player.inventory_ids:
        return None
    item = state.items.get(item_id)
    if item is None:
        return None
    effect = item.effects
    if not isinstance(effect, ConsumableEffect) or effect.effect != "damage":
        return None
    target_id = modifiers.get("target_id")
    if not isinstance(target_id, str) or target_id not in state.characters:
        return None
    target_label = state.characters[target_id].name
    return {
        "id": f"confirm_{secrets.token_hex(4)}",
        "kind": "dangerous_use",
        "title": "위험한 아이템을 사용하시겠습니까?",
        "body": f"{target_label}에게 {item.name}을 사용합니다.",
        "confirm_label": "사용",
        "cancel_label": "취소",
        "target_label": target_label,
        "payload": {
            "kind": "verb",
            "verb": verb.model_dump(mode="json"),
            "player_input": player_input,
        },
    }


def _has_invalid_attack_target(state: GameState, target_ids: list[str]) -> bool:
    actor = state.characters[state.player_id]
    actor_loc = actor.location_id
    return any(
        target_id == state.player_id
        or target_id not in state.characters
        or not state.characters[target_id].alive
        or state.characters[target_id].location_id != actor_loc
        for target_id in target_ids
    )


def _target_label(state: GameState, target_ids: list[str]) -> str:
    names = [
        state.characters[target_id].name
        for target_id in target_ids
        if target_id in state.characters
    ]
    if not names:
        return "대상"
    if len(names) == 1:
        return names[0]
    return f"{names[0]} 외 {len(names) - 1}명"


async def prompt_confirmation_and_finalize(
    state: GameState,
    save_repo: SaveRepo,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    pending: dict[str, object],
) -> AsyncIterator[dict]:
    state.pending_confirmation = pending
    yield emit_confirmation_required(pending)
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev


async def run_confirm(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    confirmation_id: str,
    decision: Decision,
    *,
    to_front_fn: ToFrontFn | None = None,
    rng: random.Random | None = None,
) -> AsyncIterator[dict]:
    dirty = Dirty()
    inner = _run_confirm_inner(
        client,
        state,
        scenario_repo,
        save_repo,
        confirmation_id,
        decision,
        dirty,
        to_front_fn,
        rng,
    )
    async for ev in persist_on_exit(state, save_repo, dirty, to_front_fn, inner):
        yield ev


async def _run_confirm_inner(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    confirmation_id: str,
    decision: Decision,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    rng: random.Random | None,
) -> AsyncIterator[dict]:
    pending = state.pending_confirmation
    if pending is None:
        raise PendingConfirmationExpected("no pending_confirmation")
    if pending.get("id") != confirmation_id:
        raise PendingConfirmationExpected("confirmation id mismatch")

    state.pending_confirmation = None
    if decision == "cancel":
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    payload = pending.get("payload")
    if not isinstance(payload, dict):
        raise PendingConfirmationExpected("pending confirmation payload missing")

    if payload.get("kind") == "quest_action":
        from src.game.engines.quest import abandon_quest, accept_quest

        action = payload.get("action")
        quest_id = payload.get("quest_id")
        if not isinstance(quest_id, str):
            raise PendingConfirmationExpected("quest id missing")
        if action == "accept":
            accept_quest(state, quest_id, dirty)
        elif action == "abandon":
            abandon_quest(state, quest_id, dirty)
        else:
            raise PendingConfirmationExpected("unknown quest action")
        for ev in flush_deferred_act_cards(state, dirty):
            yield ev
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    if payload.get("kind") == "verb":
        from .dispatch import _dispatch_verb

        verb_data = payload.get("verb")
        if not isinstance(verb_data, dict):
            raise PendingConfirmationExpected("pending verb missing")
        player_input = payload.get("player_input")
        verb = Verb.model_validate(verb_data)
        graph = state.graph()
        async for ev in _dispatch_verb(
            verb,
            client=client,
            state=state,
            scenario_repo=scenario_repo,
            save_repo=save_repo,
            dirty=dirty,
            rng=rng,
            to_front_fn=to_front_fn,
            player_input=player_input if isinstance(player_input, str) else "",
            graph=graph,
            previous_phase_signal=state.previous_phase_signal,
        ):
            yield ev
        return

    raise PendingConfirmationExpected("unknown pending confirmation payload")

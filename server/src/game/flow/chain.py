"""Multi-verb chain dispatch + combat-entry tail.

Split out of `turn.py` once chain handling grew past `_dispatch_verb`'s single
verb path. Owns the per-verb emit decisions inside a chain prefix and the
combat-entry helper that both single-verb and chain code paths share.
"""

import random
from collections.abc import AsyncIterator

from src.llm.calls.classify.schema import Verb
from src.llm.client import LLMClient
from src.db.repo import SaveRepo, ScenarioRepo
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from .actions import (
    emit_equip,
    emit_give,
    emit_move,
    emit_trade,
    emit_unequip,
    emit_use,
)
from .buff_tick import tick_turn_buffs
from .combat_auto import AutoCombatResult, PlayerAction
from .combat_phase import has_invalid_combat_targets, start_combat_and_drive_auto
from .dirty import Dirty, ToFrontFn, drop_pushed_act, finalize, push_act
from .error_phrases import is_dramatic_fail
from .format import NO_COMBAT_TARGETS_TEXT, format_combat_event_summary
from .narrate import stream_narrate_tail


def _resolve_transfer_emit(
    state: GameState,
    dirty: Dirty,
    *,
    mode: str,
    from_id: str,
    to_id: str,
    item_id: str,
    price: int | None,
) -> AsyncIterator[dict]:
    """Pick the inventory emit_* matching a non-steal transfer verb. Shared by
    the single-verb dispatch and the chain-internal dispatch so both paths use
    one decision table."""
    if "<self>.equipped" in to_id:
        return emit_equip(state, state.player_id, item_id, dirty)
    if "<self>.equipped" in from_id:
        return emit_unequip(state, state.player_id, item_id, dirty)
    if mode == "gift":
        return emit_give(state, from_id, to_id, item_id, dirty)
    if from_id == state.player_id:
        return emit_trade(
            state,
            state.player_id,
            to_id,
            item_id,
            dirty,
            direction="sell",
            agreed_price=price,
        )
    return emit_trade(
        state,
        state.player_id,
        from_id,
        item_id,
        dirty,
        direction="buy",
        agreed_price=price,
    )


def _emit_verb_in_chain(client, state, dirty, verb: Verb) -> AsyncIterator[dict]:
    """Dispatch a single chain-internal verb to its emit_* handler. No
    self-finalize — the chain outer loop owns narrate / finalize."""
    n = verb.name
    m = verb.modifiers or {}
    if n == "use":
        return emit_use(state, state.player_id, m["item_id"], m.get("target_id"), dirty)
    if n == "move":
        destination = m["destination"]
        return emit_move(state, state.player_id, destination, dirty)
    if n == "transfer":
        return _resolve_transfer_emit(
            state,
            dirty,
            mode=m["mode"],
            from_id=m["from_id"],
            to_id=m["to_id"],
            item_id=m["item_id"],
            price=m.get("price"),
        )
    # wait/perceive/speak/cast: absorbed by narrate inside a chain — no
    # emit. _emit_verb_in_chain handles only chain-prefix-compatible verbs.
    raise ValueError(f"verb {n!r} cannot be emitted in chain (use _dispatch_verb)")


def _is_receipt(
    state: GameState,
    action: Verb,
    pre_move_visited: set[str] | None = None,
) -> bool:
    """Receipt-only verb: act_log + state mutation, no narrate. `use` is always
    receipt; `transfer` is receipt only for equip/unequip; `move` is receipt
    only on re-visit."""
    if action.name == "use":
        return True
    if action.name == "transfer":
        mods = action.modifiers or {}
        from_id = mods.get("from_id", "")
        to_id = mods.get("to_id", "")
        if "<self>.equipped" in to_id or "<self>.equipped" in from_id:
            return True
        return False
    if action.name == "move":
        destination = (action.modifiers or {}).get("destination")
        if destination is None or pre_move_visited is None:
            return False
        return destination in pre_move_visited
    return False


def _chain_needs_narrate(
    state: GameState,
    parts: list[Verb],
    part_failures: list[bool] | None = None,
    pre_move_visited: set[str] | None = None,
) -> bool:
    """Chain narrates iff any part is narrate-worthy:
    wait/perceive/speak/cast/attack are narrate-worthy (cast/attack in prefix
    position get prose-absorbed under the current cast policy + chain-prefix
    attack-ignore policy). transfer (gift/trade) is an NPC interaction.
    first-visit move narrates. Skip: receipt-only chains (equip/unequip/
    use-self) and chains where every narrate-worthy part failed."""
    for i, part in enumerate(parts):
        if part.name in ("wait", "perceive", "speak", "cast", "attack"):
            return True
        if part.name == "transfer":
            mods = part.modifiers or {}
            mode = mods.get("mode")
            from_id = mods.get("from_id", "")
            to_id = mods.get("to_id", "")
            if "<self>.equipped" in to_id or "<self>.equipped" in from_id:
                continue
            if mode in ("gift", "trade"):
                failed = bool(part_failures[i]) if part_failures is not None else False
                if not failed:
                    return True
        if part.name == "move":
            destination = (part.modifiers or {}).get("destination")
            if destination and pre_move_visited is not None:
                if destination not in pre_move_visited:
                    failed = (
                        bool(part_failures[i]) if part_failures is not None else False
                    )
                    if not failed:
                        return True
    return False


async def _enter_combat_and_finalize(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    *,
    player_input: str,
    enemy_ids: list[str],
    skill_id: str | None,
    graph: GameGraph,
    surprise: bool = False,
    previous_phase_signal: str | None = None,
    act_log_lines: list[str] | None = None,
) -> AsyncIterator[dict]:
    """Start a fresh fight, run one auto-combat sim cycle, then finalize.
    `act_log_lines` carries chain-prefix tail_intents into the post-combat
    narrate so cast/attack absorbed lines aren't lost on a combat-tail chain."""
    player_action = PlayerAction(
        kind="skill" if skill_id else "attack",
        skill_id=skill_id,
        targets=list(enemy_ids),
    )
    combat_results: list[AutoCombatResult] = []
    async for ev in start_combat_and_drive_auto(
        client,
        state,
        scenario_repo,
        enemy_ids,
        dirty,
        rng,
        player_input=player_input,
        player_action=player_action,
        surprise="player" if surprise else None,
        graph=graph,
        _result_out=combat_results,
    ):
        yield ev
    state.turn_count += 1
    # Post-combat narrate so the system card isn't the terminal UI line — adds aftermath body and consumes the downed_recovered signal here when present. Skipped on player death (game-over) and on client=None (engine-only test path).
    # player_input is empty: the original input was already consumed by combat_narrate; this second narrate is the recovery beat, not a re-run of the player's intent.
    if client is not None and state.characters[state.player_id].alive:
        state.invalidate_graph()
        graph = state.graph()
        # Combat-set signal (e.g. downed_recovered) takes priority over the
        # pre-turn signal carried in via previous_phase_signal arg.
        signal = state.previous_phase_signal or previous_phase_signal
        state.previous_phase_signal = None
        recent_events: list[dict] = []
        if combat_results:
            recent_events.append(
                {
                    "type": "combat",
                    "summary": format_combat_event_summary(combat_results[0]),
                }
            )
        async for ev in stream_narrate_tail(
            client,
            state,
            scenario_repo,
            "",
            dirty,
            to_front_fn,
            Verb(name="wait"),
            graph=graph,
            previous_phase_signal=signal,
            recent_engine_events=recent_events,
            act_log_lines=act_log_lines,
        ):
            yield ev
    # Buffs already ticked per-round inside run_auto_combat; no /turn-end tick here.
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev


async def _run_verb_chain(
    verbs: list[Verb],
    *,
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    player_input: str,
    graph: GameGraph,
    previous_phase_signal: str | None = None,
) -> AsyncIterator[dict]:
    """Multi-verb chain dispatch — iterate list[Verb].

    tail attack → combat phase entry. tail cast is narrate-only in the current
    policy (same as single cast in _dispatch_verb — avoid self-targeting combat
    entry). prefix verbs go to _emit_verb_in_chain (use/move/transfer) or are
    absorbed by narrate (wait/perceive/speak/cast/attack — the latter two get
    prose-absorbed inside a chain). narrate decision is _chain_needs_narrate
    + dramatic_chain."""
    # Only tail attack triggers combat phase entry. cast falls into the
    # narrate-absorb path so chain semantics match single-cast in _dispatch_verb.
    tail_combat: Verb | None = (
        verbs[-1] if verbs and verbs[-1].name == "attack" else None
    )
    prefix = verbs[:-1] if tail_combat is not None else list(verbs)
    if tail_combat is None:
        state.turn_count += 1

    # pre-move snapshot
    pre_move_visited = (
        state.characters[state.player_id].visited_location_ids.copy()
        if any(p.name == "move" for p in prefix)
        else None
    )

    last_wait: Verb | None = None
    chain_act_lines: list[str] = []
    chain_act_evts: list[tuple[dict, int]] = []
    chain_failure_raws: list[str] = []
    part_failures: list[bool] = [False] * len(prefix)

    for idx, verb in enumerate(prefix):
        if verb.name == "wait":
            last_wait = verb
            continue
        if verb.name in ("speak", "perceive", "cast", "attack"):
            # In-chain narrate absorption — no emit; narrate handles prose.
            # cast/attack in prefix position are not phase-changing (tail is
            # non-combat), so narrate describes them as prose. Skipping emit
            # here also avoids the ValueError that _emit_verb_in_chain raises
            # for these verbs.
            tail_intent = (verb.modifiers or {}).get("tail_intent")
            if tail_intent:
                chain_act_lines.append(tail_intent)
            continue
        # use / move / transfer → emit_*
        async for ev in _emit_verb_in_chain(client, state, dirty, verb):
            if ev.get("type") == "_engine_fail":
                chain_failure_raws.append(
                    (ev.get("data") or {}).get("raw_error_msg") or ""
                )
                part_failures[idx] = True
                continue
            if ev.get("type") == "log_entry":
                d = ev.get("data") or {}
                if d.get("kind") == "act":
                    text = d.get("text") or ""
                    if text:
                        chain_act_lines.append(text)
                    chain_act_evts.append((ev, idx))
                    continue
            yield ev
        if (verb.modifiers or {}).get("tail_intent"):
            chain_act_lines.append(verb.modifiers["tail_intent"])

    state.invalidate_graph()
    graph = state.graph()
    if any(p.name == "move" for p in prefix):
        from .subject import pin_subject_by_input_name

        pin_subject_by_input_name(state, player_input, graph)

    if tail_combat is not None:
        # combat path — handle prefix act cards.
        for ev, part_idx in chain_act_evts:
            keep_card = prefix[part_idx].name == "move" and not part_failures[part_idx]
            if keep_card:
                yield ev
            else:
                drop_pushed_act(state, dirty, (ev.get("data") or {}).get("id"))
        targets = list(tail_combat.target_ids)
        if has_invalid_combat_targets(state, graph, targets):
            fail_line = NO_COMBAT_TARGETS_TEXT
            if client is None:
                yield push_act(state, dirty, fail_line)
            else:
                fail_evt = push_act(state, dirty, fail_line)
                drop_pushed_act(state, dirty, (fail_evt.get("data") or {}).get("id"))
                chain_act_lines.append(fail_line)
                async for ev in stream_narrate_tail(
                    client,
                    state,
                    scenario_repo,
                    player_input,
                    dirty,
                    to_front_fn,
                    Verb(name="wait"),
                    graph=graph,
                    act_log_lines=chain_act_lines,
                    previous_phase_signal=previous_phase_signal,
                ):
                    yield ev
            async for ev in finalize(state, save_repo, dirty, to_front_fn):
                yield ev
            return
        async for ev in _enter_combat_and_finalize(
            client,
            state,
            scenario_repo,
            save_repo,
            dirty,
            rng,
            to_front_fn,
            player_input=player_input,
            enemy_ids=targets,
            skill_id=(tail_combat.modifiers or {}).get("skill_id"),
            graph=graph,
            surprise=bool((tail_combat.modifiers or {}).get("surprise", False)),
            previous_phase_signal=previous_phase_signal,
            act_log_lines=chain_act_lines or None,
        ):
            yield ev
        return

    # narrate path
    narrate_action = last_wait if last_wait is not None else Verb(name="wait")
    dramatic_chain = any(is_dramatic_fail(r) for r in chain_failure_raws)
    narrate_chain = (
        _chain_needs_narrate(state, prefix, part_failures, pre_move_visited)
        or dramatic_chain
    )

    if narrate_chain:
        for ev, part_idx in chain_act_evts:
            keep_card = prefix[part_idx].name == "move" and not part_failures[part_idx]
            if keep_card:
                yield ev
            else:
                drop_pushed_act(state, dirty, (ev.get("data") or {}).get("id"))
        async for ev in stream_narrate_tail(
            client,
            state,
            scenario_repo,
            player_input,
            dirty,
            to_front_fn,
            narrate_action,
            graph=graph,
            act_log_lines=chain_act_lines,
            previous_phase_signal=previous_phase_signal,
        ):
            yield ev
    else:
        for ev, _part_idx in chain_act_evts:
            yield ev
        if to_front_fn is not None:
            yield {"type": "state", "data": to_front_fn(state)}

    tick_turn_buffs(state, dirty)
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev

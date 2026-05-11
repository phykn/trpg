from src.game.domain.action import Action
from src.game.domain.content import node_label
from src.game.domain.graph import GraphNode
from src.game.domain.graph_query import location_of
from src.game.domain.memory import ActLogEntry
from src.game.domain.types import GraphStatKey
from src.locale.labels import stat_label
from src.locale.render import render

from .dispatch import GraphActionDispatchResult
from .state import GameRuntimeState


def build_graph_action_card(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
) -> ActLogEntry:
    return ActLogEntry(
        id=after.progress.next_log_id,
        kind="act",
        text=_card_text(before, after, action, dispatch),
    )


def build_graph_quest_offer_card(
    runtime: GameRuntimeState,
    quest_id: str,
    log_id: int,
) -> ActLogEntry:
    quest = _quest_title(runtime, quest_id)
    return ActLogEntry(
        id=log_id,
        kind="act",
        text=render("runtime.card.quest_offer", runtime.progress.locale, quest=quest),
    )


def build_graph_level_up_card(
    runtime: GameRuntimeState,
    stat_up: GraphStatKey,
    log_id: int,
) -> ActLogEntry:
    player = runtime.graph.nodes[runtime.progress.player_id]
    level = _int_property(player, "level")
    max_hp = _int_property(player, "max_hp")
    max_mp = _int_property(player, "max_mp")
    return ActLogEntry(
        id=log_id,
        kind="act",
        text=render(
            "runtime.card.level_up",
            runtime.progress.locale,
            actor=node_label(runtime.content, player),
            level=level,
            stat=stat_label(stat_up, runtime.progress.locale),
            max_hp=max_hp,
            max_mp=max_mp,
        ),
    )


def _card_text(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
) -> str:
    if dispatch.kind == "move":
        destination_id = location_of(after.graph, after.progress.player_id)
        destination = _node_label(
            after,
            destination_id,
            fallback=render("runtime.fallback.destination", after.progress.locale),
        )
        return render(
            "runtime.card.move", after.progress.locale, destination=destination
        )

    if dispatch.kind == "combat":
        return _combat_text(before, after, action, dispatch)

    if dispatch.kind == "quest_accept":
        quest = _quest_title(
            after,
            _single(action.what) or _single(action.to),
        )
        return render("runtime.card.quest_accept", after.progress.locale, quest=quest)

    if dispatch.kind == "quest_abandon":
        quest = _quest_title(
            after,
            _single(action.what) or _single(action.to),
        )
        return render("runtime.card.quest_abandon", after.progress.locale, quest=quest)

    if dispatch.kind == "rest":
        return render("runtime.card.rest", after.progress.locale)

    if dispatch.kind == "equip":
        item = _node_label(after, _single(action.what) or _single(action.with_))
        return render("runtime.card.equip", after.progress.locale, item=item)

    if dispatch.kind == "unequip":
        item = _node_label(after, _single(action.what) or _single(action.with_))
        return render("runtime.card.unequip", after.progress.locale, item=item)

    if dispatch.kind == "use":
        item = _node_label(after, _single(action.what) or _single(action.with_))
        return render("runtime.card.use", after.progress.locale, item=item)

    if dispatch.kind == "transfer":
        item = _node_label(after, _single(action.what) or _single(action.with_))
        return render("runtime.card.transfer", after.progress.locale, item=item)

    return render("runtime.card.generic", after.progress.locale)


def _combat_text(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
) -> str:
    if before.progress.graph_combat_state is None:
        target_id = _single(action.what) or _single(action.to)
        target = _node_label(
            after,
            target_id,
            fallback=render("runtime.fallback.target", after.progress.locale),
        )
        return render("runtime.combat.start", after.progress.locale, target=target)
    outcome = dispatch.outcome
    if outcome is None and after.progress.graph_combat_state is not None:
        outcome = after.progress.graph_combat_state.outcome
    if outcome == "fled":
        return render("runtime.combat.fled", after.progress.locale)
    if outcome == "defeat":
        return render("runtime.combat.defeat", after.progress.locale)
    if outcome == "victory":
        return render("runtime.combat.victory", after.progress.locale)
    return render("runtime.combat.continue", after.progress.locale)


def _quest_title(runtime: GameRuntimeState, quest_id: str | None) -> str:
    node = runtime.graph.nodes.get(quest_id or "")
    if node is None or node.type != "quest":
        return render("runtime.fallback.quest", runtime.progress.locale)
    return node_label(runtime.content, node)


def _node_label(
    runtime: GameRuntimeState,
    node_id: str | None,
    *,
    fallback: str | None = None,
) -> str:
    node = runtime.graph.nodes.get(node_id or "")
    if node is not None:
        return node_label(runtime.content, node)
    return fallback or render("runtime.fallback.target", runtime.progress.locale)


def _int_property(node: GraphNode, key: str) -> int:
    value = node.properties.get(key)
    return value if isinstance(value, int) else 0


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None

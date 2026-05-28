from src.game.domain.action import Action
from src.game.domain.content import node_label, node_text
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph.query import location_of
from src.game.domain.quest import quest_triggers

from ..action_refs import first_ref
from ..state import GameRuntimeState


def should_start_graph_roll(
    runtime: GameRuntimeState,
    action: Action,
    *,
    check_required: bool = False,
    player_input: str | None = None,
) -> bool:
    if _roll_forbidden(runtime, action):
        return False
    if runtime.progress.graph_combat_state is not None:
        return False
    if (
        runtime.story_contract is not None
        and action.verb == "perceive"
        and not check_required
    ):
        return False
    if _roll_required_by_server(runtime, action, player_input=player_input):
        return True
    if not check_required:
        return False
    return _roll_allowed_from_check_hint(runtime, action)


def _roll_forbidden(runtime: GameRuntimeState, action: Action) -> bool:
    if action.verb in {"attack", "rest", "pass"}:
        return True
    if action.verb != "transfer":
        return False
    if action.how in {"accept", "abandon", "equip", "unequip", "steal", "trade"}:
        return True
    return _is_public_pickup(runtime, action)


def _roll_required_by_server(
    runtime: GameRuntimeState,
    action: Action,
    *,
    player_input: str | None = None,
) -> bool:
    if action.verb == "perceive":
        return True
    if action.verb == "move":
        return _is_risky_move(runtime, action)
    if action.verb == "speak":
        return action.how in {"hostile", "deceptive", "recruit"} or _matches_active_social_check(
            runtime,
            action,
            player_input=player_input,
        )
    return False


def _matches_active_social_check(
    runtime: GameRuntimeState,
    action: Action,
    *,
    player_input: str | None = None,
) -> bool:
    target = first_ref(action.what) or first_ref(action.to)
    if target is None:
        return False
    active_id = runtime.progress.active_quest_id
    if active_id is None:
        return False
    quest = runtime.graph.nodes.get(active_id)
    if quest is None or quest.type != "quest":
        return False
    for trigger in quest_triggers(quest):
        if trigger.get("type") != "social_check" or trigger.get("target") != target:
            continue
        if not _social_check_input_matches(runtime, quest, trigger, player_input):
            continue
        return True
    return False


def _social_check_input_matches(
    runtime: GameRuntimeState,
    quest: GraphNode,
    trigger: dict,
    player_input: str | None,
) -> bool:
    if player_input is None:
        return True
    input_text = _normalize_match_text(player_input)
    if not input_text:
        return False
    target = trigger.get("target")
    target_refs = _target_match_refs(runtime, target if isinstance(target, str) else None)
    for text in _social_check_match_texts(runtime, quest, trigger):
        for token in _match_tokens(text):
            normalized = _normalize_match_text(token)
            if not normalized or normalized in target_refs:
                continue
            if normalized in input_text:
                return True
    return False


def _social_check_match_texts(
    runtime: GameRuntimeState,
    quest: GraphNode,
    trigger: dict,
) -> list[str]:
    out: list[str] = []
    for value in (
        trigger.get("name"),
        node_label(runtime.content, quest),
        node_text(runtime.content, quest, "description"),
        quest.properties.get("title"),
        quest.properties.get("name"),
        quest.properties.get("description"),
    ):
        if isinstance(value, str) and value.strip():
            out.append(value)
    return out


def _target_match_refs(runtime: GameRuntimeState, target: str | None) -> set[str]:
    if target is None:
        return set()
    refs = {_normalize_match_text(target)}
    node = runtime.graph.nodes.get(target)
    if node is not None:
        label = node_label(runtime.content, node)
        refs.add(_normalize_match_text(label))
        refs.update(_normalize_match_text(token) for token in _match_tokens(label))
    return {ref for ref in refs if ref}


def _match_tokens(text: str) -> list[str]:
    return [
        token
        for token in text.replace(",", " ").replace(".", " ").split()
        if len(token) >= 2 and not token.endswith((_ko_to_person(), _ko_honorific_to_person()))
    ]


def _normalize_match_text(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _ko_to_person() -> str:
    return chr(0xC5D0) + chr(0xAC8C)


def _ko_honorific_to_person() -> str:
    return chr(0xAED8)


def _roll_allowed_from_check_hint(runtime: GameRuntimeState, action: Action) -> bool:
    if action.verb in {"move", "use", "speak", "perceive"}:
        return True
    if action.verb != "transfer":
        return False
    if action.how != "free":
        return False
    return not _is_public_pickup(runtime, action)


def _is_risky_move(runtime: GameRuntimeState, action: Action) -> bool:
    if action.how == "hasty":
        return True
    source_id = location_of(runtime.graph, runtime.progress.player_id)
    destination_id = first_ref(action.to) or first_ref(action.what)
    if source_id is None or destination_id is None:
        return False
    for edge in runtime.graph.edges.values():
        if (
            edge.type == "connects_to"
            and edge.from_node_id == source_id
            and edge.to_node_id == destination_id
        ):
            return edge.properties.get("difficulty") is not None
    return False


def _is_public_pickup(runtime: GameRuntimeState, action: Action) -> bool:
    item_id = first_ref(action.what) or first_ref(action.with_)
    if item_id is None:
        return False
    to_id = first_ref(action.to) or runtime.progress.player_id
    if to_id != runtime.progress.player_id:
        return False
    source_id = first_ref(action.from_) or _item_owner(runtime.graph, item_id)
    if source_id is None:
        return False
    source = runtime.graph.nodes.get(source_id)
    return source is not None and source.type == "location"


def _item_owner(graph: Graph, item_id: str) -> str | None:
    for edge in graph.edges.values():
        if edge.type in {"located_at", "hidden_at", "reward_of"} and edge.from_node_id == item_id:
            return edge.to_node_id
        if edge.type in {"carries", "equips"} and edge.to_node_id == item_id:
            return edge.from_node_id
    return None

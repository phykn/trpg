from src.game.domain.content import RuntimeContent
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph_character import (
    can_character_fight,
    graph_character_kind,
    is_visible_character,
)
from src.game.domain.graph_query import characters_at, edges_from, location_of
from .characher import (
    character_equipment,
    character_gender,
    character_inventory,
    character_race_job,
    character_skills,
    character_stats,
    character_status,
)
from .values import (
    int_prop_default,
    node_name,
    optional_str,
    require_node,
    static_value,
)
from src.wire.models import (
    GraphPlaceLinkPayload,
    GraphPlacePayload,
    GraphPlaceTargetPayload,
)


def place_payload(
    graph: Graph,
    player_id: str,
    locale: str = "ko",
    content: RuntimeContent | None = None,
) -> GraphPlacePayload | None:
    location_id = location_of(graph, player_id)
    if location_id is None:
        return None
    location = graph.nodes.get(location_id)
    if location is None or location.type != "location":
        return None

    exits: list[GraphPlaceLinkPayload] = []
    for edge in edges_from(graph, location_id, "connects_to"):
        target = graph.nodes.get(edge.to_node_id)
        if target is None or target.type != "location":
            continue
        exits.append(_place_link(target, content))

    targets: list[GraphPlaceTargetPayload] = []
    for character_id in characters_at(graph, location_id):
        if character_id == player_id:
            continue
        target = require_node(graph, character_id, "character")
        if not is_visible_character(target):
            continue
        targets.append(
            GraphPlaceTargetPayload(
                id=target.id,
                name=node_name(target, content),
                kind=graph_character_kind(target),
                alive=can_character_fight(target),
                level=int_prop_default(target, "level", 1),
                race_job=character_race_job(target, content),
                gender=character_gender(target, locale, content),
                role=optional_str(static_value(target, "role", content)) or "",
                gold=int_prop_default(target, "gold", 0),
                stats=character_stats(target),
                equipment=character_equipment(graph, target.id, content),
                inventory=character_inventory(graph, target.id, content),
                skills=character_skills(graph, target.id, content),
                status=character_status(target),
            )
        )

    return GraphPlacePayload(
        id=location.id,
        name=node_name(location, content),
        description=optional_str(static_value(location, "description", content)) or "",
        exits=exits,
        targets=targets,
    )


def _place_link(
    location: GraphNode,
    content: RuntimeContent | None = None,
) -> GraphPlaceLinkPayload:
    return GraphPlaceLinkPayload(
        id=location.id,
        name=node_name(location, content),
        description=optional_str(static_value(location, "description", content)) or "",
    )

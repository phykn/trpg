from src.game.domain.content import RuntimeContent
from src.game.domain.graph import Graph, GraphNode
from src.game.engines.growth import xp_for_next_level
from src.wire.graph_character_view import (
    character_equipment,
    character_inventory,
    character_skills,
    character_stats,
    character_status,
)
from src.wire.graph_payload_helpers import (
    int_prop_default,
    node_name,
    resource,
)
from src.wire.models import GraphHeroPayload


def hero_payload(
    graph: Graph,
    player: GraphNode,
    content: RuntimeContent | None = None,
) -> GraphHeroPayload:
    level = int_prop_default(player, "level", 1)
    exp = int_prop_default(player, "xp_pool", 0)
    exp_max = xp_for_next_level(level)
    return GraphHeroPayload(
        id=player.id,
        name=node_name(player, content),
        level=level,
        gold=int_prop_default(player, "gold", 0),
        exp=exp,
        exp_max=exp_max,
        can_level_up=exp_max > 0 and exp >= exp_max,
        resources={
            "hp": resource(player, "hp", "max_hp"),
            "mp": resource(player, "mp", "max_mp"),
        },
        stats=character_stats(player),
        equipment=character_equipment(graph, player.id, content),
        inventory=character_inventory(graph, player.id, content),
        status=character_status(player),
        skills=character_skills(graph, player.id, content),
    )

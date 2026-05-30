import secrets
from datetime import datetime, timezone
from typing import Literal

from src.db.repo import GraphRepo
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.domain.story_contract import StoryContract
from src.game.seed.player import PlayerInput
from src.locale.render import render

from ..state import GameRuntimeState


async def initialize_contract_generated_runtime(
    profile: str,
    player: PlayerInput,
    graph_repo: GraphRepo,
    *,
    contract: StoryContract,
    locale: Literal["ko", "en"],
) -> GameRuntimeState:
    game_id = _new_game_id()
    graph = _generated_graph(profile, player, locale)
    progress = GameProgress(
        game_id=game_id,
        player_id="player_01",
        profile_id=profile,
        locale=locale,
    )
    await graph_repo.save_progress(progress)
    await graph_repo.save_graph(game_id, graph)
    return GameRuntimeState(
        graph=graph,
        progress=progress,
        story_contract=contract,
    )


def _new_game_id() -> str:
    return datetime.now(timezone.utc).strftime(
        "game_%y%m%d_%H%M%S_"
    ) + secrets.token_hex(3)


def _generated_graph(profile: str, player: PlayerInput, locale: str) -> Graph:
    nodes = {
        "player_01": GraphNode(
            id="player_01",
            type="character",
            properties={
                "name": _player_value(player, "name")
                or render("runtime.generated.player.name", locale),
                "is_player": True,
                "level": 1,
                "gold": 0,
                "xp_pool": 0,
                "hp": 5,
                "max_hp": 5,
                "mp": 5,
                "max_mp": 5,
                "stats": {
                    "body": 1,
                    "agility": 1,
                    "mind": 1,
                    "presence": 1,
                },
            },
        ),
        "loc_fog_harbor": GraphNode(
            id="loc_fog_harbor",
            type="location",
            properties={
                "name": render("runtime.generated.loc_fog_harbor.name", locale),
                "description": render(
                    "runtime.generated.loc_fog_harbor.description",
                    locale,
                ),
            },
        ),
    }
    edges = {
        "located_at:player_01:loc_fog_harbor": GraphEdge(
            id="located_at:player_01:loc_fog_harbor",
            type="located_at",
            from_node_id="player_01",
            to_node_id="loc_fog_harbor",
        )
    }
    if profile == "white_isle":
        nodes["npc_ellie"] = GraphNode(
            id="npc_ellie",
            type="character",
            properties={
                "name": render("runtime.generated.npc_ellie.name", locale),
                "alive": True,
                "level": 1,
                "hp": 5,
                "max_hp": 5,
                "mp": 5,
                "max_mp": 5,
                "stats": {
                    "body": 1,
                    "agility": 1,
                    "mind": 1,
                    "presence": 1,
                },
                "role": render("runtime.generated.npc_ellie.role", locale),
                "gender": "female",
                "race_job": render("runtime.generated.npc_ellie.race_job", locale),
            },
        )
        edges["located_at:npc_ellie:loc_fog_harbor"] = GraphEdge(
            id="located_at:npc_ellie:loc_fog_harbor",
            type="located_at",
            from_node_id="npc_ellie",
            to_node_id="loc_fog_harbor",
        )
    return Graph(nodes=nodes, edges=edges)


def _player_value(player: PlayerInput, field: str) -> str | None:
    if isinstance(player, dict):
        value = player.get(field)
    else:
        value = getattr(player, field, None)
    return value if isinstance(value, str) and value else None

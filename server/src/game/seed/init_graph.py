import asyncio
import secrets
from datetime import datetime, timezone

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.entities import (
    Chapter,
    Character,
    Item,
    Location,
    Quest,
    Race,
    Skill as SkillModel,
)
from src.game.domain.errors import ProfileMalformed, ProfileNotFound, RaceNotFound
from src.game.engines.invariants import Scenario, check_scenario
from src.game.seed.graph_seed import SeedGraphBundle, build_seed_graph
from src.game.seed.player import PlayerInput


async def init_graph_game(
    profile_name: str,
    player: PlayerInput,
    graph_repo: GraphRepo,
    scenario_repo: ScenarioRepo,
    locale: str = "ko",
) -> SeedGraphBundle:
    if not await scenario_repo.profile_exists(profile_name):
        raise ProfileNotFound(profile_name)

    (
        races,
        locations,
        items,
        skills,
        npcs,
        quests,
        chapters,
        start,
        template,
    ) = await asyncio.gather(
        scenario_repo.load_seed_entities(profile_name, "races", Race),
        scenario_repo.load_seed_entities(profile_name, "locations", Location),
        scenario_repo.load_seed_entities(profile_name, "items", Item),
        scenario_repo.load_seed_entities(profile_name, "skills", SkillModel),
        scenario_repo.load_seed_entities(profile_name, "characters", Character),
        scenario_repo.load_seed_entities(profile_name, "quests", Quest),
        scenario_repo.load_seed_entities(profile_name, "chapters", Chapter),
        scenario_repo.read_start_json(profile_name),
        scenario_repo.read_player_template(profile_name),
    )

    seed_violations = check_scenario(
        Scenario(
            races=races,
            locations=locations,
            items=items,
            skills=skills,
            characters=npcs,
            quests=quests,
            chapters=chapters,
            start=start,
            player_template=template,
        )
    )
    if seed_violations:
        raise ProfileMalformed(
            f"profile {profile_name!r} invariant violations:\n"
            + "\n".join(seed_violations)
        )

    if player.race_id not in races:
        raise RaceNotFound(player.race_id)

    game_id = (
        datetime.now(timezone.utc).strftime("game_%y%m%d_%H%M%S_")
        + secrets.token_hex(3)
    )
    bundle = build_seed_graph(
        profile_name=profile_name,
        player=player,
        races=races,
        locations=locations,
        items=items,
        skills=skills,
        npcs=npcs,
        quests=quests,
        chapters=chapters,
        start=start,
        template=template,
        game_id=game_id,
        locale=locale,
    )

    await graph_repo.save_graph(bundle.progress.game_id, bundle.graph)
    await graph_repo.save_progress(bundle.progress)
    return bundle

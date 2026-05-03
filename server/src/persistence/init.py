import asyncio
import secrets
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from ..domain.entities import (
    Campaign,
    Chapter,
    Character,
    Equipment,
    Item,
    Location,
    Quest,
    Race,
    Skill as SkillModel,
    Stats,
)
from ..domain.errors import ProfileMalformed, ProfileNotFound, RaceNotFound
from ..domain.state import GameState
from ..engines.growth import calc_max_hp, calc_max_mp
from ..engines.invariants import Scenario, check_scenario
from ..rules.config import RULES
from .repo import SaveRepo, ScenarioRepo


class PlayerInput(BaseModel):
    name: str
    race_id: str
    gender: Literal["male", "female"]


async def init_game(
    profile_name: str,
    player: PlayerInput,
    save_repo: SaveRepo,
    scenario_repo: ScenarioRepo,
) -> GameState:
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
        campaigns,
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
        scenario_repo.load_seed_entities(profile_name, "campaigns", Campaign),
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

    # start.json / player_template integrity is already covered by
    # `check_scenario(...)` above (start_location_id, active_subject_id alive
    # + colocated, active_quest_id status, etc.). Anything that gets here is
    # well-formed.
    player_id = template.get("id", "player_01")
    template_equipment = Equipment.model_validate(template.get("equipment", {}))
    template_inventory = list(template.get("inventory_ids", []))
    location_id = start["start_location_id"]
    active_subject_id = start.get("active_subject_id")
    active_quest_id = start.get("active_quest_id")

    stats = Stats()
    chosen_race = races[player.race_id]

    player_char = Character(
        id=player_id,
        name=player.name,
        is_player=True,
        race_id=player.race_id,
        gender=player.gender,
        stats=stats,
        location_id=location_id,
        equipment=template_equipment,
        inventory_ids=template_inventory,
        gold=int(template.get("gold", 0)),
        xp_pool=int(template.get("xp_pool", 0)),
        racial_skill_ids=list(chosen_race.racial_skill_ids),
        revive_coins=RULES.death.revive_coins,
    )
    player_char.max_hp = calc_max_hp(player_char.level, stats.CON)
    player_char.max_mp = calc_max_mp(player_char.level, stats.INT)
    player_char.hp = player_char.max_hp
    player_char.mp = player_char.max_mp
    # Spawn counts as the first visit; otherwise returning to it trips first-visit narrate.
    player_char.visited_location_ids.add(location_id)

    characters: dict[str, Character] = {**npcs, player_id: player_char}

    state = GameState(
        game_id=(
            datetime.now(timezone.utc).strftime("game_%y%m%d_%H%M%S_")
            + secrets.token_hex(3)
        ),
        profile=profile_name,
        characters=characters,
        items=items,
        locations=locations,
        races=races,
        skills=skills,
        quests=quests,
        chapters=chapters,
        campaigns=campaigns,
        player_id=player_id,
        active_subject_id=active_subject_id,
        active_quest_id=active_quest_id,
    )

    await save_repo.copy_seed_into_game(
        scenario_repo, profile_name, state.game_id, player_id
    )
    # Persist the player character separately — it isn't part of the seed.
    await save_repo.save_entity(state, "characters", player_id)
    await save_repo.save_meta(state)
    return state

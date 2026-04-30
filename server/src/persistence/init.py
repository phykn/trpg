import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Type, TypeVar

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
from .store import (
    copy_seed_into_game,
    save_entity,
    save_meta,
    write_current_game_id,
)

T = TypeVar("T", bound=BaseModel)


class PlayerInput(BaseModel):
    name: str
    race_id: str
    gender: Literal["male", "female"]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _scan_dir(dirpath: Path, model_cls: Type[T]) -> dict[str, T]:
    result: dict[str, T] = {}
    if not dirpath.is_dir():
        return result
    for f in sorted(dirpath.glob("*.json")):
        obj = model_cls.model_validate(_read_json(f))
        # All seed models have an `id` attribute (Character, Item, Location, Quest,
        # Race, Chapter, Campaign). The Pydantic schema enforces it.
        result[obj.id] = obj  # type: ignore[attr-defined]
    return result


async def init_game(
    profile_name: str,
    player: PlayerInput,
    saves_dir: str,
    profile_dir: str,
) -> GameState:
    pdir = Path(profile_dir) / profile_name
    if not pdir.is_dir():
        raise ProfileNotFound(profile_name)

    seed_violations = check_scenario(Scenario.from_dir(pdir))
    if seed_violations:
        raise ProfileMalformed(
            f"profile {profile_name!r} invariant violations:\n"
            + "\n".join(seed_violations)
        )

    races = _scan_dir(pdir / "races", Race)
    if player.race_id not in races:
        raise RaceNotFound(player.race_id)

    locations = _scan_dir(pdir / "locations", Location)
    items = _scan_dir(pdir / "items", Item)
    skills = _scan_dir(pdir / "skills", SkillModel)
    npcs = _scan_dir(pdir / "characters", Character)
    quests = _scan_dir(pdir / "quests", Quest)
    chapters = _scan_dir(pdir / "chapters", Chapter)
    campaigns = _scan_dir(pdir / "campaigns", Campaign)

    start = _read_json(pdir / "start.json")
    template = _read_json(pdir / "player_template.json")

    # start.json / player_template integrity is already covered by
    # `check_scenario(Scenario.from_dir(pdir))` above (start_location_id,
    # active_subject_id alive + colocated, active_quest_id status, etc.).
    # Anything that gets here is well-formed.
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
    )
    player_char.max_hp = calc_max_hp(player_char.level, stats.CON)
    player_char.max_mp = calc_max_mp(player_char.level, stats.INT)
    player_char.hp = player_char.max_hp
    player_char.mp = player_char.max_mp

    characters: dict[str, Character] = {**npcs, player_id: player_char}

    state = GameState(
        game_id=datetime.now().strftime("game_%y%m%d_%H%M%S"),
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

    copy_seed_into_game(profile_dir, profile_name, saves_dir, state.game_id)
    # Persist the player character separately — it isn't part of the seed.
    await save_entity(state, saves_dir, "characters", player_id)
    await save_meta(state, saves_dir)
    await write_current_game_id(saves_dir, state.game_id)
    return state

import json
from datetime import datetime
from pathlib import Path
from typing import Type, TypeVar

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
    Stats,
)
from ..domain.errors import ProfileNotFound, RaceNotFound
from ..domain.state import GameState
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
    appearance: str


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


def _compute_max_hp(con: int, level: int) -> int:
    return (10 + con) + level * (5 + con // 4)


def _compute_max_mp(int_stat: int, level: int) -> int:
    return (5 + int_stat) + level * (3 + int_stat // 4)


async def init_game(
    profile_name: str,
    player: PlayerInput,
    saves_dir: str,
    profile_dir: str,
) -> GameState:
    pdir = Path(profile_dir) / profile_name
    if not pdir.is_dir():
        raise ProfileNotFound(profile_name)

    races = _scan_dir(pdir / "races", Race)
    if player.race_id not in races:
        raise RaceNotFound(player.race_id)

    locations = _scan_dir(pdir / "locations", Location)
    items = _scan_dir(pdir / "items", Item)
    npcs = _scan_dir(pdir / "characters", Character)
    quests = _scan_dir(pdir / "quests", Quest)
    chapters = _scan_dir(pdir / "chapters", Chapter)
    campaigns = _scan_dir(pdir / "campaigns", Campaign)

    start = _read_json(pdir / "start.json")
    template = _read_json(pdir / "player_template.json")

    player_id = template.get("id", "player_01")
    template_equipment = Equipment.model_validate(template.get("equipment", {}))
    template_inventory = list(template.get("inventory_ids", []))
    location_id = start["start_location_id"]

    stats = Stats()
    chosen_race = races[player.race_id]

    player_char = Character(
        id=player_id,
        name=player.name,
        appearance=player.appearance,
        is_player=True,
        race_id=player.race_id,
        stats=stats,
        location_id=location_id,
        equipment=template_equipment,
        inventory_ids=template_inventory,
        racial_skills=[s.model_copy() for s in chosen_race.racial_skills],
    )
    player_char.max_hp = _compute_max_hp(stats.CON, player_char.level)
    player_char.max_mp = _compute_max_mp(stats.INT, player_char.level)
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
        quests=quests,
        chapters=chapters,
        campaigns=campaigns,
        player_id=player_id,
        active_subject_id=start.get("active_subject_id"),
        active_quest_id=start.get("active_quest_id"),
        world_time=start["world_time"],
    )

    copy_seed_into_game(profile_dir, profile_name, saves_dir, state.game_id)
    # Persist the player character separately — it isn't part of the seed.
    await save_entity(state, saves_dir, "characters", player_id)
    await save_meta(state, saves_dir)
    await write_current_game_id(saves_dir, state.game_id)
    return state

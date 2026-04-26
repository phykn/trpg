from typing import Literal

from pydantic import BaseModel

from ..domain.entities import (
    Campaign,
    Chapter,
    Character,
    Item,
    Location,
    Quest,
    Race,
    Skill,
)
from ..domain.memory import (
    DialoguePair,
    LogEntry,
    PendingCheck,
    TurnLogEntry,
)


class CombatState(BaseModel):
    turn_order: list[str] = []
    current_turn: int = 0
    round: int = 1
    surprise: Literal["player", "enemy"] | None = None
    enemy_ids: list[str] = []
    damage_dealt: dict[str, int] = {}  # actor_id → cumulative damage (for highest_threat AI)


class GameState(BaseModel):
    game_id: str
    profile: str

    characters: dict[str, Character] = {}
    items: dict[str, Item] = {}
    locations: dict[str, Location] = {}
    races: dict[str, Race] = {}
    quests: dict[str, Quest] = {}
    chapters: dict[str, Chapter] = {}
    campaigns: dict[str, Campaign] = {}

    player_id: str
    active_subject_id: str | None = None
    active_quest_id: str | None = None

    world_time: str

    turn_count: int = 0
    pending_check: PendingCheck | None = None
    combat_state: CombatState | None = None
    pending_skill_candidates: list[Skill] = []

    turn_log: list[TurnLogEntry] = []
    recent_dialogue: list[DialoguePair] = []

    log_entries: list[LogEntry] = []
    next_log_id: int = 1

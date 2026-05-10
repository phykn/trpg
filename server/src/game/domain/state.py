from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, PrivateAttr

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
    TurnLogEntry,
)

if TYPE_CHECKING:
    from ..ontology.graph import GameGraph


class CombatState(BaseModel):
    turn_order: list[str] = []
    current_turn: int = 0
    round: int = 1
    surprise: Literal["player", "enemy"] | None = None
    enemy_ids: list[str] = []
    damage_dealt: dict[str, int] = {}
    # Persisted across rounds by the old entity combat engine.
    player_target_id: str | None = None
    player_skill_id: str | None = None
    player_skill_used: bool = False
    player_intent: str = ""


class GameState(BaseModel):
    game_id: str
    profile: str
    locale: str = "ko"

    characters: dict[str, Character] = {}
    items: dict[str, Item] = {}
    locations: dict[str, Location] = {}
    races: dict[str, Race] = {}
    skills: dict[str, Skill] = {}
    quests: dict[str, Quest] = {}
    chapters: dict[str, Chapter] = {}
    campaigns: dict[str, Campaign] = {}

    player_id: str
    active_subject_id: str | None = None
    active_quest_id: str | None = None

    turn_count: int = 0
    pending_confirmation: dict[str, object] | None = None
    combat_state: CombatState | None = None

    # Hand-off to next narrate (e.g. `"downed_recovered"`); narrate consumes + clears so it doesn't echo.
    previous_phase_signal: str | None = None

    turn_log: list[TurnLogEntry] = []
    recent_dialogue: list[DialoguePair] = []

    # Transient engine notices for the current turn (judge_rejected, etc.).
    # Appended during the turn; naturally ages out as turn_count advances.
    # Not relied on after the turn that produced them.
    recent_engine_events: list[dict] = []

    log_entries: list[LogEntry] = []
    next_log_id: int = 1

    # Lazy graph cache — flow callers invalidate after relation-touching writes. PrivateAttr keeps it off the wire.
    _graph_cache: "GameGraph | None" = PrivateAttr(default=None)

    def graph(self) -> "GameGraph":
        """Cached relational graph. Mutators of relation fields must `invalidate_graph()` before re-reading."""
        if self._graph_cache is None:
            from ..ontology.graph import build_graph

            self._graph_cache = build_graph(self)
        return self._graph_cache

    def invalidate_graph(self) -> None:
        """Drop the cached graph so the next `graph()` rebuilds. Call after any write that touches a relation field."""
        self._graph_cache = None

    def recent_npc_id(self, actor_id: str) -> str | None:
        """Most recently addressed alive same-location NPC — anchors pronoun follow-ups to the same NPC."""
        if not self.turn_log:
            return None
        actor = self.characters.get(actor_id)
        actor_loc = actor.location_id if actor is not None else None
        for entry in reversed(self.turn_log):
            tid = entry.target
            if tid is None or tid == actor_id:
                continue
            npc = self.characters.get(tid)
            if npc is None or not npc.alive:
                continue
            if actor_loc is not None and npc.location_id != actor_loc:
                continue
            return tid
        return None

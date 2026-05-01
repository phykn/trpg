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
    PendingCheck,
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
    damage_dealt: dict[
        str, int
    ] = {}  # actor_id → cumulative damage (for highest_threat AI)
    # Player intent persisted across rounds — cinematic resolves one round per
    # /roll click, so each round's player attack/skill needs to be reconstructed
    # from these instead of fresh function args.
    player_target_id: str | None = None
    player_skill_id: str | None = None
    player_skill_used: bool = False
    player_intent: str = ""


class GameState(BaseModel):
    game_id: str
    profile: str

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
    pending_check: PendingCheck | None = None
    combat_state: CombatState | None = None
    pending_skill_candidates: list[Skill] = []

    # One-shot signal handed to the next narrate call so prose can reflect
    # the just-finished phase. Set when combat ends with a downed→stable
    # revive (player blacked out then woke); narrate consumes and clears it
    # on its next turn so the body opens with recovery, not amnesia. None
    # means "previous turn was ordinary."
    previous_phase_signal: str | None = None

    turn_log: list[TurnLogEntry] = []
    recent_dialogue: list[DialoguePair] = []

    log_entries: list[LogEntry] = []
    next_log_id: int = 1

    # Lazy graph cache. Built on first `graph()` call, invalidated by callers
    # in flow after relation-touching writes (CLAUDE.md: layer rule). Held as
    # a Pydantic PrivateAttr so it doesn't round-trip through model_dump_json.
    _graph_cache: "GameGraph | None" = PrivateAttr(default=None)

    def graph(self) -> "GameGraph":
        """Cached relational graph. Reuses the cached build until
        `invalidate_graph()` is called. Read-only callers can use this freely;
        callers that just mutated a relation field must invalidate first."""
        if self._graph_cache is None:
            from ..ontology.graph import build_graph

            self._graph_cache = build_graph(self)
        return self._graph_cache

    def invalidate_graph(self) -> None:
        """Drop the cached graph so the next `graph()` rebuilds. Call after
        any write that touches a relation field (location_id, inventory_ids,
        equipment, racial/learned_skill_ids, race_id, companions,
        quest.giver_id/triggers/rewards.items, location.connections/item_ids,
        chapter.quest_ids)."""
        self._graph_cache = None

    def recent_npc_id(self, actor_id: str) -> str | None:
        """Most recently addressed NPC at this location — anchors pronoun /
        follow-up inputs ('한 번만 더 말해봐', '그래서?') to the same NPC
        instead of letting the judge drift to a different same-location
        character. Returns None if no recent target exists or it isn't an
        alive same-location NPC."""
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

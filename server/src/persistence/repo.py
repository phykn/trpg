"""Persistence repository Protocols.

Two seams:
- `SaveRepo`: per-game runtime state (replaces file IO under `saves/games/<game_id>/`).
- `ScenarioRepo`: read-only seed data (replaces file IO under `scenarios/<profile>/`).

Adapters live in `local_fs.py` (dev) and `supabase.py` (release, Phase 2 stub).
`factory.py` picks one based on `APP_ENV`.
"""

from pathlib import Path
from typing import Protocol, Type, TypeVar

from pydantic import BaseModel

from ..domain.memory import DialoguePair, LogEntry, TurnLogEntry
from ..domain.state import GameState

T = TypeVar("T", bound=BaseModel)


class SaveRepo(Protocol):
    """Per-game runtime persistence. All writes go through this in flow/."""

    async def save_meta(self, state: GameState) -> None: ...

    async def save_entity(
        self, state: GameState, kind: str, entity_id: str
    ) -> None: ...

    async def append_log_entries(
        self, game_id: str, entries: list[LogEntry]
    ) -> None: ...

    async def append_history_entries(
        self, game_id: str, entries: list[TurnLogEntry]
    ) -> None: ...

    async def append_dialogue_entries(
        self, game_id: str, entries: list[DialoguePair]
    ) -> None: ...

    def load_game(self, game_id: str) -> GameState: ...

    def copy_seed_into_game(
        self, scenario_repo: "ScenarioRepo", profile: str, game_id: str
    ) -> None: ...


class ScenarioRepo(Protocol):
    """Read-only scenario seed access."""

    def profile_exists(self, profile: str) -> bool: ...

    def list_profiles(self) -> list[dict]: ...

    def read_world_md(self, profile: str, *, missing_ok: bool = False) -> str: ...

    def read_start_json(self, profile: str) -> dict: ...

    def read_player_template(self, profile: str) -> dict: ...

    def load_seed_entities(
        self, profile: str, kind: str, model_cls: Type[T]
    ) -> dict[str, T]: ...

    def local_profile_path(self, profile: str) -> Path:
        """Return a filesystem path to the profile dir.

        LocalFs returns the actual path. Supabase materializes seed to a temp
        dir lazily. Used by `engines/invariants.Scenario.from_dir` which needs
        a real filesystem tree to walk.
        """
        ...

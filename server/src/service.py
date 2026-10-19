"""One serialized command boundary: locks, revisions, receipts, and the order of a turn."""

import asyncio
import json
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import uuid4

from src.content.load import Loaded, new_game
from src.interpret import Clarify, Rejected, interpret
from src.locale import ko
from src.models.kev import KevClient, ModelUnavailable
from src.models.qwen import QwenClient
from src.narrate import Narrator
from src.rules.candidates import candidates
from src.rules.chapter import grow, growth_options
from src.rules.resolve import Impossible, resolve
from src.scene.build import approach_names
from src.scene.view import Button, GameView, confirm_card, game_view
from src.store import SaveStore
from src.world.state import (
    ActionStep,
    GameState,
    IncompatibleSave,
    Pending,
    Receipt,
    Step,
    TurnRecord,
)

RECEIPT_LIMIT = 50
BUTTON_KINDS = {"move", "inspect", "talk", "take", "give", "act", "solve", "use_tag", "topic"}


class Stale(ValueError):
    pass


@dataclass
class Outcome:
    kind: str
    view: GameView
    turn: int | None = None
    options: list[Button] = field(default_factory=list)
    reason: str = ""


class GameService:
    def __init__(self, stories: dict[str, Loaded], store: SaveStore, kev: KevClient, qwen: QwenClient,
                 ):
        self.stories = stories
        self.store = store
        self.kev = kev
        self.qwen = qwen
        self.narrator = Narrator(qwen, kev)
        self._narrating: dict[str, asyncio.Lock] = {}

    async def check_models(self) -> None:
        await self.kev.ping()
        await self.qwen.resolve_model()

    def catalog(self) -> list[dict]:
        return [
            {"id": sid, "title": s.story.title, "synopsis": s.story.synopsis,
             "creation": {"choose": s.story.creation.choose,
                          "approaches": [{"id": a, "name": n, "text": ko.APPROACH_HINT[a]}
                                         for a, n in approach_names(s.story).items()],
                          "traits": [t.model_dump() for t in s.story.traits]}}
            for sid, s in self.stories.items()
            if not s.folder.name.startswith("_")
        ]

    def _loaded(self, state: GameState) -> Loaded:
        loaded = self.stories.get(state.story_id)
        if loaded is None or loaded.story.version != state.story_version:
            raise IncompatibleSave("story version mismatch")
        return loaded

    def _view(self, state: GameState) -> GameView:
        return game_view(self._loaded(state).story, state)

    async def start(self, story_id: str, approaches: dict | None = None, traits: list[str] | None = None) -> GameView:
        if story_id not in self.stories:
            raise ValueError("unknown story")
        story = self.stories[story_id].story
        state = new_game(story, game_id=f"g_{uuid4().hex}", seed=secrets.randbits(63),
                         approaches=approaches, traits=traits)
        await self.store.save(state)
        return self._view(state)

    async def load(self, game_id: str) -> GameView:
        return self._view(await self.store.load(game_id))

    async def act(self, game_id: str, *, revision: int, request_id: str, text: str | None = None,
                  action_id: str | None = None, confirm: str | None = None, accept: bool = True) -> Outcome:
        fingerprint = json.dumps([text, action_id, confirm, accept, revision], ensure_ascii=False)
        async with self.store.lock(game_id):
            state = await self.store.load(game_id)
            story = self._loaded(state).story
            receipt = state.receipts.get(request_id)
            if receipt is not None:
                if receipt.fingerprint != fingerprint:
                    raise Stale("request id reused with different content")
                return Outcome(kind=receipt.kind, view=self._view(state), turn=receipt.turn)
            if revision != state.revision:
                raise Stale("revision mismatch")
            if state.ending is not None:
                raise ValueError("the game has ended")
            pending = state.pending
            if pending is not None and pending.kind == "growth":
                return await self._grow(state, action_id or "", request_id, fingerprint)
            if confirm is not None:
                if pending is None or pending.id != confirm:
                    raise Stale("no such confirmation")
                if not accept:
                    state.pending = None
                    state.revision += 1
                    return await self._commit(state, request_id, fingerprint, "cancelled", None)
                return await self._run(story, state, pending.steps, pending.input, request_id, fingerprint)
            if action_id is not None:
                cand = candidates(story, state).get(action_id)
                if cand is None or not cand.enabled or cand.kind not in BUTTON_KINDS:
                    raise ValueError("action is not available")
                steps: list[Step] = [ActionStep(action_id=action_id)]
                said = cand.label
            else:
                said = (text or "").strip()
                result = await interpret(self.kev, story, state, said, self.qwen)
                if isinstance(result, Rejected):
                    return Outcome(kind="rejected", view=self._view(state), reason=result.reason)
                if isinstance(result, Clarify):
                    options = [Button(id=k, label=label) for k, label in result.options]
                    return Outcome(kind="clarify", view=self._view(state), options=options)
                steps = list(result.steps)
            card_id = f"c{state.turn + 1}_{uuid4().hex[:8]}"
            if confirm_card(story, state, steps, card_id) is not None:
                state.pending = Pending(id=card_id, kind="confirm", steps=steps, input=said)
                state.revision += 1
                return await self._commit(state, request_id, fingerprint, "confirm", None)
            return await self._run(story, state, steps, said, request_id, fingerprint)

    async def _run(self, story, state: GameState, steps: list[Step], said: str, request_id: str,
                   fingerprint: str) -> Outcome:
        try:
            new, record = resolve(story, state, steps, said)
        except Impossible:
            return Outcome(kind="rejected", view=self._view(state), reason=ko.WHY_NOT["absent"])
        new.turns.append(record)
        return await self._commit(new, request_id, fingerprint, "turn", record.n)

    async def _grow(self, state: GameState, option: str, request_id: str, fingerprint: str) -> Outcome:
        story = self._loaded(state).story
        label = growth_options(story, state).get(option)
        if label is None:
            raise ValueError("choose a growth option first")
        new = state.model_copy(deep=True)
        new.turn += 1
        new.revision += 1
        new.turns.append(TurnRecord(n=new.turn, input=label, changes=grow(story, new, option)))
        return await self._commit(new, request_id, fingerprint, "turn", new.turn)

    async def _commit(self, state: GameState, request_id: str, fingerprint: str, kind: str,
                      turn: int | None) -> Outcome:
        state.receipts[request_id] = Receipt(fingerprint=fingerprint, kind=kind, turn=turn)
        state.receipts = dict(list(state.receipts.items())[-RECEIPT_LIMIT:])
        await self.store.save(state)
        return Outcome(kind=kind, view=self._view(state), turn=turn)

    async def narration(self, game_id: str, n: int) -> AsyncIterator[dict]:
        lock = self._narrating.setdefault(game_id, asyncio.Lock())
        async with lock:
            state = await self.store.load(game_id)
            loaded = self._loaded(state)
            record = next((r for r in state.turns if r.n == n), None)
            if record is not None and record.narration:
                yield {"type": "done", "text": record.narration, "tags": record.tag_names}
                return
            if record is None or n != state.turn:
                yield {"type": "error", "retry": False}
                return
            try:
                async for event in self.narrator.narrate(loaded.story, loaded.style, state, record):
                    if event["type"] == "done":
                        await self._save_narration(game_id, n, event["text"], event["tags"])
                    yield event
            except ModelUnavailable:
                yield {"type": "error", "retry": True}

    async def _save_narration(self, game_id: str, n: int, text: str, names: dict[str, str]) -> None:
        async with self.store.lock(game_id):
            state = await self.store.load(game_id)
            record = next(r for r in state.turns if r.n == n)
            record.narration, record.tag_names = text, names
            for tag in [t for ts in state.tags.values() for t in ts] + state.traces:
                if tag.id in names and not tag.name:
                    tag.name = names[tag.id]
            await self.store.save(state)

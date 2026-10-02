"""One serialized and atomic command boundary for authored adventures."""

import secrets
from uuid import uuid4

from src.game.engine import choose, new_game
from src.game.models import IncompatibleSave, Receipt, Story
from src.store import SaveStore
from src.view import game_view


class StaleChoice(ValueError):
    pass


class GameService:
    def __init__(self, story: Story, store: SaveStore):
        self.story = story
        self.store = store

    async def start(self, name: str, role: str):
        state = new_game(self.story, name, role, seed=secrets.randbits(64))
        state.game_id = f"adv_{uuid4().hex}"
        view = game_view(self.story, state)
        await self.store.save(state)
        return view

    async def load(self, game_id: str):
        state = await self.store.load(game_id)
        self._check_version(state)
        return game_view(self.story, state)

    async def act(self, game_id: str, option_id: str, revision: int, request_id: str):
        async with self.store.lock(game_id):
            state = await self.store.load(game_id)
            self._check_version(state)
            receipt = state.receipts.get(request_id)
            if receipt:
                if receipt.action != option_id or receipt.revision != revision:
                    raise StaleChoice("request id reused with different content")
                return game_view(self.story, state)
            if revision != state.revision:
                raise StaleChoice("revision mismatch")
            state = choose(self.story, state, option_id)
            state.receipts[request_id] = Receipt(action=option_id, revision=revision)
            view = game_view(self.story, state)
            await self.store.save(state)
            return view

    def _check_version(self, state):
        if (
            state.profile != self.story.id
            or state.content_version != self.story.version
        ):
            raise IncompatibleSave("content version mismatch")

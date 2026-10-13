import asyncio
from pathlib import Path
from threading import Event

import pytest
from src import store
from src.content import load_story
from src.game.engine import new_game


@pytest.mark.asyncio
async def test_repeated_cancellation_holds_command_lock_until_write_finishes(
    tmp_path, monkeypatch
):
    story = load_story(
        Path(__file__).resolve().parents[2] / "scenarios/harbor/adventure.json"
    )
    state = new_game(story, "Tester", "listener", seed=7)
    state.game_id = "adv_" + "a" * 32
    saves = store.SaveStore(tmp_path)
    entered = asyncio.Event()
    finished = asyncio.Event()
    released = Event()
    loop = asyncio.get_running_loop()
    atomic_write = store._atomic_write

    def delayed_write(path, data):
        loop.call_soon_threadsafe(entered.set)
        if not released.wait(timeout=60):
            raise RuntimeError("test did not release the write")
        try:
            atomic_write(path, data)
        finally:
            loop.call_soon_threadsafe(finished.set)

    monkeypatch.setattr(store, "_atomic_write", delayed_write)

    async def command():
        async with saves.lock(state.game_id):
            await saves.save(state)

    task = asyncio.create_task(command())
    try:
        await asyncio.wait_for(entered.wait(), timeout=60)
        task.cancel()
        for _ in range(4):
            await asyncio.sleep(0)
        task.cancel()
        for _ in range(4):
            await asyncio.sleep(0)
        assert saves.lock(state.game_id).locked()
        assert not task.done()
    finally:
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(finished.wait(), timeout=60)
    assert not saves.lock(state.game_id).locked()
    assert await saves.load(state.game_id) == state

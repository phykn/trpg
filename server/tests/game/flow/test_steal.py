"""Steal flow — run_steal builds pending_check; handle_steal_roll_result
applies success (random item transfer) or failure (relations drop)."""

import random

from src.db.local_fs import LocalFsSaveRepo
from src.game.domain.entities import Character, Item, Location, Stats, WeaponEffect
from src.game.domain.memory import PendingCheck
from src.game.flow.dirty import Dirty
from src.game.flow.steal import handle_steal_roll_result, run_steal


def _seed(fresh_state, *, npc_inventory: list[str]):
    fresh_state.player_id = "player_01"
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    player = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(STR=10, DEX=14, CON=10, INT=10, WIS=10, CHA=10),
        level=1,
        hp=20,
        max_hp=20,
        location_id="plaza_01",
    )
    npc = Character(
        id="npc_01",
        name="상인",
        race_id="human",
        stats=Stats(),
        hp=15,
        max_hp=15,
        location_id="plaza_01",
        inventory_ids=list(npc_inventory),
    )
    fresh_state.characters["player_01"] = player
    fresh_state.characters["npc_01"] = npc
    for iid in npc_inventory:
        fresh_state.items[iid] = Item(id=iid, name=f"{iid}-name")
    return fresh_state


async def _drain(gen):
    out = []
    async for ev in gen:
        out.append(ev)
    return out


async def test_run_steal_sets_pending_check(fresh_state, tmp_path):
    state = _seed(fresh_state, npc_inventory=["coin_01"])
    repo = LocalFsSaveRepo(tmp_path)
    dirty = Dirty()

    events = await _drain(
        run_steal(state, repo, "지갑을 슬쩍한다", "npc_01", dirty, to_front_fn=None)
    )

    assert state.pending_check is not None
    assert state.pending_check.kind == "steal"
    assert state.pending_check.stat == "DEX"
    assert state.pending_check.target == "npc_01"
    # SSE event for pending_check emitted
    assert any(e.get("type") == "pending_check" for e in events)


async def test_run_steal_no_carryables_emits_card_no_pending(fresh_state, tmp_path):
    """Defensive: semantic check should reject empty-carryables before run_steal,
    but if it slips through (e.g. equipped-only inventory), surface a card and
    don't burn a pending_check."""
    state = _seed(fresh_state, npc_inventory=[])
    repo = LocalFsSaveRepo(tmp_path)
    dirty = Dirty()

    events = await _drain(
        run_steal(state, repo, "훔친다", "npc_01", dirty, to_front_fn=None)
    )

    assert state.pending_check is None
    # one act log entry with the no-carryables text
    act_evts = [e for e in events if e.get("type") == "log_entry"]
    assert len(act_evts) == 1
    assert "훔칠 만한 것이 없" in act_evts[0]["data"]["text"]


async def test_handle_steal_roll_success_transfers_random_item(fresh_state):
    state = _seed(fresh_state, npc_inventory=["coin_01"])
    pending = PendingCheck(
        player_input="훔친다",
        kind="steal",
        tier="normal",
        stat="DEX",
        target="npc_01",
        targets=["npc_01"],
        dc=10,
        mod=0,
        required_roll=8,
        reason="훔치기",
        created_at="2026-05-06T00:00:00Z",
    )
    dirty = Dirty()
    rng = random.Random(0)

    await _drain(
        handle_steal_roll_result(state, pending, "success", dirty, rng=rng)
    )

    assert "coin_01" in state.characters["player_01"].inventory_ids
    assert "coin_01" not in state.characters["npc_01"].inventory_ids
    assert ("characters", "player_01") in dirty.entities
    assert ("characters", "npc_01") in dirty.entities


async def test_handle_steal_roll_failure_drops_relations(fresh_state):
    state = _seed(fresh_state, npc_inventory=["coin_01"])
    pending = PendingCheck(
        player_input="훔친다",
        kind="steal",
        tier="normal",
        stat="DEX",
        target="npc_01",
        targets=["npc_01"],
        dc=10,
        mod=0,
        required_roll=8,
        reason="훔치기",
        created_at="2026-05-06T00:00:00Z",
    )
    dirty = Dirty()

    await _drain(
        handle_steal_roll_result(state, pending, "failure", dirty)
    )

    # item stayed with NPC
    assert "coin_01" in state.characters["npc_01"].inventory_ids
    assert "coin_01" not in state.characters["player_01"].inventory_ids
    # relations dropped on the target side (target.relations[player])
    assert state.characters["npc_01"].relations.get("player_01", 0) < 0


async def test_handle_steal_roll_critical_failure_same_drop(fresh_state):
    state = _seed(fresh_state, npc_inventory=["coin_01"])
    pending = PendingCheck(
        player_input="훔친다", kind="steal", tier="normal", stat="DEX",
        target="npc_01", targets=["npc_01"],
        dc=10, mod=0, required_roll=8,
        reason="훔치기", created_at="2026-05-06T00:00:00Z",
    )
    dirty = Dirty()

    await _drain(
        handle_steal_roll_result(state, pending, "critical_failure", dirty)
    )
    # No transfer
    assert "coin_01" in state.characters["npc_01"].inventory_ids
    assert state.characters["npc_01"].relations.get("player_01", 0) < 0


async def test_handle_steal_roll_skips_equipped_items(fresh_state):
    """Equipped items aren't stealable — engine should pick from non-equipped only."""
    state = _seed(fresh_state, npc_inventory=["sword_01", "coin_01"])
    # Mark sword as equipped on the NPC.
    sword = state.items["sword_01"]
    sword.effects = WeaponEffect(type="weapon", weapon_dice="1d6")
    state.characters["npc_01"].equipment.weapon = "sword_01"
    state.invalidate_graph()
    pending = PendingCheck(
        player_input="훔친다", kind="steal", tier="normal", stat="DEX",
        target="npc_01", targets=["npc_01"],
        dc=10, mod=0, required_roll=8,
        reason="훔치기", created_at="2026-05-06T00:00:00Z",
    )
    dirty = Dirty()
    # Force any rng outcome — only non-equipped item is "coin_01".
    rng = random.Random(0)
    await _drain(handle_steal_roll_result(state, pending, "success", dirty, rng=rng))
    # Equipped sword still on NPC; coin transferred.
    assert "sword_01" in state.characters["npc_01"].inventory_ids
    assert state.characters["npc_01"].equipment.weapon == "sword_01"
    assert "coin_01" in state.characters["player_01"].inventory_ids

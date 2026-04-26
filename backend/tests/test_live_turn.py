import os
import random
import tempfile
from pathlib import Path

import pytest

from src.domain.entities import (
    Character,
    CombatBehavior,
    Location,
    Race,
    Stats,
)
from src.errors import PendingCheckActive, PendingCheckExpected
from src.llm_client.client import LLMClient
from src.pipeline.turn import run_roll, run_turn
from src.state.models import GameState

pytestmark = pytest.mark.live


@pytest.fixture
def client():
    base_url = os.environ.get("BASE_URL", "http://localhost:8000/v1")
    return LLMClient(base_url=base_url, model="local")


@pytest.fixture
def env():
    with tempfile.TemporaryDirectory() as tmp:
        profile_dir = Path(tmp) / "profiles"
        saves_dir = Path(tmp) / "saves"
        pdir = profile_dir / "default"
        pdir.mkdir(parents=True)
        (pdir / "world.md").write_text("중세 판타지", encoding="utf-8")
        gs = GameState(
            game_id="t",
            profile="default",
            player_id="player_01",
            world_time="0812-04-28T14:00:00",
        )
        gs.races["human"] = Race(id="human", name="인간", description="x")
        gs.locations["plaza_01"] = Location(id="plaza_01", name="광장")
        gs.characters["player_01"] = Character(
            id="player_01",
            name="주",
            race_id="human",
            stats=Stats(),
            location_id="plaza_01",
            hp=20,
            max_hp=20,
            mp=15,
            max_mp=15,
        )
        gs.characters["guard_01"] = Character(
            id="guard_01",
            name="경비병",
            race_id="human",
            stats=Stats(),
            location_id="plaza_01",
            appearance="갑옷",
            tone_hint="격식체",
        )
        yield gs, str(profile_dir), str(saves_dir)


async def _collect_events(gen):
    return [e async for e in gen]


async def test_pass_branch_full_flow(client, env):
    gs, profile_dir, saves_dir = env
    events = await _collect_events(
        run_turn(
            client,
            gs,
            profile_dir,
            saves_dir,
            "주변을 둘러본다.",
        )
    )
    types = [e["type"] for e in events]
    assert types[0] == "log_entry"  # player input
    assert "judge" in types
    assert "narrative_delta" in types
    assert types[-1] == "done"
    assert gs.turn_count == 1
    assert gs.pending_check is None


async def test_roll_branch_pauses_then_resumes(client, env):
    gs, profile_dir, saves_dir = env
    events = await _collect_events(
        run_turn(
            client,
            gs,
            profile_dir,
            saves_dir,
            "경비병에게 동전을 쥐여주며 통과시켜달라고 한다.",
        )
    )
    assert events[-1]["type"] == "pending_check"
    assert gs.pending_check is not None

    # /turn is blocked while a pending_check is active.
    with pytest.raises(PendingCheckActive):
        async for _ in run_turn(client, gs, profile_dir, saves_dir, "..."):
            pass

    # Resolve via /roll.
    roll_events = await _collect_events(
        run_roll(
            client,
            gs,
            profile_dir,
            saves_dir,
            rng=random.Random(7),
        )
    )
    assert roll_events[0]["type"] == "log_entry"  # roll log
    assert roll_events[-1]["type"] == "done"
    assert gs.pending_check is None
    # turn_count bumps in /roll, not /turn (roll branch leaves it untouched).
    assert gs.turn_count == 1


async def test_roll_without_pending_blocked(client, env):
    gs, profile_dir, saves_dir = env
    with pytest.raises(PendingCheckExpected):
        async for _ in run_roll(client, gs, profile_dir, saves_dir):
            pass


async def test_rest_branch_classified_by_judge(client, env):
    """판정자가 '잠을 잔다' 를 'rest' 로 분류 → 회복 분기 진입, HP/MP 풀회복."""
    gs, profile_dir, saves_dir = env
    # 광장은 default safe — 풀회복 보장.
    player = gs.characters["player_01"]
    player.hp = 4
    player.mp = 2

    events = await _collect_events(
        run_turn(
            client,
            gs,
            profile_dir,
            saves_dir,
            "여기서 잠을 청한다.",
            rng=random.Random(1),
        )
    )
    types = [e["type"] for e in events]
    judge_event = next(e for e in events if e["type"] == "judge")
    assert judge_event["data"]["action"] == "rest"
    assert types[-1] == "done"
    assert player.hp == player.max_hp
    assert player.mp == player.max_mp


async def test_judge_matches_equip_for_weapon_in_inventory(client, env):
    """판정자가 inventory.kind=weapon 아이템 입력을 equip 으로 분류."""
    from src.domain.entities import Item, WeaponEffect

    gs, profile_dir, saves_dir = env
    gs.items["sword_01"] = Item(
        id="sword_01",
        name="강철 장검",
        effects=WeaponEffect(type="weapon", weapon_dice="1d8"),
    )
    gs.characters["player_01"].inventory_ids = ["sword_01"]

    events = await _collect_events(
        run_turn(
            client,
            gs,
            profile_dir,
            saves_dir,
            "강철 장검을 손에 든다.",
            rng=random.Random(0),
        )
    )
    judge_event = next(e for e in events if e["type"] == "judge")
    assert judge_event["data"]["action"] == "equip"
    assert judge_event["data"]["item_id"] == "sword_01"


async def test_judge_matches_use_for_inventory_item(client, env):
    """판정자가 inventory 컨텍스트로 받아 자연어를 use 로 분류, item_id 박는지."""
    from src.domain.entities import ConsumableEffect, Item

    gs, profile_dir, saves_dir = env
    gs.items["herb_01"] = Item(
        id="herb_01",
        name="치유 약초",
        consumable=True,
        effects=ConsumableEffect(type="consumable", effect="heal", amount=8),
    )
    gs.characters["player_01"].inventory_ids = ["herb_01"]
    gs.characters["player_01"].hp = 10  # 상처난 상태

    events = await _collect_events(
        run_turn(
            client,
            gs,
            profile_dir,
            saves_dir,
            "약초를 먹어 상처를 치유한다.",
            rng=random.Random(0),
        )
    )
    judge_event = next(e for e in events if e["type"] == "judge")
    assert judge_event["data"]["action"] == "use"
    assert judge_event["data"]["item_id"] == "herb_01"


async def test_judge_matches_learned_skill_in_combat(client, env):
    """판정자가 learned_skills 컨텍스트로 받아 combat 입력에 skill_id 박는지 확인."""
    from src.domain.entities import Race, Skill

    gs, profile_dir, saves_dir = env
    gs.races["goblin"] = Race(id="goblin", name="고블린", description="x")
    gs.characters["goblin_01"] = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(),
        hp=12,
        max_hp=12,
        appearance="작은 체구",
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )
    gs.characters["player_01"].learned_skills = [
        Skill(
            id="fireball",
            name="화염구",
            description="불꽃을 모아 한 번에 던지는 공격 마법",
            type="attack",
            target="single",
            primary_stat="INT",
            power=12,
            mp_cost=4,
            level=0,
        )
    ]

    events = await _collect_events(
        run_turn(
            client,
            gs,
            profile_dir,
            saves_dir,
            "고블린에게 화염구를 던진다.",
            rng=random.Random(0),
        )
    )
    judge_event = next(e for e in events if e["type"] == "judge")
    assert judge_event["data"]["action"] == "combat"
    # skill_id 가 박혔어야
    assert judge_event["data"].get("skill_id") == "fireball"


async def test_combat_branch_boots_combat_state(client, env):
    """판정자가 'combat' 으로 분류 → 엔진이 combat_state 부팅 + combat_start SSE 발행."""
    gs, profile_dir, saves_dir = env
    gs.races["goblin"] = Race(id="goblin", name="고블린", description="x")
    gs.characters["goblin_01"] = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(STR=8, DEX=14, CON=10, INT=8, WIS=8, CHA=6),
        hp=12,
        max_hp=12,
        appearance="작은 체구의 고블린",
        tone_hint="쉭쉭거림",
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )

    events = await _collect_events(
        run_turn(
            client,
            gs,
            profile_dir,
            saves_dir,
            "고블린에게 칼을 휘둘러 공격한다.",
            rng=random.Random(42),
        )
    )
    types = [e["type"] for e in events]
    judge_event = next(e for e in events if e["type"] == "judge")
    # judge LLM 이 의도대로 combat 으로 분류해야 P2 라이프사이클 진입.
    assert judge_event["data"]["action"] == "combat"
    assert "combat_start" in types
    cs_data = next(e["data"] for e in events if e["type"] == "combat_start")
    assert "goblin_01" in cs_data["enemy_ids"]
    assert types[-1] == "done"

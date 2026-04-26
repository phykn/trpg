"""§2.4 폴백 — sleep_encounters 풀 비었을 때 LLM 즉석 적 생성. agent mock."""
import tempfile
from pathlib import Path

import pytest

from src.domain.entities import Character, Location, Race, Stats
from src.agents import encounter_summon as agent_mod
from src.agents.encounter_summon import (
    EncounterStats,
    EncounterSummonOutput,
)
from src.flow import encounter as encounter_engine
from src.engines import recovery


@pytest.fixture
def tmp_profile():
    with tempfile.TemporaryDirectory() as d:
        pdir = Path(d) / "default"
        pdir.mkdir()
        (pdir / "world.md").write_text("중세 판타지", encoding="utf-8")
        yield d


def _seed_state(fresh_state):
    fresh_state.profile = "default"
    fresh_state.player_id = "player_01"
    fresh_state.races["wolf"] = Race(id="wolf", name="늑대", description="x")
    fresh_state.races["human"] = Race(id="human", name="인간", description="x")
    fresh_state.locations["forest_01"] = Location(
        id="forest_01", name="외진 숲길", sleep_risk="dangerous", sleep_encounters=[]
    )
    fresh_state.characters["player_01"] = Character(
        id="player_01", name="주", race_id="human", is_player=True,
        stats=Stats(), location_id="forest_01", level=2,
        hp=20, max_hp=20, mp=15, max_mp=15,
    )
    return fresh_state


def _patch_agent(monkeypatch, output: EncounterSummonOutput):
    async def fake_summon(client, input_, retries=5):
        return output
    monkeypatch.setattr(
        encounter_engine, "encounter_summon", fake_summon
    )
    monkeypatch.setattr(agent_mod, "encounter_summon", fake_summon)


_VALID_OUTPUT = EncounterSummonOutput(
    name="회색 늑대",
    description="굶주려 외톨이가 된 늑대",
    appearance="회색 털, 누런 송곳니",
    tone_hint="으르렁",
    race_id="wolf",
    stats=EncounterStats(STR=12, DEX=14, CON=11, INT=9, WIS=6, CHA=8),
    attack_priority="nearest",
)


# --- agent output → Character ---------------------------------------------


async def test_summon_registers_character_with_pair_trade(fresh_state, tmp_profile, monkeypatch):
    state = _seed_state(fresh_state)
    _patch_agent(monkeypatch, _VALID_OUTPUT)

    char = await encounter_engine.summon_encounter(
        client=None, state=state,
        location=state.locations["forest_01"],
        profile_dir=tmp_profile, profile="default",
    )
    assert char is not None
    assert char.id in state.characters
    assert char.location_id == "forest_01"
    assert char.race_id == "wolf"
    # pair-trade 확인
    s = char.stats
    assert s.STR + s.CHA == 20
    assert s.DEX + s.WIS == 20
    assert s.CON + s.INT == 20
    # HP/MP 가 max 로 부팅
    assert char.hp == char.max_hp
    assert char.mp == char.max_mp


async def test_summon_unknown_race_returns_none(fresh_state, tmp_profile, monkeypatch):
    state = _seed_state(fresh_state)
    bad = EncounterSummonOutput(
        name="유령", description="x", appearance="x", race_id="ghost",
        stats=EncounterStats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
    )
    _patch_agent(monkeypatch, bad)

    char = await encounter_engine.summon_encounter(
        client=None, state=state,
        location=state.locations["forest_01"],
        profile_dir=tmp_profile, profile="default",
    )
    assert char is None


# --- recovery + summon 통합 ------------------------------------------------


async def test_recovery_uses_summon_when_pool_empty(fresh_state, tmp_profile, monkeypatch):
    """sleep_encounters 비었지만 summon 콜백 → encounter."""
    state = _seed_state(fresh_state)

    async def summon(s, loc_id):
        char = Character(
            id="summoned_01", name="늑대", race_id="wolf",
            stats=Stats(STR=12, DEX=14, CON=11, INT=9, WIS=6, CHA=8),
            location_id=loc_id, hp=8, max_hp=8,
        )
        s.characters[char.id] = char
        return char.id

    class _AlwaysEncounter:
        def random(self):
            return 0.0  # encounter_chance > 0 이면 무조건 발동

    outcome, enemies = await recovery.attempt_rest(
        state, "player_01", rng=_AlwaysEncounter(), dirty=set(), summon=summon
    )
    assert outcome == "encounter"
    assert enemies == ["summoned_01"]
    assert "summoned_01" in state.characters


async def test_recovery_falls_back_when_summon_fails(fresh_state, tmp_profile, monkeypatch):
    """summon 이 None 반환 → 풀회복 폴백."""
    state = _seed_state(fresh_state)

    async def summon(s, loc_id):
        return None

    class _AlwaysEncounter:
        def random(self):
            return 0.0

    outcome, enemies = await recovery.attempt_rest(
        state, "player_01", rng=_AlwaysEncounter(), dirty=set(), summon=summon
    )
    assert outcome == "full_recovery"
    assert enemies == []
    p = state.characters["player_01"]
    assert p.hp == p.max_hp

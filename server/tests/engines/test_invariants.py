"""Invariant checks — single dispatcher (check.X), list[str] returns."""

from src.domain.entities import (
    ArmorEffect,
    Chapter,
    Character,
    CombatBehavior,
    ConsumableEffect,
    Disposition,
    Equipment,
    Item,
    Quest,
    QuestTrigger,
    Race,
    Skill,
    Stats,
    WeaponEffect,
)
from src.engines.growth import calc_max_hp, calc_max_mp
from src.engines.invariants import (
    Scenario,
    check_chapter_graph,
    check_character,
    check_inventory,
    check_item,
    check_quest_graph,
    check_scenario,
    check_skills,
    check_stats,
)


def _char(
    cid: str = "c1",
    *,
    is_player: bool = False,
    level: int = 1,
    stats: Stats | None = None,
    inventory: list[str] | None = None,
    equipment: Equipment | None = None,
    skills: list[Skill] | None = None,
    aggressive: int = 50,
    combat: CombatBehavior | None = None,
    location_id: str | None = None,
    race_id: str = "human",
    xp_reward: int = 0,
) -> Character:
    s = stats or Stats()
    c = Character(
        id=cid,
        name=cid,
        is_player=is_player,
        level=level,
        race_id=race_id,
        stats=s,
        location_id=location_id,
        equipment=equipment or Equipment(),
        inventory_ids=inventory or [],
        learned_skill_ids=[sk.id for sk in (skills or [])],
        disposition=Disposition(aggressive=aggressive),
        combat_behavior=combat,
        xp_reward=xp_reward,
    )
    c.max_hp = calc_max_hp(level, s.CON)
    c.max_mp = calc_max_mp(level, s.INT)
    c.hp = c.max_hp
    c.mp = c.max_mp
    return c


def _skill_pool(*skills: Skill) -> dict[str, Skill]:
    return {s.id: s for s in skills}


def _basic_skill(sid: str = "skl", **kw) -> Skill:
    base = dict(
        id=sid,
        name=sid,
        type="attack",
        target="single",
        primary_stat="STR",
        power=5,
        mp_cost=0,
        level=1,
        duration=0,
    )
    base.update(kw)
    return Skill(**base)


# --- check_stats ----------------------------------------------------------


def test_stats_default_passes():
    assert check_stats(Stats()) == []


def test_stats_pair_trade_violations():
    bad = Stats(STR=12, CHA=5, DEX=10, WIS=10, CON=10, INT=10)
    msgs = check_stats(bad)
    assert len(msgs) == 1
    assert "STR+CHA" in msgs[0] and "17" in msgs[0]


def test_stats_three_pair_violations():
    bad = Stats(STR=12, CHA=5, DEX=12, WIS=12, CON=12, INT=12)
    msgs = check_stats(bad)
    assert len(msgs) == 3


# --- check_character (stateless) ------------------------------------------


def test_character_default_passes():
    assert check_character(_char(level=0)) == []


def test_character_max_hp_off_formula():
    c = _char(level=1, stats=Stats(CON=14))
    c.max_hp = 999
    msgs = check_character(c)
    assert any("max_hp" in m and "999" in m for m in msgs)


def test_character_alive_false_with_positive_hp():
    c = _char()
    c.alive = False
    c.hp = 10
    msgs = check_character(c)
    assert any("alive=False" in m for m in msgs)


def test_seed_dead_character_passes_full_pool_rule():
    """alive=False seed corpses (e.g. quest backstory: 'found dead in the cave')
    must seed with hp/mp=0; the seed-only full-pool rule applies only to living
    NPCs. Otherwise the writer can't represent characters who start dead."""
    from src.engines.invariants import check_seed_character

    c = _char(skills=[_basic_skill()])
    c.alive = False
    c.hp = 0
    c.mp = 0
    msgs = check_seed_character(
        c, items_pool={}, skills_pool=_skill_pool(_basic_skill())
    )
    assert not any("seed hp" in m or "seed mp" in m for m in msgs)


def test_seed_living_character_with_low_hp_still_flagged():
    """Living NPCs must still seed at full hp/mp — relaxation only covers alive=False."""
    from src.engines.invariants import check_seed_character

    c = _char(skills=[_basic_skill()])
    c.hp = c.max_hp - 1  # alive=True (default), but hp not full
    msgs = check_seed_character(
        c, items_pool={}, skills_pool=_skill_pool(_basic_skill())
    )
    assert any("seed hp" in m for m in msgs)


def test_character_skill_level_above_owner_level():
    skill = _basic_skill(level=5)
    c = _char(level=2, skills=[skill])
    msgs = check_skills(c, _skill_pool(skill))
    assert any("level=5" in m and "level=2" in m for m in msgs)


def test_character_duplicate_skill_id():
    skill1 = _basic_skill("a")
    c = _char(skills=[skill1])
    c.learned_skill_ids.append("a")  # duplicate id
    msgs = check_character(c)
    assert any("duplicated" in m for m in msgs)


def test_character_inventory_duplicate():
    c = _char(inventory=["sword", "sword"])
    msgs = check_character(c)
    assert any("inventory_ids" in m and "duplicated" in m for m in msgs)


def test_character_equipment_not_in_inventory():
    c = _char(inventory=[], equipment=Equipment(weapon="sword"))
    msgs = check_character(c)
    assert any("weapon" in m and "sword" in m and "not in inventory" in m for m in msgs)


def test_character_negative_gold():
    c = _char()
    c.gold = -1
    msgs = check_character(c)
    assert any("gold=-1" in m for m in msgs)


# --- check_item -----------------------------------------------------------


def test_item_default_passes():
    assert check_item(Item(id="i", name="i")) == []


def test_item_negative_weight():
    msgs = check_item(Item(id="i", name="i", weight=-1.0))
    assert any("weight=-1" in m for m in msgs)


def test_item_weapon_dice_invalid():
    weapon = Item(
        id="i",
        name="i",
        effects=WeaponEffect(type="weapon", weapon_dice="oops"),
    )
    msgs = check_item(weapon)
    assert any("weapon_dice" in m and "oops" in m for m in msgs)


def test_item_weapon_dice_valid_forms():
    for spec in ("1d6", "2d4", "1d8+2", "1d4-1", " 2d10 + 3 "):
        weapon = Item(
            id="i",
            name="i",
            effects=WeaponEffect(type="weapon", weapon_dice=spec),
        )
        assert check_item(weapon) == [], f"failed for {spec!r}"


def test_item_armor_negative_defense():
    armor = Item(id="a", name="a", effects=ArmorEffect(type="armor", defense=-1))
    msgs = check_item(armor)
    assert any("defense=-1" in m for m in msgs)


# --- check_inventory ------------------------------------------------------


def test_inventory_armor_in_weapon_slot():
    armor = Item(id="hat", name="hat", effects=ArmorEffect(type="armor", defense=2))
    c = _char(inventory=["hat"], equipment=Equipment(weapon="hat"))
    msgs = check_inventory(c, {"hat": armor})
    assert any("defense item" in m for m in msgs)


def test_inventory_armor_in_accessory_slot_passes():
    armor = Item(id="ring", name="ring", effects=ArmorEffect(type="armor", defense=1))
    c = _char(inventory=["ring"], equipment=Equipment(accessory="ring"))
    assert check_inventory(c, {"ring": armor}) == []


def test_inventory_weapon_in_armor_slot():
    sword = Item(
        id="sw", name="sw", effects=WeaponEffect(type="weapon", weapon_dice="1d6")
    )
    c = _char(inventory=["sw"], equipment=Equipment(armor="sw"))
    msgs = check_inventory(c, {"sw": sword})
    assert any("weapon" in m and "weapon slot" in m for m in msgs)


def test_inventory_consumable_equipped():
    potion = Item(
        id="p",
        name="p",
        effects=ConsumableEffect(type="consumable", effect="heal", amount=10),
    )
    c = _char(inventory=["p"], equipment=Equipment(weapon="p"))
    msgs = check_inventory(c, {"p": potion})
    assert any("consumable" in m and "cannot be equipped" in m for m in msgs)


def test_inventory_required_stat_not_met():
    heavy = Item(
        id="h",
        name="h",
        effects=WeaponEffect(type="weapon", weapon_dice="1d8"),
        required=Stats(STR=18),
    )
    c = _char(
        stats=Stats(STR=10, CHA=10), inventory=["h"], equipment=Equipment(weapon="h")
    )
    msgs = check_inventory(c, {"h": heavy})
    assert any("STR≥18" in m and "STR=10" in m for m in msgs)


def test_inventory_carry_capacity_exceeded():
    big = Item(id="big", name="big", weight=200.0)
    c = _char(stats=Stats(STR=10), inventory=["big"])
    msgs = check_inventory(c, {"big": big})
    assert any("carry capacity" in m for m in msgs)


def test_inventory_id_not_in_pool():
    c = _char(inventory=["ghost"])
    msgs = check_inventory(c, {})
    assert any(
        "inventory_ids" in m and "ghost" in m and "not in items" in m for m in msgs
    )


# --- check_skills ---------------------------------------------------------


def test_skills_attack_with_duration():
    skill = _basic_skill(type="attack", duration=3)
    c = _char(skills=[skill])
    msgs = check_skills(c, _skill_pool(skill))
    assert any("type='attack'" in m and "got 3" in m for m in msgs)


def test_skills_buff_with_zero_duration():
    skill = _basic_skill(type="buff", duration=0)
    c = _char(skills=[skill])
    msgs = check_skills(c, _skill_pool(skill))
    assert any("type='buff'" in m and "got 0" in m for m in msgs)


def test_skills_buff_with_positive_duration_passes():
    skill = _basic_skill(type="buff", duration=3)
    c = _char(skills=[skill])
    assert check_skills(c, _skill_pool(skill)) == []


# --- check_quest_graph ----------------------------------------------------


def _quest(qid: str, status: str = "active", prereq: list[str] | None = None) -> Quest:
    return Quest(
        id=qid,
        title=qid,
        giver_id="anyone",
        difficulty="보통",
        prerequisite_ids=prereq or [],
        status=status,
    )


def test_quest_graph_active_with_uncompleted_prereq():
    s = Scenario(
        quests={
            "a": _quest("a", "active"),
            "b": _quest("b", "active", prereq=["a"]),
        }
    )
    msgs = check_quest_graph(s)
    assert any("status='active'" in m and "'a'" in m for m in msgs)


def test_quest_graph_cycle():
    s = Scenario(
        quests={
            "a": _quest("a", "locked", prereq=["b"]),
            "b": _quest("b", "locked", prereq=["a"]),
        }
    )
    msgs = check_quest_graph(s)
    assert any("cycle" in m for m in msgs)


def test_quest_graph_active_with_completed_prereq_passes():
    s = Scenario(
        quests={
            "a": _quest("a", "completed"),
            "b": _quest("b", "active", prereq=["a"]),
        }
    )
    assert check_quest_graph(s) == []


# --- check_chapter_graph --------------------------------------------------


def _chapter(
    cid: str, status: str = "locked", prereq: list[str] | None = None
) -> Chapter:
    return Chapter(
        id=cid,
        title=cid,
        prerequisite_ids=prereq or [],
        status=status,
    )


def test_chapter_graph_active_with_uncompleted_prereq():
    s = Scenario(
        chapters={
            "a": _chapter("a", "active"),
            "b": _chapter("b", "active", prereq=["a"]),
        }
    )
    msgs = check_chapter_graph(s)
    assert any("status='active'" in m and "'a'" in m for m in msgs)


def test_chapter_graph_cycle():
    s = Scenario(
        chapters={
            "a": _chapter("a", "locked", prereq=["b"]),
            "b": _chapter("b", "locked", prereq=["a"]),
        }
    )
    msgs = check_chapter_graph(s)
    assert any("cycle" in m for m in msgs)


def test_chapter_graph_active_with_completed_prereq_passes():
    s = Scenario(
        chapters={
            "a": _chapter("a", "completed"),
            "b": _chapter("b", "active", prereq=["a"]),
        }
    )
    assert check_chapter_graph(s) == []


# --- check_scenario (integration) -----------------------------------------


def _minimal_scenario(**overrides) -> Scenario:
    sword = Item(
        id="sword",
        name="sword",
        weight=1.0,
        effects=WeaponEffect(type="weapon", weapon_dice="1d6"),
    )
    from src.domain.entities import Chapter, Location

    location = Location(id="inn", name="inn")
    slash_skill = _basic_skill("slash", level=1)
    npc = _char(
        cid="npc1",
        level=2,
        race_id="human",
        location_id="inn",
        inventory=["sword"],
        equipment=Equipment(weapon="sword"),
        skills=[slash_skill],
        aggressive=80,
        combat=CombatBehavior(attack_priority="nearest", flee_hp_percent=20),
        xp_reward=80,
    )
    quest = Quest(
        id="q1",
        title="t",
        giver_id="npc1",
        difficulty="보통",
        status="active",
        triggers=[
            QuestTrigger(id="t1", name="t1", type="character_death", target_id="npc1")
        ],
    )
    chapter = Chapter(id="ch1", title="c", quest_ids=["q1"], status="active")
    base = Scenario(
        races={"human": Race(id="human", name="human", description="d")},
        locations={"inn": location},
        items={"sword": sword},
        skills={"slash": slash_skill},
        characters={"npc1": npc},
        quests={"q1": quest},
        chapters={"ch1": chapter},
        start={
            "start_location_id": "inn",
            "active_subject_id": "npc1",
            "active_quest_id": "q1",
        },
        player_template={"id": "player_01", "equipment": {}, "inventory_ids": []},
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_scenario_minimal_passes():
    assert check_scenario(_minimal_scenario()) == []


def test_scenario_dangling_race_id():
    s = _minimal_scenario()
    s.characters["npc1"].race_id = "elf"
    msgs = check_scenario(s)
    assert any("race_id='elf'" in m and "not in races" in m for m in msgs)


def test_scenario_start_subject_at_wrong_location():
    s = _minimal_scenario()
    s.characters["npc1"].location_id = None
    msgs = check_scenario(s)
    assert any("active_subject_id" in m and "location_id" in m for m in msgs)


def test_scenario_seed_full_hp_required():
    s = _minimal_scenario()
    s.characters["npc1"].hp = 1
    msgs = check_scenario(s)
    assert any("seed hp" in m for m in msgs)


def test_scenario_npc_level_zero_rejected():
    s = _minimal_scenario()
    npc = s.characters["npc1"]
    npc.level = 0
    npc.max_hp = calc_max_hp(0, npc.stats.CON)
    npc.max_mp = calc_max_mp(0, npc.stats.INT)
    npc.hp = npc.max_hp
    npc.mp = npc.max_mp
    msgs = check_scenario(s)
    assert any("NPC level=0" in m for m in msgs)


def test_scenario_hostile_npc_unarmed_passes():
    s = _minimal_scenario()
    s.characters["npc1"].equipment = Equipment()
    s.characters["npc1"].inventory_ids = []
    msgs = check_scenario(s)
    assert not any("equipped weapon" in m for m in msgs)


def test_scenario_active_quest_locked():
    s = _minimal_scenario()
    s.quests["q1"].status = "locked"
    msgs = check_scenario(s)
    assert any("active_quest_id" in m and "locked" in m for m in msgs)


def test_scenario_player_template_missing_item():
    s = _minimal_scenario()
    s.player_template["inventory_ids"] = ["ghost"]
    msgs = check_scenario(s)
    assert any("player_template" in m and "ghost" in m for m in msgs)


# --- check_state (relaxed) ------------------------------------------------


def test_state_allows_partial_hp(fresh_state):
    s = _minimal_scenario()
    fresh_state.races = s.races
    fresh_state.locations = s.locations
    fresh_state.items = s.items
    fresh_state.characters = s.characters
    fresh_state.quests = s.quests
    fresh_state.chapters = s.chapters
    fresh_state.active_subject_id = "npc1"
    fresh_state.active_quest_id = "q1"
    # Damage taken — runtime state, not seed
    fresh_state.characters["npc1"].hp = 5
    msgs = check_scenario(Scenario.from_state(fresh_state))
    # No "seed hp" violation; max_hp formula still holds
    assert not any("seed hp" in m for m in msgs)

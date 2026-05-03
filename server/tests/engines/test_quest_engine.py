"""Quest auto-triggers, rewards, chapter progression — character_death / location_enter / item_use."""

from src.domain.entities import (
    Chapter,
    Character,
    CombatBehavior,
    Item,
    Location,
    Quest,
    QuestRewards,
    QuestTrigger,
    Stats,
)
from src.engines import quest as q


def _player(**kw):
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        gold=0,
        xp_pool=0,
    )
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def _quest(
    qid,
    *,
    triggers,
    status="active",
    required=True,
    prereq=None,
    fail=None,
    rewards=None,
):
    return Quest(
        id=qid,
        title=qid,
        giver_id="someone",
        difficulty="보통",
        triggers=triggers,
        fail_triggers=fail or [],
        prerequisite_ids=prereq or [],
        status=status,
        required=required,
        rewards=rewards or QuestRewards(),
    )


def _trig(tid, ttype, target, name="x"):
    return QuestTrigger(id=tid, name=name, type=ttype, target_id=target)


def _state(fresh_state, *, quests=None, chapters=None):
    fresh_state.characters["player_01"] = _player()
    if quests:
        for q_obj in quests:
            fresh_state.quests[q_obj.id] = q_obj
    if chapters:
        for ch in chapters:
            fresh_state.chapters[ch.id] = ch
    return fresh_state


# --- Single trigger ---------------------------------------------------------


def test_single_trigger_completes_quest_and_applies_rewards(fresh_state):
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[_trig("a", "character_death", "goblin_01")],
                rewards=QuestRewards(gold=50, exp=100),
            )
        ],
    )
    dirty: set[tuple[str, str]] = set()
    changed = q.check_quests(state, "character_death", "goblin_01", dirty)
    assert changed == ["q1"]
    qq = state.quests["q1"]
    assert qq.status == "completed"
    assert qq.triggers_met == [True]
    p = state.characters["player_01"]
    assert p.gold == 50
    assert p.xp_pool == 100
    assert ("quests", "q1") in dirty
    assert ("characters", "player_01") in dirty


def test_unrelated_event_does_not_change_quest(fresh_state):
    state = _state(
        fresh_state,
        quests=[_quest("q1", triggers=[_trig("a", "character_death", "goblin_01")])],
    )
    dirty: set[tuple[str, str]] = set()
    changed = q.check_quests(state, "location_enter", "plaza_01", dirty)
    assert changed == []
    assert state.quests["q1"].status == "active"


def test_inactive_quest_skipped(fresh_state):
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[_trig("a", "character_death", "goblin_01")],
                status="locked",
            )
        ],
    )
    q.check_quests(state, "character_death", "goblin_01")
    # locked → not evaluated
    assert state.quests["q1"].status == "locked"


# --- Multiple triggers (AND) ----------------------------------------------


def test_multiple_triggers_require_all(fresh_state):
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[
                    _trig("a", "character_death", "goblin_01"),
                    _trig("b", "location_enter", "plaza_01"),
                ],
            )
        ],
    )
    q.check_quests(state, "character_death", "goblin_01")
    assert state.quests["q1"].status == "active"  # 1/2
    q.check_quests(state, "location_enter", "plaza_01")
    assert state.quests["q1"].status == "completed"  # 2/2


# --- single-fire ----------------------------------------------------------


def test_same_trigger_event_fires_once(fresh_state):
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[_trig("a", "character_death", "goblin_01")],
                rewards=QuestRewards(gold=10),
            )
        ],
    )
    q.check_quests(state, "character_death", "goblin_01")
    assert state.characters["player_01"].gold == 10
    # Same event twice — rewards must not stack
    q.check_quests(state, "character_death", "goblin_01")
    assert state.characters["player_01"].gold == 10


# --- prereq unlock --------------------------------------------------------


def test_completing_quest_unlocks_dependents(fresh_state):
    state = _state(
        fresh_state,
        quests=[
            _quest("q1", triggers=[_trig("a", "character_death", "goblin_01")]),
            _quest(
                "q2",
                triggers=[_trig("b", "location_enter", "plaza_01")],
                status="locked",
                prereq=["q1"],
            ),
        ],
    )
    q.check_quests(state, "character_death", "goblin_01")
    assert state.quests["q1"].status == "completed"
    assert state.quests["q2"].status == "active"  # unlocked


# --- fail trigger ---------------------------------------------------------


def test_fail_trigger_marks_quest_failed(fresh_state):
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[_trig("a", "character_death", "boss_01")],
                fail=[_trig("f", "character_death", "civilian_01")],
                rewards=QuestRewards(gold=999),
            )
        ],
    )
    q.check_quests(state, "character_death", "civilian_01")
    qq = state.quests["q1"]
    assert qq.status == "failed"
    # Rewards not applied
    assert state.characters["player_01"].gold == 0


# --- chapter progress -----------------------------------------------------


def test_chapter_progress_counts_required_only(fresh_state):
    state = _state(
        fresh_state,
        quests=[
            _quest("q_main", triggers=[_trig("a", "character_death", "goblin_01")]),
            _quest(
                "q_side",
                triggers=[_trig("b", "item_use", "herb_01")],
                required=False,
            ),
        ],
        chapters=[
            Chapter(
                id="ch1", title="t", quest_ids=["q_main", "q_side"], status="active"
            )
        ],
    )
    q.check_quests(state, "character_death", "goblin_01")
    ch = state.chapters["ch1"]
    assert ch.progress.total == 1  # required=true only
    assert ch.progress.done == 1


def test_chapter_advances_when_all_required_complete(fresh_state):
    state = _state(
        fresh_state,
        quests=[_quest("q_main", triggers=[_trig("a", "character_death", "g1")])],
        chapters=[Chapter(id="ch1", title="t", quest_ids=["q_main"], status="active")],
    )
    q.check_quests(state, "character_death", "g1")
    assert state.chapters["ch1"].status == "completed"


# --- chapter prereq unlock ------------------------------------------------


def test_completing_chapter_unlocks_dependent_chapter(fresh_state):
    state = _state(
        fresh_state,
        quests=[_quest("q1", triggers=[_trig("a", "character_death", "g1")])],
        chapters=[
            Chapter(id="ch1", title="t1", quest_ids=["q1"], status="active"),
            Chapter(
                id="ch2",
                title="t2",
                quest_ids=[],
                prerequisite_ids=["ch1"],
                status="locked",
            ),
        ],
    )
    q.check_quests(state, "character_death", "g1")
    assert state.chapters["ch1"].status == "completed"
    assert state.chapters["ch2"].status == "active"


def test_chapter_with_uncompleted_prereq_stays_locked(fresh_state):
    state = _state(
        fresh_state,
        quests=[_quest("q1", triggers=[_trig("a", "character_death", "g1")])],
        chapters=[
            Chapter(id="ch1", title="t1", quest_ids=["q1"], status="active"),
            Chapter(
                id="ch2",
                title="t2",
                quest_ids=[],
                prerequisite_ids=["ch1", "ch3"],
                status="locked",
            ),
            Chapter(id="ch3", title="t3", quest_ids=[], status="locked"),
        ],
    )
    q.check_quests(state, "character_death", "g1")
    # ch1 done but ch3 still locked → ch2 stays locked
    assert state.chapters["ch2"].status == "locked"


# --- Runtime field consistency --------------------------------------------


def test_seed_quest_with_empty_triggers_met_gets_initialized(fresh_state):
    """Seed quests may arrive with triggers_met=[]; first evaluation aligns the length."""
    state = _state(
        fresh_state,
        quests=[
            _quest("q1", triggers=[_trig("a", "character_death", "g1")]),
        ],
    )
    state.quests["q1"].triggers_met = []  # bare seed state
    q.check_quests(state, "character_death", "g1")
    qq = state.quests["q1"]
    assert qq.triggers_met == [True]
    assert qq.status == "completed"


def test_appended_trigger_preserves_existing_progress(fresh_state):
    """Regression: when a seed change adds a new trigger to an in-flight quest,
    the existing satisfied triggers must not be reset to all-False. The earlier
    implementation overwrote `triggers_met` with `[False] * n` on any length
    mismatch, silently losing player progress."""
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[
                    _trig("a", "character_death", "g1"),
                    _trig("b", "character_death", "g2"),
                    _trig("c", "character_death", "g3"),  # new trigger added later
                ],
            ),
        ],
    )
    # Simulate state loaded from disk where the third trigger didn't exist yet.
    state.quests["q1"].triggers_met = [True, False]
    # Fire an unrelated event so check_quests runs alignment.
    q.check_quests(state, "character_death", "unrelated_npc")
    assert state.quests["q1"].triggers_met == [True, False, False]


def test_rewards_include_items(fresh_state):
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[_trig("a", "character_death", "g1")],
                rewards=QuestRewards(gold=0, exp=0, items=["sword_01"]),
            )
        ],
    )
    state.items["sword_01"] = Item(id="sword_01", name="검", weight=0)
    q.check_quests(state, "character_death", "g1")
    assert "sword_01" in state.characters["player_01"].inventory_ids


def test_rewards_overflow_drops_to_location(fresh_state):
    """When a reward item exceeds carry, it lands at the player's location."""
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[_trig("a", "character_death", "g1")],
                rewards=QuestRewards(items=["anvil_01"]),
            )
        ],
    )
    state.items["anvil_01"] = Item(id="anvil_01", name="모루", weight=999)
    state.locations["loc_01"] = Location(id="loc_01", name="대장간", description="")
    state.characters["player_01"].location_id = "loc_01"
    q.check_quests(state, "character_death", "g1")
    assert "anvil_01" not in state.characters["player_01"].inventory_ids
    assert "anvil_01" in state.locations["loc_01"].item_ids


# --- kill trigger fallback by location ------------------------------------


def test_kill_trigger_matches_same_location_hostile_when_id_misses(fresh_state):
    """Trigger references a scenario bandit at san_pass_road; player kills a
    different hostile (dynamic spawn) at the same location. The fallback
    matches by (event_type=character_death, victim's location == trigger
    target's location, victim has combat_behavior)."""
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[_trig("a", "character_death", "bandit_at_san_pass")],
                rewards=QuestRewards(gold=50, exp=100),
            )
        ],
    )
    state.locations["san_pass_road"] = Location(id="san_pass_road", name="산문 가는 길")
    state.characters["bandit_at_san_pass"] = Character(
        id="bandit_at_san_pass",
        name="약탈자",
        race_id="human",
        stats=Stats(),
        location_id="san_pass_road",
        combat_behavior=CombatBehavior(),
    )
    state.characters["goblin_spawn_3"] = Character(
        id="goblin_spawn_3",
        name="고블린 약탈자",
        race_id="goblin",
        stats=Stats(),
        location_id="san_pass_road",
        combat_behavior=CombatBehavior(),
        alive=False,
    )
    dirty: set[tuple[str, str]] = set()
    changed = q.check_quests(state, "character_death", "goblin_spawn_3", dirty)
    assert changed == ["q1"]
    assert state.quests["q1"].status == "completed"
    assert state.quests["q1"].triggers_met == [True]
    assert state.characters["player_01"].gold == 50
    assert state.characters["player_01"].xp_pool == 100


def test_kill_trigger_fallback_skips_non_hostile(fresh_state):
    """A non-hostile (no combat_behavior) victim at the right location
    must NOT satisfy the trigger — guards against quest completion when the
    player kills a friendly NPC."""
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[_trig("a", "character_death", "bandit_at_san_pass")],
            )
        ],
    )
    state.locations["san_pass_road"] = Location(id="san_pass_road", name="산문 가는 길")
    state.characters["bandit_at_san_pass"] = Character(
        id="bandit_at_san_pass",
        name="약탈자",
        race_id="human",
        stats=Stats(),
        location_id="san_pass_road",
        combat_behavior=CombatBehavior(),
    )
    state.characters["villager_npc"] = Character(
        id="villager_npc",
        name="마을 사람",
        race_id="human",
        stats=Stats(),
        location_id="san_pass_road",
        combat_behavior=None,
        alive=False,
    )
    q.check_quests(state, "character_death", "villager_npc")
    assert state.quests["q1"].status == "active"


def test_kill_trigger_fallback_skips_different_location(fresh_state):
    """A hostile killed at a DIFFERENT location must not satisfy the trigger."""
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[_trig("a", "character_death", "bandit_at_san_pass")],
            )
        ],
    )
    state.locations["san_pass_road"] = Location(id="san_pass_road", name="산문 가는 길")
    state.locations["plaza"] = Location(id="plaza", name="광장")
    state.characters["bandit_at_san_pass"] = Character(
        id="bandit_at_san_pass",
        name="약탈자",
        race_id="human",
        stats=Stats(),
        location_id="san_pass_road",
        combat_behavior=CombatBehavior(),
    )
    state.characters["goblin_spawn_3"] = Character(
        id="goblin_spawn_3",
        name="고블린",
        race_id="goblin",
        stats=Stats(),
        location_id="plaza",
        combat_behavior=CombatBehavior(),
        alive=False,
    )
    q.check_quests(state, "character_death", "goblin_spawn_3")
    assert state.quests["q1"].status == "active"


def test_kill_trigger_fallback_skips_when_target_id_unknown(fresh_state):
    """If the trigger's target_id refers to no Character (no location to anchor),
    the fallback can't fire — only exact-id match works."""
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[_trig("a", "character_death", "abstract_quest_target")],
            )
        ],
    )
    state.locations["san_pass_road"] = Location(id="san_pass_road", name="산문 가는 길")
    state.characters["goblin_spawn_3"] = Character(
        id="goblin_spawn_3",
        name="고블린",
        race_id="goblin",
        stats=Stats(),
        location_id="san_pass_road",
        combat_behavior=CombatBehavior(),
        alive=False,
    )
    q.check_quests(state, "character_death", "goblin_spawn_3")
    assert state.quests["q1"].status == "active"


def test_non_kill_trigger_event_does_not_fall_back(fresh_state):
    """Fallback applies only to character_death — location_enter / item_use
    must keep strict id matching."""
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                triggers=[_trig("a", "location_enter", "plaza_main")],
            )
        ],
    )
    state.locations["plaza_main"] = Location(id="plaza_main", name="중앙 광장")
    state.locations["plaza_side"] = Location(id="plaza_side", name="옆 광장")
    q.check_quests(state, "location_enter", "plaza_side")
    assert state.quests["q1"].status == "active"

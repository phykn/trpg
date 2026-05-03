from src.domain.entities import (
    Chapter,
    Character,
    Connection,
    Equipment,
    Item,
    Location,
    Quest,
    QuestRewards,
    QuestTrigger,
    Race,
    Skill,
    Stats,
)
from src.ontology.graph import build_graph
from src.ontology.target_view import build_target_view


def _seed(state):
    state.locations["plaza_01"] = Location(
        id="plaza_01",
        name="광장",
        connections=[Connection(target_id="gate_01", key_item_id="key_01")],
    )
    state.locations["gate_01"] = Location(id="gate_01", name="성문")
    state.items["sword_01"] = Item(id="sword_01", name="검")
    state.items["key_01"] = Item(id="key_01", name="열쇠")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        inventory_ids=["key_01"],
        relations={"guard_01": -25},
    )
    state.characters["guard_01"] = Character(
        id="guard_01",
        name="경비",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        appearance="갑옷",
        tone_hint="격식",
    )
    state.quests["q1"] = Quest(
        id="q1",
        title="t",
        giver_id="guard_01",
        difficulty="보통",
        triggers=[
            QuestTrigger(
                id="x", name="처치", type="character_death", target_id="goblin_01"
            )
        ],
        rewards=QuestRewards(items=["sword_01"]),
    )
    return state


def test_graph_node_types(fresh_state):
    g = build_graph(_seed(fresh_state))
    assert g.get_node_type("player_01") == "character"
    assert g.get_node_type("plaza_01") == "location"
    assert g.get_node_type("sword_01") == "item"
    assert g.get_node_type("q1") == "quest"
    assert g.get_node_type("ghost") is None


def test_graph_edges(fresh_state):
    g = build_graph(_seed(fresh_state))
    assert any(e.to_id == "plaza_01" for e in g.get_edges("player_01", "located_at"))
    assert any(e.to_id == "key_01" for e in g.get_edges("player_01", "carries"))
    assert any(e.to_id == "gate_01" for e in g.get_edges("plaza_01", "connects_to"))
    assert any(e.to_id == "gate_01" for e in g.get_edges("key_01", "unlocks"))
    assert any(e.to_id == "q1" for e in g.get_edges("guard_01", "gives_quest"))
    assert any(e.to_id == "q1" for e in g.get_edges("sword_01", "reward_of"))


def test_target_view_npc(fresh_state):
    state = _seed(fresh_state)
    g = build_graph(state)
    v = build_target_view(state, g, "guard_01", actor_id="player_01")
    assert v["type"] == "npc" and v["name"] == "경비"
    assert v["appearance"] == "갑옷"
    assert v["tone_hint"] == "격식"


def test_target_view_location(fresh_state):
    state = _seed(fresh_state)
    g = build_graph(state)
    v = build_target_view(state, g, "plaza_01", actor_id="player_01")
    assert v["type"] == "location" and v["name"] == "광장"


def test_target_view_item(fresh_state):
    state = _seed(fresh_state)
    g = build_graph(state)
    v = build_target_view(state, g, "key_01", actor_id="player_01")
    assert v["type"] == "item" and v["name"] == "열쇠"


def test_target_view_unknown_returns_none(fresh_state):
    state = _seed(fresh_state)
    g = build_graph(state)
    assert build_target_view(state, g, "ghost", actor_id="player_01") is None


def test_target_view_npc_failure_grade_masks_secrets(fresh_state):
    """Failure-grade narrate path drops NPC inner-state slots: tone_hint
    (true disposition) and memories (past secrets). Identity slots
    (name/description/appearance) stay — race/appearance prose still needs
    them. quests_given keeps title/kill_targets/triggers (player can still
    see *what* the quest is) but rewards detail drops."""
    state = _seed(fresh_state)
    # Add a memory so the masking is observable, not just absent-by-seed.
    from src.domain.memory import Memory

    state.characters["guard_01"].memories.append(
        Memory(content="비밀 단서", importance=2, turn=1)
    )
    g = build_graph(state)

    base = build_target_view(state, g, "guard_01", actor_id="player_01")
    assert base["tone_hint"] == "격식"
    assert base["memories"] and base["memories"][0]["content"] == "비밀 단서"
    assert base["quests_given"][0].get("rewards") == [{"id": "sword_01", "name": "검"}]

    masked = build_target_view(
        state, g, "guard_01", actor_id="player_01", grade="failure"
    )
    assert "tone_hint" not in masked, "tone_hint must drop on failure grade"
    assert "memories" not in masked, "memories must drop on failure grade"
    assert masked["name"] == "경비"  # identity stays
    assert "appearance" in masked
    # quest stays surfaced (player can know the quest exists) but rewards drop.
    assert masked["quests_given"][0]["title"] == "t"
    assert "rewards" not in masked["quests_given"][0]


def test_target_view_npc_critical_failure_grade_also_masks(fresh_state):
    state = _seed(fresh_state)
    g = build_graph(state)
    masked = build_target_view(
        state, g, "guard_01", actor_id="player_01", grade="critical_failure"
    )
    assert "tone_hint" not in masked


def test_target_view_npc_success_grade_unchanged(fresh_state):
    """Non-masked grades (success, partial_success, critical_success, None)
    leave the view identical to a no-grade call — gate is failure-only."""
    state = _seed(fresh_state)
    g = build_graph(state)
    base = build_target_view(state, g, "guard_01", actor_id="player_01")
    for grade in ("success", "partial_success", "critical_success", None):
        v = build_target_view(state, g, "guard_01", actor_id="player_01", grade=grade)
        assert v == base, f"grade={grade!r} should not mask"


def test_target_view_location_failure_grade_masks_quest_rewards(fresh_state):
    state = _seed(fresh_state)
    g = build_graph(state)
    base = build_target_view(state, g, "plaza_01", actor_id="player_01")
    # plaza has no quest in this seed; add a `required_by` link via a quest
    # whose trigger is the location.
    from src.domain.entities import QuestTrigger

    state.quests["q_loc"] = state.quests["q1"].model_copy(
        update={
            "id": "q_loc",
            "title": "광장 가기",
            "triggers": [
                QuestTrigger(
                    id="x", name="도착", type="location_enter", target_id="plaza_01"
                )
            ],
        }
    )
    g = build_graph(state)
    base = build_target_view(state, g, "plaza_01", actor_id="player_01")
    assert any(q.get("rewards") for q in base.get("quests", []))

    masked = build_target_view(
        state, g, "plaza_01", actor_id="player_01", grade="failure"
    )
    for q in masked.get("quests", []):
        assert "rewards" not in q, f"location quest rewards must drop: {q}"


def test_target_view_dead_character_returns_dead_marker(fresh_state):
    """Dead NPC target_view returns name + alive=False + lootable inventory
    so narrate gets the death signal and what's loot-eligible without
    leaking live-only fields (memories/disposition)."""
    state = _seed(fresh_state)
    state.characters["guard_01"].alive = False
    g = build_graph(state)
    v = build_target_view(state, g, "guard_01", actor_id="player_01")
    assert v == {
        "type": "npc",
        "id": "guard_01",
        "name": "경비",
        "alive": False,
        "inventory": [],
    }


# --- Phase 1: richer graph (in_edges, attrs, new edge types, new nodes) ----


def _seed_phase1(state):
    """Wider seed for Phase 1 — covers race, skill, chapter, equipment, items
    in a location, and a quest whose trigger has type=character_death (so
    `kill_target_of` is exercised alongside `required_by`)."""
    state.races["human"] = Race(
        id="human", name="인간", description="평범한 인간", racial_skill_ids=["bite"]
    )
    state.skills["bite"] = Skill(
        id="bite", name="물기", type="attack", target="single", primary_stat="STR"
    )
    state.skills["fireball"] = Skill(
        id="fireball", name="화염구", type="attack", target="single", primary_stat="INT"
    )
    state.locations["plaza_01"] = Location(
        id="plaza_01",
        name="광장",
        connections=[
            Connection(target_id="gate_01", difficulty="어려움", key_item_id="key_01")
        ],
        item_ids=["sword_01"],
    )
    state.locations["gate_01"] = Location(id="gate_01", name="성문")
    state.items["sword_01"] = Item(id="sword_01", name="검")
    state.items["key_01"] = Item(id="key_01", name="열쇠")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        equipment=Equipment(weapon="sword_01"),
        inventory_ids=["key_01"],
        racial_skill_ids=["bite"],
        learned_skill_ids=["fireball"],
    )
    state.characters["goblin_01"] = Character(
        id="goblin_01",
        name="고블린",
        race_id="human",
        stats=Stats(),
        location_id="gate_01",
    )
    state.quests["q_kill"] = Quest(
        id="q_kill",
        title="고블린 처치",
        giver_id="player_01",
        difficulty="보통",
        triggers=[
            QuestTrigger(
                id="t1", name="처치", type="character_death", target_id="goblin_01"
            )
        ],
    )
    state.quests["q_visit"] = Quest(
        id="q_visit",
        title="성문에 도착",
        giver_id="player_01",
        difficulty="쉬움",
        triggers=[
            QuestTrigger(
                id="t2", name="도착", type="location_enter", target_id="gate_01"
            )
        ],
    )
    state.chapters["ch1"] = Chapter(
        id="ch1", title="1장", quest_ids=["q_kill", "q_visit"]
    )
    return state


def test_new_node_types(fresh_state):
    g = build_graph(_seed_phase1(fresh_state))
    assert g.get_node_type("human") == "race"
    assert g.get_node_type("bite") == "skill"
    assert g.get_node_type("ch1") == "chapter"


def test_in_edges_invert_out_edges(fresh_state):
    """get_in_edges answers 'who points at me' without scanning all nodes."""
    g = build_graph(_seed_phase1(fresh_state))
    here = [e.from_id for e in g.get_in_edges("plaza_01", "located_at")]
    assert "player_01" in here and "goblin_01" not in here  # goblin is at gate_01


def test_located_in_item_to_location(fresh_state):
    g = build_graph(_seed_phase1(fresh_state))
    assert any(e.to_id == "plaza_01" for e in g.get_edges("sword_01", "located_in"))
    # And the inverse — what's at this location
    items_here = [e.from_id for e in g.get_in_edges("plaza_01", "located_in")]
    assert items_here == ["sword_01"]


def test_kill_target_of_separate_from_required_by(fresh_state):
    """character_death triggers get BOTH `required_by` (general) and
    `kill_target_of` (specific). location_enter gets only `required_by`."""
    g = build_graph(_seed_phase1(fresh_state))
    # goblin: character_death trigger → both edges
    goblin_out = {e.type for e in g.get_edges("goblin_01")}
    assert "kill_target_of" in goblin_out
    assert "required_by" in goblin_out
    # gate_01: location_enter trigger → required_by only
    gate_out = {e.type for e in g.get_edges("gate_01")}
    assert "required_by" in gate_out
    assert "kill_target_of" not in gate_out


def test_knows_skill_with_source_attr(fresh_state):
    g = build_graph(_seed_phase1(fresh_state))
    edges = g.get_edges("player_01", "knows_skill")
    by_skill = {e.to_id: e.attrs for e in edges}
    assert by_skill["bite"] == {"source": "racial"}
    assert by_skill["fireball"] == {"source": "learned"}


def test_belongs_to_race(fresh_state):
    g = build_graph(_seed_phase1(fresh_state))
    assert any(e.to_id == "human" for e in g.get_edges("player_01", "belongs_to_race"))


def test_member_of_chapter(fresh_state):
    g = build_graph(_seed_phase1(fresh_state))
    chapter_quests = {e.from_id for e in g.get_in_edges("ch1", "member_of_chapter")}
    assert chapter_quests == {"q_kill", "q_visit"}


def test_racial_skill_of(fresh_state):
    g = build_graph(_seed_phase1(fresh_state))
    assert any(e.to_id == "human" for e in g.get_edges("bite", "racial_skill_of"))


def test_equips_carries_attrs(fresh_state):
    g = build_graph(_seed_phase1(fresh_state))
    equip_edges = g.get_edges("player_01", "equips")
    assert len(equip_edges) == 1
    assert equip_edges[0].to_id == "sword_01"
    assert equip_edges[0].attrs == {"slot": "weapon"}


def test_connects_to_attrs(fresh_state):
    g = build_graph(_seed_phase1(fresh_state))
    edges = g.get_edges("plaza_01", "connects_to")
    assert len(edges) == 1
    assert edges[0].to_id == "gate_01"
    assert edges[0].attrs == {"difficulty": "어려움", "key_item_id": "key_01"}


# --- Phase 4: target_view 2-hop traversal ----------------------------------


def _seed_phase4(state):
    """Quest ecosystem: an NPC who gives a quest, the quest's kill target,
    location trigger, and reward item — so npc/location/item views can each
    pull a complete 2-hop story for narrate."""
    state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    state.locations["ruins_01"] = Location(id="ruins_01", name="낡은 폐허")
    state.items["sword_01"] = Item(id="sword_01", name="대장의 검")
    state.items["key_01"] = Item(id="key_01", name="고대의 열쇠")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    state.characters["chief_01"] = Character(
        id="chief_01",
        name="에드릭 촌장",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    state.characters["goblin_01"] = Character(
        id="goblin_01",
        name="고블린 두목",
        race_id="human",
        stats=Stats(),
        location_id="ruins_01",
    )
    state.quests["q_chief"] = Quest(
        id="q_chief",
        title="촌장의 부탁",
        giver_id="chief_01",
        difficulty="보통",
        triggers=[
            QuestTrigger(
                id="t1", name="처치", type="character_death", target_id="goblin_01"
            ),
            QuestTrigger(
                id="t2", name="도착", type="location_enter", target_id="ruins_01"
            ),
        ],
        rewards=QuestRewards(items=["sword_01"]),
    )
    return state


def test_npc_view_2hop_surfaces_quest_kill_targets(fresh_state):
    """NPC view's quests_given resolves the quest's kill targets by name —
    narrator can phrase 'goblin 두목을 처치해 달라' instead of seeing a bare id."""
    state = _seed_phase4(fresh_state)
    g = build_graph(state)
    v = build_target_view(state, g, "chief_01", actor_id="player_01")
    assert v["quests_given"]
    q = v["quests_given"][0]
    assert q["title"] == "촌장의 부탁"
    assert q["status"] == "locked"
    kill_names = [t["name"] for t in q.get("kill_targets", [])]
    assert "고블린 두목" in kill_names


def test_npc_view_2hop_surfaces_quest_triggers_and_rewards(fresh_state):
    state = _seed_phase4(fresh_state)
    g = build_graph(state)
    v = build_target_view(state, g, "chief_01", actor_id="player_01")
    q = v["quests_given"][0]
    # location trigger surfaces under triggers (kill targets are split out)
    trigger_names = [t["name"] for t in q.get("triggers", [])]
    assert "낡은 폐허" in trigger_names
    # rewards resolve item ids to names
    reward_names = [r["name"] for r in q.get("rewards", [])]
    assert "대장의 검" in reward_names


def test_npc_view_kill_target_self_flagged(fresh_state):
    """NPC who is itself a quest's kill target flags it under quests_kill_target,
    so narrate knows 'killing me advances something' even if I don't give a quest."""
    state = _seed_phase4(fresh_state)
    g = build_graph(state)
    v = build_target_view(state, g, "goblin_01", actor_id="player_01")
    titles = [q["title"] for q in (v.get("quests_kill_target") or [])]
    assert "촌장의 부탁" in titles


def test_location_view_2hop_surfaces_quest_giver(fresh_state):
    """Location view's quests payload includes the giver name so narrate can
    phrase '이 폐허를 가야 하는 이유는 에드릭 촌장의 부탁이오'."""
    state = _seed_phase4(fresh_state)
    g = build_graph(state)
    v = build_target_view(state, g, "ruins_01", actor_id="player_01")
    assert v["quests"]
    q = v["quests"][0]
    assert q["giver"]["name"] == "에드릭 촌장"


def test_item_view_resolves_unlocks_and_reward_of(fresh_state):
    """Item view replaces raw `edges` with name-resolved unlocks/reward_of/located_in
    so narrate doesn't see bare ids."""
    state = _seed_phase4(fresh_state)
    # add the unlock relation
    state.locations["plaza_01"].connections.append(
        Connection(target_id="ruins_01", key_item_id="key_01")
    )
    g = build_graph(state)
    v = build_target_view(state, g, "key_01", actor_id="player_01")
    unlocks_names = [u["name"] for u in (v.get("unlocks") or [])]
    assert "낡은 폐허" in unlocks_names

    # sword_01 is a reward → reward_of resolves quest title
    v_sword = build_target_view(state, g, "sword_01", actor_id="player_01")
    reward_titles = [r["title"] for r in (v_sword.get("reward_of") or [])]
    assert "촌장의 부탁" in reward_titles


def test_npc_view_drops_completed_failed_quests(fresh_state):
    """quests_given and quests_kill_target filter out completed/failed; locked/active survive with full 2-hop payload."""
    state = _seed(fresh_state)
    state.quests["q_locked"] = Quest(
        id="q_locked",
        title="잠긴 의뢰",
        giver_id="guard_01",
        difficulty="보통",
        triggers=[
            QuestTrigger(
                id="t1", name="처치", type="character_death", target_id="goblin_01"
            )
        ],
        rewards=QuestRewards(items=["sword_01"]),
        status="locked",
    )
    state.quests["q_active"] = Quest(
        id="q_active",
        title="진행 의뢰",
        giver_id="guard_01",
        difficulty="보통",
        triggers=[
            QuestTrigger(
                id="t2", name="처치", type="character_death", target_id="goblin_02"
            )
        ],
        rewards=QuestRewards(items=["sword_01"]),
        status="active",
    )
    state.quests["q_completed"] = Quest(
        id="q_completed",
        title="완료 의뢰",
        giver_id="guard_01",
        difficulty="보통",
        status="completed",
    )
    state.quests["q_failed"] = Quest(
        id="q_failed",
        title="실패 의뢰",
        giver_id="guard_01",
        difficulty="보통",
        status="failed",
    )
    state.characters["goblin_02"] = Character(
        id="goblin_02", name="고블린2", race_id="human", stats=Stats()
    )
    state.quests["q_hunt_active"] = Quest(
        id="q_hunt_active",
        title="현상금: 경비",
        giver_id="player_01",
        difficulty="보통",
        triggers=[
            QuestTrigger(
                id="t3", name="처치", type="character_death", target_id="guard_01"
            )
        ],
        status="active",
    )
    state.quests["q_hunt_completed"] = Quest(
        id="q_hunt_completed",
        title="이전 현상금",
        giver_id="player_01",
        difficulty="보통",
        triggers=[
            QuestTrigger(
                id="t4", name="처치", type="character_death", target_id="guard_01"
            )
        ],
        status="completed",
    )

    g = build_graph(state)
    v = build_target_view(state, g, "guard_01", actor_id="player_01")

    given_titles = {q["title"] for q in v["quests_given"]}
    assert given_titles == {"t", "잠긴 의뢰", "진행 의뢰"}

    locked = next(q for q in v["quests_given"] if q["title"] == "잠긴 의뢰")
    assert locked["status"] == "locked"
    assert "rewards" in locked

    hunt_titles = {q["title"] for q in v["quests_kill_target"]}
    assert hunt_titles == {"현상금: 경비"}


def test_location_view_drops_completed_failed_quests(fresh_state):
    state = _seed(fresh_state)
    state.characters["player_01"].location_id = "plaza_01"
    state.quests["q_visit_active"] = Quest(
        id="q_visit_active",
        title="광장 방문",
        giver_id="guard_01",
        difficulty="보통",
        triggers=[
            QuestTrigger(
                id="tv1", name="도달", type="location_visited", target_id="plaza_01"
            )
        ],
        status="active",
    )
    state.quests["q_visit_completed"] = Quest(
        id="q_visit_completed",
        title="과거 방문 의뢰",
        giver_id="guard_01",
        difficulty="보통",
        triggers=[
            QuestTrigger(
                id="tv2", name="도달", type="location_visited", target_id="plaza_01"
            )
        ],
        status="completed",
    )

    g = build_graph(state)
    v = build_target_view(state, g, "plaza_01", actor_id="player_01")

    titles = {q["title"] for q in v.get("quests", [])}
    assert "광장 방문" in titles
    assert "과거 방문 의뢰" not in titles

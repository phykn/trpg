"""퀘스트 자동 트리거·보상·챕터 진행 — character_death / location_enter / item_use."""
from src.domain.entities import Chapter, Character, Quest, QuestRewards, QuestTrigger, Stats
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


def _quest(qid, *, triggers, status="active", required=True, prereq=None, fail=None, rewards=None):
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


# --- 단일 trigger -----------------------------------------------------------


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
    # locked 상태라 평가 안 함
    assert state.quests["q1"].status == "locked"


# --- 복수 trigger AND -----------------------------------------------------


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
    # 같은 이벤트 두 번 — 보상 중복 가산 안 됨
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
    assert state.quests["q2"].status == "active"  # 잠금 해제


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
    # 보상 적용 안 됨
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
            Chapter(id="ch1", title="t", quest_ids=["q_main", "q_side"], status="active")
        ],
    )
    q.check_quests(state, "character_death", "goblin_01")
    ch = state.chapters["ch1"]
    assert ch.progress.total == 1  # required=true 만
    assert ch.progress.done == 1


def test_chapter_advances_when_all_required_complete(fresh_state):
    state = _state(
        fresh_state,
        quests=[_quest("q_main", triggers=[_trig("a", "character_death", "g1")])],
        chapters=[Chapter(id="ch1", title="t", quest_ids=["q_main"], status="active")],
    )
    q.check_quests(state, "character_death", "g1")
    assert state.chapters["ch1"].status == "completed"


# --- runtime field 정합 ---------------------------------------------------


def test_seed_quest_with_empty_triggers_met_gets_initialized(fresh_state):
    """시드 quest 가 triggers_met=[] 로 들어올 수 있는데, 첫 평가에서 길이 맞춤."""
    state = _state(
        fresh_state,
        quests=[
            _quest("q1", triggers=[_trig("a", "character_death", "g1")]),
        ],
    )
    state.quests["q1"].triggers_met = []  # 시드 빈 상태
    q.check_quests(state, "character_death", "g1")
    qq = state.quests["q1"]
    assert qq.triggers_met == [True]
    assert qq.status == "completed"


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
    q.check_quests(state, "character_death", "g1")
    assert "sword_01" in state.characters["player_01"].inventory_ids

from src.mapping.labels import (
    ROLL_REASON_DEFAULT,
    STORY_EDGE_LABEL_CURRENT,
    STORY_EDGE_LABEL_MEET,
    STORY_EDGE_LABEL_MOVE,
    STORY_EDGE_LABEL_OBSERVE,
    STORY_EDGE_LABEL_PROGRESS,
    STORY_EDGE_LABEL_QUEST_GIVER,
    STORY_EDGE_LABEL_QUEST_TARGET,
    STORY_SUMMARY_EMPTY,
    STORY_SUMMARY_HERO,
    state_tag_friendly,
    state_tag_wary,
    state_tag_wounded,
    story_summary_entities,
    story_summary_location,
    story_summary_places,
    story_summary_quest,
)


def test_story_edge_labels_match_existing_text():
    assert STORY_EDGE_LABEL_CURRENT == "현재 위치"
    assert STORY_EDGE_LABEL_OBSERVE == "주시"
    assert STORY_EDGE_LABEL_PROGRESS == "진행 중"
    assert STORY_EDGE_LABEL_MOVE == "이동"
    assert STORY_EDGE_LABEL_MEET == "등장"
    assert STORY_EDGE_LABEL_QUEST_GIVER == "의뢰"
    assert STORY_EDGE_LABEL_QUEST_TARGET == "목표"


def test_story_summary_constants():
    assert STORY_SUMMARY_HERO == "주인공"
    assert STORY_SUMMARY_EMPTY == "스토리 데이터 없음"


def test_story_summary_helpers():
    assert story_summary_quest("어둠의 의뢰") == "퀘스트 어둠의 의뢰"
    assert story_summary_location("광장") == "현재 위치 광장"
    assert story_summary_entities(3) == "등장인물 3"
    assert story_summary_places(5) == "장소 5"


def test_roll_reason_default():
    assert ROLL_REASON_DEFAULT == "행동 판정"


def test_state_tag_helpers():
    assert state_tag_friendly(50) == "우호적(affinity 50)"
    assert state_tag_wary(-30) == "경계중(affinity -30)"
    assert state_tag_wounded(45) == "부상(hp 45%)"

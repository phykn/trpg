"""The relations of the ontology redesign (data/01 2절, 4절): suspicion, clearing, properties, knowing,
help for the dice, calls, and answers given as lists."""
from pathlib import Path

import pytest
import yaml
from src.ai.jobs import list_inner, make_ending
from src.game.view import make_view
from src.rules.act import act, find_bet_bonus
from src.rules.state import judge_ending, list_cleared, start_state
from src.story.check import check_story
from src.story.load import Story, StoryFile, find_missing, load_story

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
STORY = load_story(SCENARIOS / "skeleton")
SEEN = ["사람 오토", "사람 한스", "사람 리사"]
LAMP = "볼 것 꺼진 등잔"   # shows the warden left, which points at 한스
STEPS = "볼 것 창고 앞 발자국"   # the culprit does not limp, and 오토 does
FLOUR = "볼 것 밀가루 더미"   # 리사 sifted all night


def data():
    return yaml.safe_load((SCENARIOS / "skeleton" / "story.yaml").read_text(encoding="utf-8"))


def build(edit):
    raw = data()
    edit(raw)
    return Story(StoryFile.model_validate(raw))


def concluded(story, lines, who="한스"):
    state = start_state(story, 0)
    return {**state, "notebook": dict.fromkeys(lines, 1), "conclusion": {"who": who, "how": None, "why": None}}


def test_a_fact_is_a_sentence_or_carries_its_relations():
    assert STORY.facts["노름빚"].text == "한스는 노름빚에 쫓기고 있었다."
    assert (STORY.facts["자리를 비운 창고지기"].points, STORY.facts["밤새 친 체"].clears) == ("한스", "리사")
    assert STORY.suspects == ["한스", "오토", "리사"]


def test_a_new_relation_naming_nothing_stops_the_story():
    raw = data()
    raw["사실"]["경비의 열쇠"]["가리킨다"] = "유령"
    raw["사람"]["오토"]["성질"] = ["날개가 있다"]
    raw["번진 일"][0]["부르는 것"] = "말 오토.없는 화제.참말"
    missing = find_missing(StoryFile.model_validate(raw))
    assert missing == ["사실 경비의 열쇠의 가리킨다: 유령", "사람 오토의 성질: 날개가 있다",
                       "번진 일 5칸째의 부르는 것: 말 오토.없는 화제.참말"]


def test_calling_needs_its_delay_and_a_reason_to_hide_is_for_a_lie():
    raw = data()
    del raw["번진 일"][0]["뒤"]
    with pytest.raises(ValueError, match="뒤 goes with 부르는 것"):
        StoryFile.model_validate(raw)
    raw = data()
    raw["사람"]["리사"]["화제"]["새벽"]["감추는 까닭"] = "무섭다."
    with pytest.raises(ValueError, match="감추는 까닭 is for 거짓말한다"):
        StoryFile.model_validate(raw)


def test_a_suspect_is_ruled_out_by_a_clearing_fact_or_a_property_unlike_the_culprits():
    assert list_cleared(STORY, concluded(STORY, SEEN + [STEPS, FLOUR])) == ["오토", "리사"]
    # 오토's limp counts only once the player has met him
    assert list_cleared(STORY, concluded(STORY, ["사람 리사", STEPS, FLOUR])) == ["리사"]


def test_the_right_culprit_is_proven_only_when_pointed_at_and_every_other_suspect_is_ruled_out():
    assert judge_ending(STORY, concluded(STORY, SEEN + [LAMP, STEPS, FLOUR]))["proved"] is True
    assert judge_ending(STORY, concluded(STORY, SEEN + [LAMP, STEPS]))["proved"] is False
    assert judge_ending(STORY, concluded(STORY, SEEN + [STEPS, FLOUR]))["proved"] is False
    assert judge_ending(STORY, concluded(STORY, SEEN + [LAMP, STEPS, FLOUR], who="오토"))["proved"] is False
    plain = build(lambda d: [f.pop("가리킨다", None) for f in d["사실"].values() if isinstance(f, dict)])
    assert judge_ending(plain, concluded(plain, SEEN))["proved"] is None


def test_the_ending_and_its_text_know_a_guess_from_a_proof():
    state = concluded(STORY, SEEN + [LAMP, STEPS])
    assert make_view(STORY, state)[0]["ending"]["proved"] is False
    assert "짐작" in make_ending(STORY, state)["answers"]


def test_any_fact_of_a_listed_answer_answers():
    story = build(lambda d: d["머리"]["진실"].update({"어떻게": ["뒷문으로 실어 냄", "자리를 비운 창고지기"]}))
    state = {**concluded(story, [LAMP]), "conclusion": {"who": "한스", "how": LAMP, "why": None}}
    assert judge_ending(story, state)["answers"]["how"] is True


def test_a_clue_that_helps_with_a_block_adds_one_to_its_bet():
    state = {**start_state(STORY, 0), "stats": {"charm": 2, "might": 0, "wit": 1, "skill": 0}}
    base = find_bet_bonus(STORY, state, "꺼림 리사.새벽", "soothe")
    debt = {**state, "notebook": {**state["notebook"], "볼 것 빚 문서": 1}}
    assert find_bet_bonus(STORY, debt, "꺼림 리사.새벽", "soothe") == base + 1


def test_hearing_the_lie_calls_the_event_two_cells_on():
    state = start_state(STORY, 0)
    results = []
    for action, heard in [({"do": "stats", "plus2": "skill", "plus1": "charm"}, None),
                          ({"do": "move", "place": "곡물 창고"}, None),
                          ({"do": "ask"}, {"kind": "topics", "topics": ["그날 밤"]}),
                          ({"do": "move", "place": "광장"}, None), ({"do": "move", "place": "곡물 창고"}, None)]:
        result = act(STORY, state, action, heard)
        state, results = result["state"], results + [result]
    assert results[2]["happened"] == [{"omen": 0}] and state["called"] == {"0": 1}
    assert (state["spent"], state["events"]) == (3, {"0": "happened"})


def test_a_lie_gives_its_reason_to_hide_only_while_it_is_told():
    state = start_state(STORY, 0)
    assert "감추는 까닭: 들키면 마을에서 쫓겨날까 두렵다." in list_inner(STORY, state, "한스", ["말 한스.그날 밤.거짓말"])
    assert not any(i.startswith("감추는 까닭") for i in list_inner(STORY, state, "한스", ["말 한스.열쇠.참말"]))


def test_a_person_knows_what_their_words_show_and_what_their_lie_covers():
    assert STORY.knows["한스"] == ["노름빚", "경비의 열쇠", "자리를 비운 창고지기"]


@pytest.mark.parametrize("edit, name, detail", [
    (lambda d: d["사실"]["자리를 비운 창고지기"].pop("가리킨다"), "의심", "한스를 가리키는 사실이 진실 말고 없다"),
    (lambda d: d["사실"].update({"노름빚": {"문장": "빚이 있다.", "벗긴다": "한스"}}), "범인이 지워지지 않는다", "사실 노름빚"),
    (lambda d: d["볼 것"]["밀가루 더미"].pop("보여 주는 사실"), "주사위 없이 지운다", "사람 리사"),
    (lambda d: d["사람"]["리사"]["화제"]["새벽"].update({"거드는 것": ["자리를 비운 창고지기"]}), "거드는 것",
     "꺼림 리사.새벽: 자리를 비운 창고지기"),
    (lambda d: d["사실"]["고른 발자국"].update({"벗긴다": "리사"}), "한 사실이 모두를 지운다", "사실 고른 발자국"),
])
def test_each_broken_copy_fails_or_alerts_its_new_check(edit, name, detail):
    raw = data()
    edit(raw)
    results = {n: (v, d) for v, n, d in check_story(StoryFile.model_validate(raw))[0]}
    assert results[name][0] in ("떨어짐", "알림") and detail in results[name][1]


def test_a_story_copy_from_before_the_new_fields_still_opens():
    raw = data()
    raw["사실"] = {k: v if isinstance(v, str) else v["문장"] for k, v in raw["사실"].items()}
    old = Story(StoryFile.model_validate(raw))
    assert old.suspects == [] and judge_ending(old, concluded(old, SEEN))["proved"] is None

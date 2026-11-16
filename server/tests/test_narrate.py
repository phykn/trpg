from itertools import product

from src.ai.mbti import MBTI
from src.ai.narrate import judge, make_checks, make_messages, pick_best, split_sentences


def test_a_text_fails_on_low_checks_and_on_length():
    job = {"kind": "answer", "person": "브람", "bio": "", "attitude": "", "said": None, "says": ["말"], "lines": ["말"],
           "quiet": False}
    assert set(make_checks(job)) == {"added", "meaning"}
    assert judge(job, {"added": {"noul": 0.2}, "meaning": {"noul": 0.8}}, "한 말.") == (
        [], {"added": 0.2, "meaning": 0.8})
    assert judge(job, {"added": {"noul": 0.9}, "meaning": {"noul": 0.4}}, "하나. 둘! 셋? 넷. 다섯. 여섯.")[0] == [
        "added", "meaning", "length"]
    assert len(split_sentences("……알았소, 그렇다면 말하리다. 해 지기 전에 떠났소")) == 2
    assert len(split_sentences("그... 그래요. 미... 미안하면 됐어요.")) == 2   # research2-text-skeleton 인상 리사
    long = "낮게 깔린 새벽 안개 사이로 차가운 습기가 느껴지는 가운데, 우물 한가운데에 박힌 장대가 안개 속에서 희미하게 윤곽을 드러냅니다."
    assert "long" in judge(job, {"added": {"noul": 0.2}, "meaning": {"noul": 0.8}}, f"한 말. {long}")[0]
    assert judge(job, {"added": {"noul": 0.2}, "meaning": {"noul": 0.8}}, "말 모르겠어요.")[0] == []   # a person keeps their own speech


def test_an_answer_that_drops_a_line_fails_meaning_even_when_kanana_passes_it():
    says = {"kind": "answer", "person": "브람", "bio": "", "attitude": "", "said": None, "quiet": False,
            "says": ["징수관 나리가 집에 오셨었다.", "내가 잔 둘을 내갔다."], "lines": ["징수관 나리가 집에 오셨었다.", "내가 잔 둘을 내갔다."]}
    passing = {"added": {"noul": 0.1}, "meaning": {"noul": 0.9}}
    assert judge(says, passing, "그건... 제가 잘 모르겠어요...")[0] == ["meaning"]   # qa-5 turn 46
    assert judge(says, passing, "사실 징수관 나리가 집에 오셨었어요.")[0] == ["meaning"]   # the second line dropped
    assert judge(says, passing, "사실 징수관 나리가 집에 오셨었어요... 제가 잔을 둘이나 내갔는걸요.")[0] == []


def test_a_pass_need_not_echo_its_words():
    # "답할 것이 없다" is an instruction, not a line; asking its syllables back gave "무슨 소리냐" every time
    job = {"kind": "answer", "person": "최두식", "said": "담배 하나 꽂아봐라", "says": ["답할 것이 없다"], "lines": [],
           "quiet": True}
    assert set(make_checks(job)) == {"added", "quiet"}
    assert judge(job, {"added": {"noul": 0.1}, "quiet": {"noul": 0.9}}, "옜다, 한 대만 피우고 정신 차려라.")[0] == []


def test_the_dm_shows_a_sign_in_합니다체_without_advice_or_invented_speech():
    dm, low = {"kind": "dm", "key": "unvisited"}, {"added": {"noul": 0.1}}
    assert judge(dm, low, "그에게 물어보도록 하세요.")[0] == ["style"]
    assert judge(dm, low, "점잖은 얼굴이군요. 그에게 물어보십시오.")[0] == ["style", "push"]
    assert judge(dm, low, "그가 \"모르겠어요\" 하고 고개를 젓습니다.")[0] == ["speech"]
    assert judge(dm, low, "아직 가 보지 않은 경기장으로 가 보길 권합니다.")[0] == ["push"]
    assert judge(dm, low, "경기장 쪽에서 함성이 한 차례 터져 나옵니다.")[0] == []
    assert judge({"kind": "dm", "key": "conclude"}, low, "공이 울립니다. 당신의 결론을 들려주십시오.")[0] == []
    # Help names what it points at; only the ready cue may say it is time to weigh things up (game/07 2절).
    hint = {"kind": "dm", "key": "hint_topic", "leads": ["6시 반"]}
    assert judge(hint, low, "최두식이 자꾸 시계를 봅니다.")[0] == ["lead"]
    assert judge(hint, low, "최두식이 6시 반 이야기를 꺼내고 싶은 눈치입니다.")[0] == []
    assert judge({"kind": "dm", "key": "ready"}, low, "조각이 다 모인 듯합니다. 이제 따져 보는 게 좋겠습니다.")[0] == []


def test_narration_in_해라체_is_written_again():
    low = {"added": {"noul": 0.1}}
    assert judge({"kind": "scene"}, low, "풀 냄새가 납니다. 넬은 처마 밑에서 풀 다발을 뒤집어 건다.")[0] == ["style"]   # research2-text-dawn
    assert judge({"kind": "scene"}, low, "넬이 처마 밑에서 풀 다발을 뒤집어 겁니다. \"됐다.\" 하고 중얼거립니다.")[0] == []
    assert judge({"kind": "answer", "says": [], "lines": [], "quiet": False}, low, "됐다. 가 보거라.")[0] == []


def test_brackets_are_written_again_in_every_kind():
    low = {"added": {"noul": 0.1}, "quiet": {"noul": 0.9}}
    scene = {"kind": "scene"}
    assert judge(scene, low, "대기실입니다. 최두식(빈 벨트 케이스 앞을 서성인다)")[0] == ["bracket"]   # research-text-arena
    assert judge(scene, low, "대기실입니다. 최두식이 빈 벨트 케이스 앞을 서성입니다.")[0] == []
    answer = {"kind": "answer", "says": ["답할 것이 없다"], "lines": [], "quiet": True}
    assert judge(answer, low, "(나무 뒤에서 눈을 깜빡이며) 그런 건 잘 모르겠어요.")[0] == ["bracket"]


def test_an_answer_that_repeats_an_earlier_one_is_written_again():
    job = {"kind": "answer", "says": [], "lines": [], "quiet": False,
           "recent": [{"said": "후.... 내가 이자리 까지 어떻게 올라왔는지 아냐",
                       "answer": "봉식아, 갑자기 왜 그래? 옛날 얘기는 이제 그만하고 술이나 한잔하자."}]}
    low = {"added": {"noul": 0.1}}
    assert judge(job, low, "봉식아, 갑자기 왜 그래? 옛날 얘기는 이제 그만하고 술이나 한잔하자.")[0] == ["repeat"]   # react-replay 턴 5
    assert judge(job, low, "힘들면 오늘은 내가 링 밖에서 다 막아 줄 테니까 숨 좀 돌려.")[0] == []


def test_a_line_said_for_the_first_time_is_not_called_said_before():
    job = {"kind": "answer", "says": ["벨트는 6시까지 케이스에 있었다."], "lines": ["벨트는 6시까지 케이스에 있었다."],
           "told": [], "quiet": False}
    low = {"added": {"noul": 0.1}, "meaning": {"noul": 0.9}}
    assert judge(job, low, "봉식아, 내가 아까 말했잖아. 벨트는 6시까지 케이스에 있었다니까!")[0] == ["again"]   # react-impress-rude 턴 2
    assert judge({**job, "told": job["lines"]}, low, "봉식아, 내가 아까 말했잖아. 벨트는 6시까지 케이스에 있었다니까!")[0] == []


def test_a_lead_names_its_topic_word_for_word():
    job = {"kind": "answer", "says": ["답할 것이 없다"], "lines": [], "quiet": True, "leads": ["벨트"]}
    low = {"added": {"noul": 0.1}, "quiet": {"noul": 0.9}}
    # c4aae5 턴 5: the lead was in the job and the answer never named it
    assert judge(job, low, "봉식아, 내가 지금 제정신이겠냐? 머리만 아파서 죽겠는데.")[0] == ["lead"]
    assert judge(job, low, "봉식아, 벨트 얘기라면 나도 아는 게 좀 있다.")[0] == []


def test_the_text_kept_is_never_a_repeat_when_another_draft_is_not():
    checks = [{"text": "같은 말", "failed": ["repeat"]}, {"text": "다른 말", "failed": ["added", "length"]},
              {"text": "같은 말", "failed": ["repeat"]}]
    assert pick_best(checks) == "다른 말"
    assert pick_best([{"text": "첫 글", "failed": []}]) == "첫 글"


def test_a_person_is_played_from_what_their_type_means_not_its_four_letters():
    assert set(MBTI) == {"".join(t) for t in product("EI", "SN", "TF", "JP")}
    job = {"kind": "answer", "person": "브람", "bio": "여관 주인", "mbti": "ISTP", "attitude": "", "said": "누구요?",
           "says": [], "lines": [], "quiet": False}
    assert MBTI["ISTP"] in make_messages(job)[0]["content"]


def test_a_text_naming_someone_the_player_has_not_met_and_was_not_given_fails():
    job = {"kind": "answer", "person": "브람", "bio": "여관 주인", "attitude": "", "said": "누구요?", "says": [], "lines": [],
           "quiet": False, "unknown": ["고드릭", "약초꾼 오두막"]}
    low = {"added": {"noul": 0.1}}
    assert judge(job, low, "고드릭 나리라면 알지도 모르지.")[0] == ["unknown"]
    assert judge(job, low, "난 모르오.")[0] == []
    assert judge({**job, "said": "고드릭은 어디 있소?"}, low, "고드릭 나리라면 집에 있소.")[0] == []

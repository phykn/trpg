from src.narrate import count_sentences, judge, make_checks


def test_a_text_fails_on_low_checks_and_on_length():
    job = {"kind": "answer", "person": "브람", "bio": "", "attitude": "", "said": None, "says": ["말"], "lines": ["말"],
           "quiet": False}
    assert set(make_checks(job)) == {"added", "meaning"}
    assert judge(job, {"added": {"noul": 0.2}, "meaning": {"noul": 0.8}}, "한 말.") == (
        [], {"added": 0.2, "meaning": 0.8})
    assert judge(job, {"added": {"noul": 0.9}, "meaning": {"noul": 0.4}}, "하나. 둘! 셋? 넷.")[0] == [
        "added", "meaning", "length"]
    assert count_sentences("……알았소, 그렇다면 말하리다. 해 지기 전에 떠났소") == 2
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


def test_an_answer_that_repeats_an_earlier_one_is_written_again():
    job = {"kind": "answer", "says": [], "lines": [], "quiet": False,
           "recent": [{"said": "후.... 내가 이자리 까지 어떻게 올라왔는지 아냐",
                       "answer": "봉식아, 갑자기 왜 그래? 옛날 얘기는 이제 그만하고 술이나 한잔하자."}]}
    low = {"added": {"noul": 0.1}}
    assert judge(job, low, "봉식아, 갑자기 왜 그래? 옛날 얘기는 이제 그만하고 술이나 한잔하자.")[0] == ["repeat"]   # react-replay 턴 5
    assert judge(job, low, "힘들면 오늘은 내가 링 밖에서 다 막아 줄 테니까 숨 좀 돌려.")[0] == []

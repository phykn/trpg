from conftest import FakeKev, FakeQwen, noul
from src.models.kev import ModelUnavailable
from src.narrate import Narrator, TagFilter, form_feedback, messages, repeated
from src.rules import dsl
from src.rules.resolve import resolve
from src.world.state import ActionStep, ImproviseStep


def test_tag_filter_hides_name_lines():
    f = TagFilter({"t1_1"})
    shown = f.feed("바람이 붑니다.\n@t1_") + f.feed("1 젖은 계단\n@t9_9 남의 것\n끝.")
    f.finish()
    assert shown == "바람이 붑니다.\n끝."
    assert f.names == {"t1_1": "젖은 계단"}


def test_tag_filter_ignores_long_names():
    f = TagFilter({"t1_1"})
    f.feed("@t1_1 " + "가" * 20)
    f.finish()
    assert f.names == {}


def test_messages_carry_facts_changes_and_naming(loaded, state):
    story = loaded.story
    out = []
    dsl.move(state, "player", "base", out)
    state.seed = 2
    new, record = resolve(story, state, [ImproviseStep(purpose="setup", target="door", approach="wits")], "녹을 턴다")
    msgs = messages(story, loaded.style, new, record)
    user = msgs[1]["content"]
    assert msgs[0]["role"] == "system" and "합니다체" in msgs[0]["content"]
    assert "[사실]" in user and "[바뀐 것]" in user and "녹을 턴다" in user
    if any(c.kind == "tag_add" for s in record.steps for c in s.changes):
        assert "[이름 짓기]" in user


async def collect(narrator, loaded, state, record):
    return [e async for e in narrator.narrate(loaded.story, loaded.style, state, record)]


async def test_narration_passes_the_check(loaded, state):
    narrator = Narrator(FakeQwen(["당신은 광장에 있습니다.\n@t1_1 이름"]), FakeKev())
    events = await collect(narrator, loaded, state, state.turns[0])
    assert events[-1] == {"type": "done", "text": "당신은 광장에 있습니다.", "tags": {}}
    assert all("@" not in e.get("text", "") for e in events)


async def test_failed_check_resets_and_rewrites(loaded, state):
    kev = FakeKev({"invents": noul(True)})
    qwen = FakeQwen(["새 상인이 나타납니다.", "광장은 조용합니다."])
    narrator = Narrator(qwen, kev)
    calls = {"n": 0}
    original = kev.decide

    async def decide(text, questions):
        calls["n"] += 1
        if calls["n"] > 1:
            kev.answers = {}
        return await original(text, questions)

    kev.decide = decide
    events = await collect(narrator, loaded, state, state.turns[0])
    kinds = [e["type"] for e in events]
    assert "reset" in kinds and kinds[-1] == "done"
    assert "[고칠 점]" in qwen.calls[1][1]["content"]


async def test_three_failures_end_in_error(loaded, state):
    narrator = Narrator(FakeQwen(["틀림"]), FakeKev({"contradicts": noul(True)}))
    events = await collect(narrator, loaded, state, state.turns[0])
    assert [e["type"] for e in events].count("reset") == 3
    assert events[-1] == {"type": "error", "retry": True}


async def test_low_confidence_complaint_passes(loaded, state):
    narrator = Narrator(FakeQwen(), FakeKev({"contradicts": noul(True, 0.2)}))
    events = await collect(narrator, loaded, state, state.turns[0])
    assert events[-1]["type"] == "done"


async def test_model_error_propagates(loaded, state):
    narrator = Narrator(FakeQwen(error=ModelUnavailable("down")), FakeKev())
    try:
        await collect(narrator, loaded, state, state.turns[0])
    except ModelUnavailable:
        return
    raise AssertionError("expected ModelUnavailable")


def test_opening_turn_uses_the_intro(loaded, state):
    user = messages(loaded.story, loaded.style, state, state.turns[0])[1]["content"]
    assert loaded.story.intro in user and "[플레이어 입력]" not in user
    new, record = resolve(loaded.story, state, [ActionStep(action_id="inspect:mira")], "본다")
    assert "[플레이어 입력]" in messages(loaded.story, loaded.style, new, record)[1]["content"]


def test_repeated_lists_copied_sentences():
    previous = "안개가 짙습니다. 여울이 당신을 바라봅니다. \"누구인가요?\""
    assert repeated("여울이 당신을 바라봅니다. 그리고 웃습니다.", previous) == ["여울이 당신을 바라봅니다."]
    assert repeated("여울이 고개를 끄덕입니다. 안개가 걷힙니다.", previous) == []
    assert repeated("무엇이든.", None) == []


def test_tag_filter_hides_quoted_and_misplaced_tag_lines():
    f = TagFilter({"t4_1"})
    shown = f.feed("\"증거입니다.\"\n'@t4_1 젖은 잉크'\n")
    assert f.finish() == ""
    assert shown == "\"증거입니다.\"\n"
    assert f.names == {"t4_1": "젖은 잉크"}
    assert f.scrub("끝입니다.\n'부두 광장 @t4_1'") == "끝입니다."


async def test_copied_narration_is_rewritten_but_never_fails_alone(loaded, state):
    old = "여울이 명단을 다시 읽습니다. 그가 종이를 단단히 쥡니다."
    state.turns[0].narration = old
    new, record = resolve(loaded.story, state, [ActionStep(action_id="inspect:mira")], "본다")
    qwen = FakeQwen([old])
    events = await collect(Narrator(qwen, FakeKev()), loaded, new, record)
    assert [e["type"] for e in events].count("reset") == 2
    assert events[-1]["type"] == "done"
    assert "여울이 명단을 다시 읽습니다." in qwen.calls[1][1]["content"].split("[고칠 점]")[1]
    assert len(set(qwen.seeds)) == 3 and None not in qwen.seeds, "each attempt samples differently"


def test_previous_scene_is_left_out_after_a_move(loaded, state):
    state.turns[0].narration = "여울이 묻습니다. \"나루의 죄목은 무엇입니까?\""
    stay, record = resolve(loaded.story, state, [ActionStep(action_id="inspect:mira")], "본다")
    assert "나루의 죄목" in messages(loaded.story, loaded.style, stay, record)[1]["content"]
    gone, record = resolve(loaded.story, state, [ActionStep(action_id="move:base")], "간다")
    assert "나루의 죄목" not in messages(loaded.story, loaded.style, gone, record)[1]["content"]


def test_form_feedback_flags_foreign_script_and_length():
    assert form_feedback("손이 微微 떨립니다.", None)
    assert form_feedback("바람이 붑니다. " * 10, None)
    assert form_feedback("바람이 붑니다. 종이 울립니다. \"누구인가요?\"", None) == ""
    assert form_feedback("여울이 고개를 끄덕입니다.", None, ["정정 명령서"])
    assert form_feedback("여울이 정정 명령서를 건넵니다.", None, ["정정 명령서"]) == ""
    assert form_feedback("모라가 고개를 끄덕였다. \"알고 있다.\" 종소리가 들린다.", None)
    assert form_feedback("모라가 말합니다. \"알고 있다. 그건 안 된다.\"", None) == "", "speech may be plain"


async def test_last_attempt_keeps_text_but_drops_foreign_script(loaded, state):
    qwen = FakeQwen(["손이 微微 떨립니다. 종이 울립니다."])
    events = await collect(Narrator(qwen, FakeKev()), loaded, state, state.turns[0])
    assert [e["type"] for e in events].count("reset") == 2
    assert events[-1]["text"] == "손이 떨립니다. 종이 울립니다."


def test_tag_filter_cuts_an_echoed_prompt():
    f = TagFilter(set())
    shown = f.feed("종이 울립니다.\n[사실 확인 중인 문장]은 그대로 둡니다.\n\n[직전 장면의") + f.feed(" 끝] (이미 보여 줌)\n여울이 봅니다.\n")
    shown += f.finish()
    assert shown == "종이 울립니다.\n[사실 확인 중인 문장]은 그대로 둡니다.\n\n"


def test_rewards_not_yet_earned_are_flagged_by_their_stem():
    assert "정정 명령서" in form_feedback("여울이 정정 명령을 내립니다.", None, unearned=["정정 명령서"])
    assert form_feedback("여울이 고개를 끄덕입니다.", None, unearned=["정정 명령서"]) == ""


def test_small_talk_says_nothing_changed(loaded, state):
    from src.scene.render import record_lines
    from src.world.state import TalkStep
    new, record = resolve(loaded.story, state, [TalkStep(character="mira")], "안녕하세요")
    assert record_lines(loaded.story, new, record)[-1] == "말이 오갔지만 바뀐 것은 없습니다"


def test_handing_over_a_held_item_is_flagged():
    from src.narrate import handed
    assert handed("당신은 마른 붕대를 건넵니다. 도윤이 받습니다.", ["마른 붕대"]) == ["마른 붕대"]
    assert handed("당신의 주머니에 마른 붕대가 있습니다.", ["마른 붕대"]) == []


async def test_out_of_attempts_keeps_the_least_flawed_draft(loaded, state):
    drafts = ["손이 微微 차다. 종이 붉다.", "손이 찹니다. 종이 붉다.", "손이 微微 차다. 종이 붉다."]
    events = await collect(Narrator(FakeQwen(drafts), FakeKev()), loaded, state, state.turns[0])
    assert events[-1] == {"type": "done", "text": "손이 찹니다. 종이 붉다.", "tags": {}}


def test_a_sentence_written_twice_is_flagged():
    text = "이든은 당신을 보지 않은 체합니다. 루가 고개를 듭니다. 이든은 당신을 보지 않은 체합니다."
    assert "두 번" in form_feedback(text, None)


def test_plain_endings_become_polite_outside_quotes():
    from src.locale import ko
    from src.narrate import QUOTED
    text = '당신은 명령서를 내민다. 도윤이 잡는다. 문이 열렸다. "가자, 빨리 간다." 길이 없다.'
    assert ko.polite(text, QUOTED) == '당신은 명령서를 내밉니다. 도윤이 잡습니다. 문이 열렸습니다. "가자, 빨리 간다." 길이 없습니다.'
    assert ko.polite("눈앞에 넓은 바다. 그는 크다.", QUOTED) == "눈앞에 넓은 바다. 그는 크다."


def test_broken_letters_are_rewritten():
    assert "깨진" in form_feedback("이건� 유효하군.", None)


def test_the_player_is_never_called_neo_outside_quotes():
    assert "당신" in form_feedback("너의 손길에 그가 떱니다.", None)
    assert form_feedback('그가 말합니다. "너의 손을 잡겠습니다."', None) == ""


def test_an_ending_scene_is_told_to_close(loaded, state):
    state.ending = loaded.story.endings[0].id
    user = messages(loaded.story, loaded.style, state, state.turns[0])[1]["content"]
    assert "[결말]" in user and loaded.story.endings[0].title in user


def test_an_echoed_change_list_is_dropped():
    f = TagFilter(set())
    assert f.scrub("문이 열립니다.\n- 철사로 자물쇠를 땁니다\n- 잠긴 등대 문") == "문이 열립니다."


def test_a_new_chapter_opens_without_a_player_action(loaded, state):
    from src.world.state import Change, TurnRecord
    record = TurnRecord(n=1, input="재주 1→2", changes=[Change(kind="chapter", target="ch_light", after="ch_light")])
    state.turns.append(record)
    user = messages(loaded.story, loaded.style, state, record)[1]["content"]
    assert "[새 장]" in user and "[플레이어 입력]" not in user


def test_handling_an_item_nobody_mentioned_is_flagged():
    from src.narrate import form_problems
    said = "자물쇠를 철사로 딴다"
    bad = form_problems("철사가 들어갑니다. 당신은 기름통의 뚜껑을 열었습니다.", None, items=["기름통"], said=said)
    assert any("기름통" in p for p in bad)
    assert form_problems("기름통이 구석에 놓여 있습니다.", None, items=["기름통"], said=said) == []


def test_a_companion_out_of_nowhere_is_flagged():
    from src.narrate import form_problems
    assert form_problems("동행한 인물이 묻습니다.", None, alone=True)
    assert not form_problems("동행한 인물이 묻습니다.", None, alone=False)


def test_she_is_flagged_when_everyone_here_is_he():
    from src.narrate import form_problems
    assert form_problems("그녀가 고개를 듭니다.", None, no_she=True)
    assert not form_problems('그가 말합니다. "그녀는 떠났소."', None, no_she=True)


def test_first_person_outside_quotes_is_flagged():
    assert "당신" in form_feedback("이제 우리는 감옥을 벗어났습니다.", None)
    assert form_feedback('나루가 말합니다. "우리는 살았어."', None) == ""


def test_the_ending_text_is_not_repeated_in_the_scene(loaded, state):
    from src.narrate import sentences, without_ending
    ending = loaded.story.endings[0]
    state.ending = ending.id
    first = sentences(ending.text)[0]
    text = f"바람이 붑니다.\n\n{ending.title}: {ending.text}\n\n{first}"
    assert without_ending(loaded.story, state, text) == "바람이 붑니다."


def test_numbers_and_rule_words_are_flagged():
    assert "숫자" in form_feedback("출항 준비가 3/8로 차오릅니다.", None)
    assert "숫자" in form_feedback("배를 훔쳐 탑니다. 성공입니다.", None)
    assert form_feedback('그가 말합니다. "판정은 끝났소."', None) == ""

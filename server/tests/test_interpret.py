from conftest import FakeKev, choice, noul
from src.interpret import (
    Clarify,
    Rejected,
    Steps,
    assemble,
    detail_questions,
    interpret,
    questions,
    step_questions,
)
from src.rules import dsl
from src.rules.candidates import candidates
from src.scene.build import build
from src.world.state import ActionStep, ImproviseStep, TalkStep


def ask(story, state):
    return questions(story, state, build(story, state), candidates(story, state))


def run(story, state, answers):
    return assemble(story, state, candidates(story, state), answers)


def at_base(state):
    dsl.move(state, "player", "base", [])
    return state


def test_first_step_has_no_none_and_later_steps_do(story, state):
    q = ask(story, state)
    first = q["s1"]["criteria"]
    assert "move:base" in first and "improvise" in first and "none" not in first
    assert not any(k.startswith(("solve:", "use_tag:", "topic:")) for k in first)
    assert "none" in q["s2"]["criteria"] and "none" in q["s3"]["criteria"]
    assert "s1.uses.tag" not in q, "no edge tags, so the question has only 'none'"
    assert set(q["talk.topic"]["criteria"]) == {"topic_key_mira", "topic_lamp_mira", "chat"}


def test_target_options_never_offer_none(story, state):
    state = at_base(state)
    snag = dsl.add_tag(state, "snag", "door", [])
    assert set(ask(story, state)["s1.target"]["criteria"]) == {"door", snag.id}


def test_low_confidence_first_choice_is_still_taken(story, state):
    answers = {"s1": choice("move:base", 0.26, {"move:base": 0.26, "talk:mira": 0.2})}
    assert run(story, state, answers) == Steps(steps=[ActionStep(action_id="move:base")])


def test_close_choices_of_the_same_kind_ask_back(story, state):
    answers = {"s1": choice("talk:mira", 0.4, {"talk:mira": 0.4, "talk:doha": 0.35, "improvise": 0.25})}
    result = run(story, state, answers)
    assert isinstance(result, Clarify)
    assert [k for k, _ in result.options] == ["talk:mira", "talk:doha"]


def test_nearly_tied_concrete_readings_ask_back(story, state):
    answers = {"s1": choice("talk:mira", 0.4, {"talk:mira": 0.4, "move:base": 0.38})}
    assert [k for k, _ in run(story, state, answers).options] == ["talk:mira", "move:base"]
    clear = {"s1": choice("talk:mira", 0.6, {"talk:mira": 0.6, "move:base": 0.3})}
    assert isinstance(run(story, state, clear), Steps)
    loose = {"s1": choice("talk:mira", 0.4, {"talk:mira": 0.4, "improvise": 0.38})}
    assert isinstance(run(story, state, loose), Steps), "an improvise reading is not a concrete choice"


def test_a_single_obstacle_is_the_target_without_asking_kev(story, state):
    state = at_base(state)
    answers = {"s1": choice("improvise"), "s1.approach": choice("force")}
    step = run(story, state, answers).steps[0]
    assert isinstance(step, ImproviseStep) and step.target == "door" and step.check


def test_rules_decide_roll_purpose_and_risk(story, state):
    calm = run(story, state, {"s1": choice("improvise")}).steps[0]
    assert calm.target is None and not calm.check, "nothing to act on here, so no roll"
    state = at_base(state)
    door = run(story, state, {"s1": choice("improvise")}).steps[0]
    assert door.target == "door" and door.check and door.purpose == "overcome" and door.risk == "normal"
    snag = dsl.add_tag(state, "snag", "door", [])
    answers = {"s1": choice("improvise"), "s1.target": choice(snag.id)}
    assert run(story, state, answers).steps[0].purpose == "clear"


def test_only_a_sure_impossible_is_rejected(story, state):
    sure = {"s1": choice("improvise"), "s1.plausible": choice("impossible", 0.9)}
    assert run(story, state, sure) == Rejected(reason="지금의 당신으로는 할 수 없는 일입니다.")
    unsure = {"s1": choice("improvise"), "s1.plausible": choice("impossible", 0.5)}
    assert run(story, state, unsure).steps[0].plausibility == "stretch"


def test_later_steps_must_differ_and_be_likely(story, state):
    repeat = {"s1": choice("move:base"), "s2": choice("move:base", 0.6)}
    assert run(story, state, repeat).steps == [ActionStep(action_id="move:base")]
    weak = {"s1": choice("take:bread"), "s2": choice("give:mira:bread", 0.15)}
    assert run(story, state, weak).steps == [ActionStep(action_id="take:bread")]
    chain = {"s1": choice("take:bread"), "s2": choice("move:base", 0.4), "s3": choice("none")}
    assert [s.action_id for s in run(story, state, chain).steps] == ["take:bread", "move:base"]


def test_talk_step_keeps_only_the_partners_topics_and_known_lies(story, state):
    answers = {
        "s1": choice("talk:doha"), "talk.topic": choice("topic_key_mira"), "talk.attitude": choice("deceive"),
        "talk.claim": noul(True), "talk.lie.kn_lamp_trick": choice("deny"), "talk.touch": choice("fear"),
    }
    step = run(story, state, answers).steps[0]
    assert isinstance(step, TalkStep)
    assert step.topic == "chat", "topic_key_mira belongs to mira"
    assert step.contradicts is None, "doha does not know the lamp trick"
    assert step.claim and step.attitude == "deceive" and step.touch == "fear"


async def test_listed_actions_need_one_call_with_only_step_questions(story, state):
    kev = FakeKev({"s1": choice("move:base")})
    result = await interpret(kev, story, state, "등대로 간다")
    assert result.steps == [ActionStep(action_id="move:base")]
    assert len(kev.calls) == 1 and kev.calls[0][0] == "등대로 간다"
    assert set(kev.calls[0][1]) == {"s1", "s2", "s3"}


async def test_improvise_asks_its_details_in_a_second_call(story, state):
    kev = FakeKev({"s1": choice("improvise"), "s1.approach": choice("wits"), "s1.plausible": choice("natural")})
    result = await interpret(kev, story, state, "우물 도르래를 감아 본다")
    assert result.steps[0].approach == "wits"
    assert len(kev.calls) == 2
    assert "s1.approach" in kev.calls[1][1] and "s2.approach" not in kev.calls[1][1]
    assert not any(k.startswith("talk.") for k in kev.calls[1][1])


async def test_talk_details_cover_only_the_chosen_partner(story, state):
    kev = FakeKev({"s1": choice("talk:doha")})
    await interpret(kev, story, state, "도하에게 묻는다")
    details = kev.calls[1][1]
    assert set(details["talk.topic"]["criteria"]) == {"topic_key_doha", "chat"}
    assert not any(k.startswith("s1.") for k in details)


def test_lie_needs_a_sure_denial_of_a_known_fact(story, state):
    base = {"s1": choice("talk:doha"), "talk.claim": noul(True)}
    agree = run(story, state, {**base, "talk.lie.kn_spare_key": choice("agree")}).steps[0]
    assert agree.contradicts is None, "agreeing with a fact is not a lie"
    unsure = run(story, state, {**base, "talk.lie.kn_spare_key": choice("deny", 0.3)}).steps[0]
    assert unsure.contradicts is None
    deny = run(story, state, {**base, "talk.lie.kn_spare_key": choice("deny")}).steps[0]
    assert deny.contradicts == "kn_spare_key"


def test_unsure_claim_is_not_a_claim(story, state):
    step = run(story, state, {"s1": choice("talk:doha"), "talk.claim": noul(True, 0.2)}).steps[0]
    assert not step.claim


def test_each_known_fact_gets_its_own_stance_question(story, state):
    scene = build(story, state)
    q = detail_questions(story, scene, ["talk:mira"])
    assert {"talk.lie.kn_spare_key", "talk.lie.kn_lamp_trick"} <= set(q)
    assert set(q["talk.lie.kn_spare_key"]["criteria"]) == {"agree", "deny", "none"}


def test_a_verb_naming_an_approach_overrides_kev(story, state):
    state = at_base(state)
    answers = {"s1": choice("improvise"), "s1.target": choice("door"), "s1.approach": choice("wits")}
    result = assemble(story, state, candidates(story, state), answers, "문을 힘껏 밀어 연다")
    assert result.steps[0].approach == "force"


def test_an_obstacle_look_with_an_action_verb_is_an_attempt(story, state):
    state = at_base(state)
    answers = {"s1": choice("inspect:door")}
    result = assemble(story, state, candidates(story, state), answers, "자물쇠를 몰래 따고 들어간다")
    assert result.steps[0] == ImproviseStep(purpose="overcome", target="door", approach="finesse", risk="normal",
                                            plausibility="natural", check=True)
    plain = assemble(story, state, candidates(story, state), answers, "문을 자세히 살펴본다")
    assert plain.steps[0] == ActionStep(action_id="inspect:door")


async def test_words_to_a_named_person_are_talk(story, state):
    kev = FakeKev({"s1": choice("move:base"), "talk.topic": choice("chat")})
    result = await interpret(kev, story, state, "미라에게 등대로 가는 길을 묻는다")
    assert isinstance(result.steps[0], TalkStep) and result.steps[0].character == "mira"
    assert "talk.topic" in kev.calls[1][1], "the talk details are asked for the person named"


def test_talk_aimed_at_an_obstacle_becomes_an_attempt(story, state):
    state = at_base(state)
    dsl.move(state, "mira", "base", [])
    cands = candidates(story, state)
    aimed = {"s1": choice("talk:mira"), "talk.topic": choice("chat"), "talk.approach": choice("charm"),
             "talk.press": choice("door", 0.45, {"door": 0.45, "none": 0.55})}
    result = assemble(story, state, cands, aimed, "미라에게 문을 열어 달라고 한다")
    assert result.steps[0].kind == "improvise" and result.steps[0].target == "door"
    idle = {**aimed, "talk.press": choice("none", 0.8, {"door": 0.2, "none": 0.8})}
    assert assemble(story, state, cands, idle, "미라에게 날씨 얘기를 한다").steps[0].kind == "talk"


def test_naming_the_thing_a_solution_needs_uses_that_solution(story, state):
    state = at_base(state)
    dsl.give(state, "spare_key", [])
    answers = {"s1": choice("improvise"), "s1.target": choice("door"), "s1.approach": choice("force")}
    result = assemble(story, state, candidates(story, state), answers, "예비 열쇠를 꽂아 돌린다")
    assert result.steps[0] == ActionStep(action_id="solve:door:0")


def test_a_gift_goes_only_to_the_person_spoken_to(story, state):
    dsl.give(state, "spare_key", [])
    answers = {"s1": choice("talk:mira"), "s2": choice("give:doha:spare_key", 0.5), "talk.topic": choice("chat")}
    result = assemble(story, state, candidates(story, state), answers, "미라에게 예비 열쇠를 보여 주며 도하를 데려가라고 한다")
    assert [s.kind for s in result.steps] == ["talk"]


def test_a_named_place_is_reached_along_open_exits(story, state):
    from src.interpret import route
    answers = {"s1": choice("inspect:mira")}
    result = assemble(story, state, candidates(story, state), answers, "등대 아래로 걸어간다")
    assert result.steps == [ActionStep(action_id="move:base")]
    assert route(state, story, "등대 꼭대기로 간다") is None, "the way up is still locked"
    dsl.set_exit(state, "base", "top", True, [])
    assert route(state, story, "등대 꼭대기로 간다") == ["move:base", "move:top"]


def test_every_hop_of_a_route_is_kept(story, state):
    dsl.set_exit(state, "base", "top", True, [])
    result = assemble(story, state, candidates(story, state), {"s1": choice("inspect:mira")}, "등대 꼭대기로 올라간다")
    assert result.steps == [ActionStep(action_id="move:base"), ActionStep(action_id="move:top")]


def test_a_sentence_close_to_a_solution_label_is_that_solution(story, state):
    state = at_base(state)
    answers = {"s1": choice("improvise"), "s1.target": choice("door")}
    result = assemble(story, state, candidates(story, state), answers, "철사로 자물쇠를 따 본다")
    assert result.steps[0] == ActionStep(action_id="solve:door:2")


def test_a_named_topic_is_not_small_talk(story, state):
    title = next(t.title for t in story.topics if t.id == "topic_key_mira")
    answers = {"s1": choice("talk:mira"), "talk.topic": choice("chat")}
    result = assemble(story, state, candidates(story, state), answers, f"미라에게 {title}에 대해 묻는다")
    assert result.steps[0].topic == "topic_key_mira"


def test_a_gift_needs_a_giving_verb(story, state):
    dsl.give(state, "spare_key", [])
    cands = candidates(story, state)
    answers = {"s1": choice("move:base"), "s2": choice("give:mira:spare_key", 0.5)}
    read = assemble(story, state, cands, answers, "예비 열쇠를 만지작거리며 걸음을 옮긴다")
    assert read.steps == [ActionStep(action_id="move:base")]
    gift = assemble(story, state, cands, answers, "걸음을 옮기기 전에 미라에게 예비 열쇠를 건넨다")
    assert gift.steps[0] == ActionStep(action_id="give:mira:spare_key"), "the final verb is the deed: give first"


def test_words_to_a_person_walk_nowhere(story, state):
    answers = {"s1": choice("talk:mira"), "s2": choice("move:base", 0.5), "talk.topic": choice("chat")}
    result = assemble(story, state, candidates(story, state), answers, "미라에게 등대로 들어가는 길을 묻는다")
    assert [s.kind for s in result.steps] == ["talk"]


async def test_what_the_world_forbids_is_turned_back_without_kev(story, state):
    kev = FakeKev()
    assert isinstance(await interpret(kev, story, state, "하늘을 날아 등대로 간다"), Rejected)
    assert isinstance(await interpret(kev, story, state, "점심 메뉴 추천해줘"), Rejected)
    assert kev.calls == []
    assert not isinstance(await interpret(kev, story, state, "미라에게 등대 이야기를 알려줘"), Rejected)


def test_an_impossible_phrase_may_not_block_a_button(story):
    from src.content.validate import validate
    bad = story.model_copy(update={"impossible": [story.obstacles["door"].solutions[0].label[:4]]})
    assert any(e.startswith("impossible:") for e in validate(bad))


def test_attitude_and_claim_come_from_the_words(story, state):
    answers = {"s1": choice("talk:mira"), "talk.topic": choice("chat"), "talk.attitude": choice("polite")}
    lie = assemble(story, state, candidates(story, state), answers, "미라에게 내가 등대 관리인이라고 거짓말한다")
    assert lie.steps[0].attitude == "deceive" and lie.steps[0].claim
    plain = assemble(story, state, candidates(story, state), answers, "미라에게 안부를 묻는다")
    assert plain.steps[0].attitude == "polite" and not plain.steps[0].claim


def test_the_verb_tells_a_look_from_a_grab(story, state):
    answers = {"s1": choice("take:bread", 0.36, {"take:bread": 0.36, "inspect:bread": 0.31})}
    look = assemble(story, state, candidates(story, state), answers, "갓 구운 빵을 살펴본다")
    assert look.steps == [ActionStep(action_id="inspect:bread")]


def test_named_gift_comes_first(story, state):
    dsl.give(state, "spare_key", [])
    answers = {"s1": choice("move:base")}
    result = assemble(story, state, candidates(story, state), answers, "미라에게 예비 열쇠를 주고 등대 아래로 간다")
    assert result.steps[0] == ActionStep(action_id="give:mira:spare_key")


def test_looking_at_the_sky_is_not_an_attempt(story, state):
    state = at_base(state)
    answers = {"s1": choice("improvise"), "s1.target": choice("door")}
    result = assemble(story, state, candidates(story, state), answers, "흐린 하늘을 올려다본다")
    assert result.steps[0].check is False and result.steps[0].target is None


def test_taking_a_guarded_thing_is_an_attempt_on_its_guard(story, state):
    state = at_base(state)
    door = story.obstacles["door"]
    story.obstacles["door"] = door.model_copy(update={"guards": ["bread"]})
    dsl.move(state, "bread", "base", [])
    answers = {"s1": choice("inspect:bread")}
    result = assemble(story, state, candidates(story, state), answers, "문지기가 한눈판 틈에 빵을 몰래 빼낸다")
    assert result.steps[0].kind == "improvise" and result.steps[0].target == "door"


def test_plain_words_settle_what_kev_would_ask_back(story, state):
    state = at_base(state)
    dsl.give(state, "spare_key", [])
    torn = {"s1": choice("talk:mira", 0.4, {"talk:mira": 0.4, "talk:doha": 0.35})}
    result = assemble(story, state, candidates(story, state), torn, "예비 열쇠로 문을 연다")
    assert result.steps[0] == ActionStep(action_id="solve:door:0")


def test_a_trait_called_by_name_is_used(story, state):
    from src.interpret import trait_named
    trait = story.trait(state.player.traits[0])
    word = max(trait.name.split(), key=len)
    assert trait_named(story, state, f"{word} 솜씨를 살려 문을 연다") == trait.id
    assert trait_named(story, state, "문을 연다") is None


def test_a_bare_look_is_not_an_attempt(story, state):
    state = at_base(state)
    answers = {"s1": choice("improvise"), "s1.target": choice("door")}
    assert assemble(story, state, candidates(story, state), answers, "주위를 살펴본다").steps[0].check is False
    tried = assemble(story, state, candidates(story, state), answers, "자물쇠를 슬쩍 따 본다").steps[0]
    assert tried.target == "door" and tried.check


def test_an_attempt_needs_words_that_touch_the_obstacle(story, state):
    state = at_base(state)
    answers = {"s1": choice("improvise"), "s1.target": choice("door")}
    rest = assemble(story, state, candidates(story, state), answers, "바닥에 걸터앉아 쉰다").steps[0]
    assert rest.check is False and rest.target is None
    lock = assemble(story, state, candidates(story, state), answers, "철사로 자물쇠 구멍을 쑤신다").steps[0]
    assert lock.target == "door" and lock.check


def test_calling_out_by_role_is_talk(story, state):
    answers = {"s1": choice("move:base"), "talk.topic": choice("chat")}
    result = assemble(story, state, candidates(story, state), answers, "등대지기 양반, 잠깐 이리 와 보시오")
    assert result.steps[0].kind == "talk" and result.steps[0].character == "mira"


def test_a_clause_before_a_walk_is_its_own_step(story, state):
    answers = {"s1": choice("move:base")}
    result = assemble(story, state, candidates(story, state), answers, "갓 구운 빵을 살펴보고 등대 아래로 간다")
    assert result.steps == [ActionStep(action_id="inspect:bread"), ActionStep(action_id="move:base")]


def test_a_look_finds_the_thing_its_description_names(story, state):
    answers = {"s1": choice("improvise")}
    result = assemble(story, state, candidates(story, state), answers, "갓 구운 빵 쪽을 가까이 들여다본다")
    assert result.steps == [ActionStep(action_id="inspect:bread")]


def test_hiding_a_thing_away_takes_it(story, state):
    answers = {"s1": choice("inspect:bread", 0.4, {"inspect:bread": 0.4, "take:bread": 0.3})}
    result = assemble(story, state, candidates(story, state), answers, "빵을 소매에 감춘다")
    assert result.steps == [ActionStep(action_id="take:bread")]


def test_later_look_or_take_needs_its_verb(story, state):
    answers = {"s1": choice("talk:mira"), "s2": choice("take:bread", 0.5), "talk.topic": choice("chat")}
    result = assemble(story, state, candidates(story, state), answers, "미라에게 안부를 묻는다")
    assert [s.kind for s in result.steps] == ["talk"]


async def test_qwen_settles_an_unsure_first_step(story, state):
    from conftest import FakeQwen
    from src.models.kev import ModelUnavailable
    unsure = {"s1": choice("talk:mira", 0.3, {"talk:mira": 0.3, "move:base": 0.25})}
    labels = list(step_questions(candidates(story, state))["s1"]["criteria"])
    qwen = FakeQwen([str(labels.index("move:base") + 1)])
    result = await interpret(FakeKev(unsure), story, state, "어디론가 간다", qwen)
    assert result.steps[0] == ActionStep(action_id="move:base")
    down = await interpret(FakeKev(unsure), story, state, "어디론가 간다", FakeQwen(error=ModelUnavailable("down")))
    assert not isinstance(down, Rejected), "a Qwen failure keeps Kev's reading"
    sure = {"s1": choice("talk:mira", 0.9)}
    quiet = FakeQwen(["2"])
    await interpret(FakeKev(sure), story, state, "미라와 이야기한다", quiet)
    assert quiet.calls == [], "Kev was sure: Qwen is not asked"


def test_going_back_to_a_named_place_walks(story, state):
    answers = {"s1": choice("talk:mira")}
    result = assemble(story, state, candidates(story, state), answers, "등대 아래로 돌아가 숨을 고른다")
    assert result.steps[0] == ActionStep(action_id="move:base")

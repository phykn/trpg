import random

import pytest
from conftest import skeleton_raw
from src.onto.atoms import PLAYER
from src.onto.change import Work
from src.onto.log import Delta, Log
from src.onto.universe import conforms, initial
from src.onto.view import Seen, facts_of, observe, record
from src.rules.acts import format, parse
from src.rules.candidates import active_threats, admits, candidates, held_clock, space
from src.rules.costs import pool
from src.rules.recommend import recommend
from src.rules.resolve import event_of, resolve
from src.rules.roll import DC, chance, modifiers, outcome, preview, risk, roll, rolls
from src.rules.triggers import ended
from src.story.compile import build
from src.story.validate import Run
from src.view import atom_label, changes, step_record


class Play:
    """A game in memory: admits, then resolve, then record (engine.md 7, without the service)."""

    def __init__(self, u, creation, seed=1):
        self.u, self.s, self.log, self.seed = u, initial(u, creation), Log(), seed

    @property
    def obs(self):
        return observe(self.u, self.s, self.log)

    def do(self, aid, r=None):
        a = parse(aid)
        o = self.obs
        assert admits(self.u, o, a), f"{aid} is not a candidate"
        r = r or roll(self.seed, len(self.log))
        step = resolve(self.u, self.s, self.log.hist, a, r)
        record(self.u, self.log, self.s, step.after, event_of(self.u, self.s, len(self.log), a, step))
        self.s = step.after
        return step


@pytest.fixture
def play(u, creation):
    return Play(u, creation)


@pytest.mark.parametrize("aid", [
    "go:village", "look:door", "take:oil", "give:letter:dohae", "declare:l_baek", "cut:pass", "cut:rest",
    "talk:dohae:t_oil;tone=threaten", "talk:dohae:favor", "talk:dohae:chat;claim=c_keeper;tone=deceive",
    "try:door:finesse;rely=thing:key", "try:door:force;strain=forced", "choose:g_oil:beacon",
    "pay:c_wave", "pay:engine.beat", "grow:finesse", "grow:trait:sailor:islander", "grow:scar:2",
    "try:door:finesse;rely=tag:door:1",
])
def test_canonical_ids_round_trip(aid):
    assert format(parse(aid)) == aid


def test_neutral_and_order_are_normalized():
    assert format(parse("try:door:force;strain=natural")) == "try:door:force"
    assert format(parse("talk:dohae:chat;tone=deceive;claim=c_keeper")) == "talk:dohae:chat;claim=c_keeper;tone=deceive"
    for bad in ("fly:away", "go", "go:a:b", "try:door:force;tone=friendly", "grow:scar:4", "go:x;", ""):
        with pytest.raises(ValueError):
            parse(bad)


def test_roll_is_a_function_of_seed_and_turn():
    assert roll(5, 3) == roll(5, 3)
    d1, d2, u_ = roll(5, 3)
    assert 1 <= d1 <= 6 and 1 <= d2 <= 6 and 0 <= u_ < 60
    assert len({roll(5, t) for t in range(30)}) > 20


def test_the_target_number_splits_success_from_fail(u, s0):
    a = parse("try:door:wits")
    m = modifiers(u, s0, a)          # wits 1
    assert m.z == 1
    for r, dc in DC.items():
        assert [outcome((d, 0, 0), m, r) for d in (dc - 2, dc - 1)] == ["fail", "success"]


@pytest.mark.parametrize("z", range(-2, 6))
def test_chance_counts_2d6(z):
    totals = [d1 + d2 + z for d1 in range(1, 7) for d2 in range(1, 7)]
    for dc in DC.values():
        assert chance(z, dc) == sum(t >= dc for t in totals) / 36


def test_chance_at_zero():
    assert [chance(0, DC[r]) for r in ("low", "normal", "high")] == [21 / 36, 15 / 36, 10 / 36]


def test_oracle_path(play):
    play.do("go:village")
    play.do("go:yard")
    a = parse("try:door:finesse;rely=trait:tinker")
    o = play.obs
    pv = preview(play.u, o, a)
    assert pv.risk == "normal" and [c[2] for c in pv.mods.chips()] == [2, 0, -1] and pv.z == 1
    step = play.do(format(a), (4, 3, 0))
    s = play.s
    assert pv.dc == 8 and step.result == "success" and step.risk == "normal" and step.mods == pv.mods.atoms()
    assert s.stat(PLAYER, "beats") == 3 and s.fill("door") == 1 and s.fill("clock.1") == 0
    assert s.has("spent", PLAYER, "tinker")


def test_a_fail_applies_its_cost_at_once(play):
    play.do("go:village")
    play.do("go:yard")
    snags = len(play.s.marks(PLAYER))
    step = play.do("try:door:finesse", (1, 1, 0))
    s = play.s
    assert step.result == "fail" and s.fill("door") == 0 and s.fill("clock.1") == 1
    assert len(s.marks(PLAYER)) == snags + 1          # normal risk applies a light cost; u = 0 picks engine.snag
    assert "pay" not in {a.schema for a in candidates(play.u, play.obs)}


def test_the_decisive_chips_are_those_whose_removal_flips_the_result(play):
    """api.md 3: with the spray hindering, finesse 2 and a guarding tinker (0) roll against 8."""
    play.do("go:village")
    play.do("go:yard")
    play.do("try:door:finesse;rely=trait:tinker", (4, 2, 0))          # 7 fails; without the spray, 8 would succeed
    assert step_record(play.u, {"tags": []}, play.log.seen[PLAYER][-1], "", None)["decisive"] == [2]
    play.do("try:door:finesse;rely=thing:letter", (4, 3, 0))          # 8 succeeds; without finesse, 6 would fail
    assert step_record(play.u, {"tags": []}, play.log.seen[PLAYER][-1], "", None)["decisive"] == [0]


def path_steps(u, i):
    p = u.witnesses["paths"][i]
    before = path_steps(u, p["after"]) if "after" in p else []
    return before + p["steps"]


def pass_until(run, done):
    """cut(pass) alone reaches an ending within 1 + Σ deadline boxes steps (rule.md 10, guaranteed ending)."""
    for _ in range(1 + sum(run.u.boxes(c.deadline) for c in run.u.chapters)):
        if done(run.s) or ended(run.s):
            break
        run.step(parse("cut:pass"))
    assert done(run.s), "passing time did not get there within the guaranteed bound"


@pytest.mark.parametrize("i", range(4))
def test_witness_paths_reach_their_goal(u, creation, i):
    play = Play(u, creation)
    reach = u.witnesses["paths"][i]["reach"]
    steps = path_steps(u, i)
    for n, st in enumerate(steps):
        aid, r = (st["do"], tuple(st["roll"])) if isinstance(st, dict) else (st, None)
        assert not ended(play.s)
        play.do(aid, r or (1, 1, 0))
        if n < len(steps) - 1 and "goal" in reach:
            assert play.s.flag("chapter") == reach["goal"]
    if "goal" in reach:
        assert play.s.flag("chapter") == reach["goal"] + 1
    else:
        assert play.s.flag("ending") == reach["ending"]
        assert candidates(u, play.obs) is not None


@pytest.mark.parametrize("aid", [
    "give:clock.1:dohae", "try:door:finesse;rely=thing:clock.1", "try:clock.1:force", "try:deadline.1:wits",
    "try:player:force;strain=forced", "take:key", "go:lamp_room", "talk:dohae:t_oil", "pay:engine.beat",
    "try:door:force;rely=trait:islander", "talk:yunseul:chat;claim=c_keeper",
])
def test_out_of_candidate_ids_are_refused(play, aid):
    play.do("go:yard") if aid.startswith(("try:door", "give")) else None
    assert not admits(play.u, play.obs, parse(aid))


def test_progress_and_neutral_self_try(play):
    play.do("go:village")
    play.do("go:yard")
    play.do("try:door:finesse", (1, 1, 0))
    step = play.do("try:player:wits")
    assert step.delta.add == step.delta.remove == frozenset() and step.result == "none"


def test_hinder_counts_once(u, play):
    play.do("go:yard")                     # spray: a snag on the player
    w = Work(u, play.s)
    w.tag("door", "snag", "scene", None)
    w.tag("yard", "snag", "scene", None)
    m = modifiers(u, w.state(), parse("try:door:finesse"))
    assert len(m.hinder) == 3 and m.z == 2 - 1


def test_a_talk_is_hindered_by_the_axis_its_tone_reads(u, s0):
    """rule.md 3.2: a threat reads the other party's fear, any other tone their trust; only a negative one hinders."""
    w = Work(u, s0)
    w.set_("regards", ("yunseul", PLAYER, "trust"), -1)
    threat, ask = parse("talk:yunseul:t_wall;tone=threaten"), parse("talk:yunseul:t_wall")
    assert modifiers(u, w.state(), threat).hinder == ()
    assert modifiers(u, w.state(), ask).hinder == (("regards", "yunseul", PLAYER, "trust", -1),)
    w.set_("regards", ("yunseul", PLAYER, "fear"), -1)
    assert modifiers(u, w.state(), threat).hinder == (("regards", "yunseul", PLAYER, "fear", -1),)


def test_risk_reads_only_the_action(u):
    assert risk(u, parse("try:door:force")) == "high"                 # normal + clash
    assert risk(u, parse("try:bridge:wits;strain=forced")) == "normal"
    assert risk(u, parse("try:door:force;strain=forced")) == "high"
    assert risk(u, parse("talk:dohae:chat;tone=threaten")) == "high"
    assert risk(u, parse("talk:dohae:chat;tone=deceive")) == "high"
    assert risk(u, parse("talk:dohae:chat")) == "normal"
    assert risk(u, parse("choose:g_oil:beacon")) == "high"
    assert risk(u, parse("go:yard")) == "low"


def test_hidden_blocker_is_revealed_without_a_roll(play):
    play.do("go:village")
    assert admits(play.u, play.obs, parse("talk:dohae:t_oil"))
    step = play.do("talk:dohae:t_oil")
    assert step.result == "blocked" and not step.rolled
    assert play.s.has("believes", PLAYER, "hound.hidden") and play.s.stat(PLAYER, "beats") == 2
    assert "hound" in play.obs.seen
    assert not admits(play.u, play.obs, parse("talk:dohae:t_oil"))
    assert admits(play.u, play.obs, parse("try:hound:charm"))


def test_favor_promise_is_kept_by_giving_back(play):
    play.do("go:village")
    play.do("talk:dohae:chat")             # reveals the hound
    play.do("try:hound:wits", (6, 6, 0))
    assert play.s.fill("hound") == 1
    play.do("talk:dohae:favor", (6, 6, 0))
    assert play.s.where("key") == PLAYER and play.s.has("owes", PLAYER, "dohae", "promise")
    assert play.s.regards("dohae", PLAYER, "trust") == 1          # the won roll
    assert not admits(play.u, play.obs, parse("talk:dohae:favor"))
    play.do("give:key:dohae")
    assert not play.s.rows("owes") and play.s.regards("dohae", PLAYER, "trust") == 2
    assert not admits(play.u, play.obs, parse("talk:dohae:favor"))        # one favor per character (story.md 3.4)


def test_an_open_promise_outlives_chapters_and_the_ending(u, play):
    """A promise has no hidden due: lighting the lamp broke the borrowed key's promise with no moment to keep it
    (qa_test/runs/play-4-talker 47)."""
    from src.narrate import legacy
    for aid, r in (("go:village", None), ("talk:dohae:chat", None), ("try:hound:wits", (6, 6, 0)),
                   ("talk:dohae:favor", (6, 6, 0)), ("go:yard", None), ("try:door:finesse;rely=thing:key", (6, 6, 0)),
                   ("go:lamp_room", None)):
        play.do(aid, r)
    trust = play.s.regards("dohae", PLAYER, "trust")
    assert play.s.flag("chapter") == 2 and play.s.has("owes", PLAYER, "dohae", "promise")
    play.do("try:lens:finesse", (6, 6, 0))
    play.do("choose:g_oil:all_in")
    play.do("try:lamp:wits", (6, 6, 0))
    assert ended(play.s) and play.s.has("owes", PLAYER, "dohae", "promise")
    assert play.s.regards("dohae", PLAYER, "trust") == trust and not play.s.marks(PLAYER)
    assert ("owes", PLAYER, "dohae", "promise") in legacy(u, play.obs)


def test_deceit_is_caught_by_a_contrary_belief(play):
    play.do("go:village")
    play.do("talk:dohae:chat")
    play.do("try:hound:wits", (6, 6, 0))
    play.do("talk:dohae:chat;claim=c_keeper;tone=deceive")
    assert play.s.regards("dohae", PLAYER, "trust") == -2
    assert any(k == "snag" and life == "chapter" for _, k, life in play.s.marks(PLAYER))


def test_a_threat_frightens_and_costs_trust_even_when_it_fails(play):
    """rule.md 5.1 step 4: whatever the result."""
    assert play.do("talk:yunseul:t_wall;tone=threaten", (1, 1, 0)).result == "fail"
    assert play.s.regards("yunseul", PLAYER, "fear") == 1 and play.s.regards("yunseul", PLAYER, "trust") == -1


def test_a_won_talk_earns_trust_and_a_failed_one_does_not(play):
    """rule.md 5.1 step 4: a rolled success raises trust, so the next topic gated on trust opens without a roll."""
    assert play.do("talk:yunseul:come", (1, 1, 0)).result == "fail"
    assert play.s.regards("yunseul", PLAYER, "trust") == 0
    assert play.do("talk:yunseul:come", (6, 6, 0)).result == "success"
    assert play.s.regards("yunseul", PLAYER, "trust") == 1
    assert not rolls(play.u, facts_of(play.u, play.s, PLAYER), play.log.hist, parse("talk:yunseul:t_wall"))


def test_a_won_threat_earns_no_trust(play):
    assert play.do("talk:yunseul:t_wall;tone=threaten", (6, 6, 0)).result == "success"
    assert play.s.regards("yunseul", PLAYER, "trust") == -1


def test_a_failed_favor_can_be_asked_again(play):
    """Only a granted favor counts as asked (rule.md 5.1 step 5): its pattern takes success or none, not fail."""
    play.do("go:village")
    play.do("talk:dohae:chat")             # reveals the hound
    play.do("try:hound:wits", (6, 6, 0))
    assert play.do("talk:dohae:favor", (1, 1, 0)).result == "fail"
    assert play.s.where("key") == "dohae" and admits(play.u, play.obs, parse("talk:dohae:favor"))


def test_a_story_complication_waits_for_its_condition(u, s0):
    """rule.md 3.3: a story complication joins the pool only while its when holds (dohae is cold at trust 0 or less)."""
    w = Work(u, s0)
    w.move(PLAYER, "village")
    assert "c_dohae_cold" in [c.id for c in pool(u, "light", "dohae", w.state(), frozenset())]
    w.set_("regards", ("dohae", PLAYER, "trust"), 1)
    assert [c.id for c in pool(u, "light", "dohae", w.state(), frozenset())] == ["engine.snag", "engine.beat"]


def test_give_wanted_thing_earns_kindness(play):
    play.do("go:village")
    play.do("talk:dohae:chat")
    play.do("try:hound:wits", (6, 6, 0))
    play.do("give:letter:dohae")
    assert play.s.has("owes", "dohae", PLAYER, "kindness")
    assert not rolls(play.u, facts_of(play.u, play.s, PLAYER), play.log.hist, parse("talk:dohae:favor"))
    play.do("talk:dohae:favor")
    assert play.s.where("key") == PLAYER and not play.s.rows("owes")
    assert not admits(play.u, play.obs, parse("talk:dohae:favor"))


def test_declare_brings_the_latent(play):
    play.do("go:village")
    assert admits(play.u, play.obs, parse("declare:l_baek"))
    play.do("declare:l_baek")
    assert play.s.where("baek") == "village" and play.s.fill("clock.1") == 1
    assert admits(play.u, play.obs, parse("talk:baek:chat"))
    play.do("go:yard")
    assert admits(play.u, play.obs, parse("try:door:wits;rely=bond:baek"))


def test_rest_only_where_one_can_rest(play):
    assert not admits(play.u, play.obs, parse("cut:rest"))           # the dock is no resting place
    play.do("go:village")
    assert admits(play.u, play.obs, parse("cut:rest"))


def test_an_overcome_obstacle_is_no_longer_a_target(play):
    play.do("go:village")
    play.do("go:yard")
    assert admits(play.u, play.obs, parse("try:door:wits"))
    play.do("try:door:finesse", (6, 6, 0))
    assert play.s.fill("door") == play.u.boxes("door") and admits(play.u, play.obs, parse("go:lamp_room"))
    assert not [a for a in candidates(play.u, play.obs) if a.schema == "try" and a.intent[0] == "door"]


def test_a_fitting_approach_fills_one_box_more(u, creation):
    play = Play(u, creation)
    for st in path_steps(u, 0):
        aid, r = (st["do"], tuple(st["roll"])) if isinstance(st, dict) else (st, None)
        play.do(aid, r)
    play.do("try:lens:finesse", (6, 6, 0))                                # the lens fits finesse
    assert play.s.fill("lens") == 2
    play.do("try:lamp:wits", (6, 6, 0))                                   # the lamp fits wits
    assert play.s.fill("lamp") == 2
    play.do("try:lamp:finesse", (6, 6, 0))
    assert play.s.fill("lamp") == 3


def test_a_success_on_something_else_lifts_its_lowest_snag(u, play):
    """rule.md 7: the lowest-slot snag, the one the roll card names."""
    w = Work(u, play.s)
    w.tag("letter", "snag", "scene")
    w.tag("letter", "snag", "chapter")
    play.s = w.state()
    assert preview(u, play.obs, parse("try:letter:finesse")).gain["remove"] == ("mark", "letter", "snag", "scene", 1)
    play.do("try:letter:finesse", (6, 6, 0))
    assert play.s.marks("letter") == [(2, "snag", "chapter")]


def test_rest_heals_and_brings_threats_closer(play):
    play.do("go:yard")                     # the bridge threat appears
    play.do("go:village")
    w = play.s.stat(PLAYER, "wounds")
    play.do("cut:rest")
    assert play.s.fill("t_bridge_fall") == 2 and play.s.fill("deadline.1") == 2
    assert play.s.stat(PLAYER, "beats") == 0 and play.s.stat(PLAYER, "wounds") == max(w - 1, 0)


def test_chapter_change_opens_growth(u, creation):
    play = Play(u, creation)
    for st in path_steps(u, 0):
        aid, r = (st["do"], tuple(st["roll"])) if isinstance(st, dict) else (st, None)
        play.do(aid, r)
    s = play.s
    assert s.where("clock.2") == PLAYER and s.where("clock.1") is None and s.stat(PLAYER, "growth") == 1
    assert s.where("g_oil") is None        # the fork waits for 윤슬 (story.md 3.8)
    grows = [format(a) for a in candidates(u, play.obs) if a.schema == "grow"]
    assert "grow:finesse" in grows and "grow:trait:sailor:islander" in grows
    play.do("grow:trait:sailor:islander")
    assert s.stat(PLAYER, "sailor") == 1 and play.s.stat(PLAYER, "sailor") is None
    assert play.s.stat(PLAYER, "islander") == 1 and play.s.stat(PLAYER, "growth") == 0
    assert play.s.stat(PLAYER, "beats") == 0              # growth is picked on a card, not spent in the scene


def test_a_new_chapter_is_a_new_scene(u, creation):
    """The yard's spray stayed on into the lamp room and the next chapter (play-5-bold 6, 8)."""
    play = Play(u, creation)
    steps = path_steps(u, 0)
    for st in steps[:-1]:
        aid, r = (st["do"], tuple(st["roll"])) if isinstance(st, dict) else (st, None)
        play.do(aid, r)
    assert play.s.stat(PLAYER, "beats") and any(life == "scene" for _, _, life in play.s.marks(PLAYER))
    play.do(steps[-1])
    assert play.s.flag("chapter") == 2 and play.s.stat(PLAYER, "beats") == 0
    assert not any(life == "scene" for _, _, life in play.s.marks(PLAYER))


def test_an_edge_on_a_carried_thing_goes_along(u, play):
    """Readying the oil won an edge that could only help a roll on the oil itself (play-5-explorer 34, 38, 40)."""
    play.do("try:letter:finesse", (6, 6, 0))
    assert [kind for _, kind, _ in play.s.marks("letter")] == ["edge"]
    play.do("go:village")
    play.do("go:yard")
    step = play.do("try:door:finesse;rely=tag:letter:1", (6, 6, 0))
    assert ("mark", "letter", "edge", "scene", 1) in step.mods and not play.s.marks("letter")


def test_a_thing_leaned_on_is_spent_until_the_chapter_changes(u, creation):
    """A free letter gave +1 to every roll and no trait was ever leaned on (play-5-odd 25)."""
    from src.rules.candidates import rely_values
    run = Run(u, creation)
    for a in ("go:village", "go:yard"):
        run.step(parse(a))
    assert "thing:letter" in rely_values(u, run.obs.facts, "door")
    run.step(parse("try:door:finesse;rely=thing:letter"), (1, 1, 0))
    assert run.s.has("spent", PLAYER, "letter") and "thing:letter" not in rely_values(u, run.obs.facts, "door")
    assert not admits(u, run.obs, parse("try:door:finesse;rely=thing:letter"))
    pass_until(run, lambda s: s.flag("chapter") == 2)
    assert not run.s.has("spent", PLAYER, "letter")


def pick(rng, k):
    """Schema first, then an action: a uniform pick over K is nearly all rely variants of try."""
    schema = rng.choice(sorted({a.schema for a in k}))
    return rng.choice([a for a in k if a.schema == schema])


def visible(u, s):
    return facts_of(u, s, PLAYER).atoms()


CLOCK_COST = {"low": 1, "normal": 1, "high": 2}     # boxes a fail adds to the held clock (rule.md 3.3)


def paced(a, step) -> bool:
    """Steps that raise a beat: moves, rolls, and steps a hidden block stopped (rule.md 4.1)."""
    return a.schema == "go" or step.rolled or step.result == "blocked"


def may_lose(u, a, s0, step) -> set:
    """Tag slots this step may clear without an expiry: what it relied on, the snag a success lifts, a healed scar,
    and slots it tagged again (ontology.md 4)."""
    out = {(x, slot) for x, slot, _ in step.names}
    rely = a.get("rely") or ""
    if rely.startswith("tag:"):
        x, _, slot = rely[4:].rpartition(":")
        out.add((x, int(slot)))
    if a.schema == "try" and step.result == "success" and a.intent[0] not in u.obstacles:
        snags = [i for i, kind, _ in s0.marks(a.intent[0]) if kind == "snag"]
        out |= {(a.intent[0], snags[0])} if snags else set()
    if a.schema == "grow" and a.intent[0] == "scar":
        out.add((PLAYER, int(a.intent[1])))
    return out


def check_time(u, a, s0, step):
    """When things happen (rule.md 4, 6, 8): crises, scene ends, arrivals and collapse."""
    s1 = step.after
    marks = s1.marks(PLAYER)
    assert (s1.flag("ending") == "collapse") == (len(marks) == 3 and all(life == "scar" for _, _, life in marks))
    if ended(s1):
        return
    for o in active_threats(u, s1):
        assert s1.fill(o) < u.boxes(o), f"{o} is full but has not arrived"
    new_chapter = s1.flag("chapter") != s0.flag("chapter")
    scene_end = not new_chapter and (a.schema == "cut" or paced(a, step) and s1.stat(PLAYER, "beats") == 0)
    lose = may_lose(u, a, s0, step)
    for (x, slot), (kind, life) in s0.mark_.items():
        if (x, slot) in lose:
            continue
        if life == "scene" and (scene_end or new_chapter) or life == "chapter" and new_chapter:
            assert (x, slot) not in s1.mark_, f"{life} tag on {x} outlived its {life}"
        else:
            assert s1.mark_.get((x, slot)) == (kind, life), f"{life} tag on {x} lost after {format(a)}"
    if new_chapter:
        return
    c = held_clock(u, s0)
    guarded = bool(a.get("rely")) and not a.get("rely").startswith(("bond:", "with:"))
    fail = 1 if guarded else CLOCK_COST[step.risk]          # something spent makes a fail cost one box (rule.md 3.3)
    n = s0.fill(c) + (fail if step.result == "fail" else 0) + (a.schema == "declare")
    # A full clock brings its crisis and starts over; short of full, nothing else moves it.
    assert s1.fill(c) == (0 if n >= u.boxes(c) else n), f"{c}: {s0.fill(c)} → {s1.fill(c)} after {format(a)}"


@pytest.mark.parametrize("seed", range(40))
def test_random_play_keeps_the_properties(u, creation, seed):
    rng = random.Random(seed)
    ap = rng.sample([2, 1, 1, 0], 4)
    traits = rng.sample(sorted(u.traits), u.pick)
    play = Play(u, {"approaches": dict(zip(("force", "finesse", "wits", "charm"), ap, strict=True)),
                    "traits": traits}, seed)
    beats = dict.fromkeys(range(1, len(u.chapters) + 1), 0)
    for _ in range(300):
        if ended(play.s):
            break
        o = play.obs
        k = candidates(u, o)
        assert k, "K is empty before an ending"
        buttons = recommend(u, o)
        a = rng.choice(buttons) if buttons and rng.random() < 0.5 else pick(rng, k)
        r = (rng.randint(1, 6), rng.randint(1, 6), rng.randrange(60))
        pv = preview(u, o, a) if rolls(u, o.facts, o.hist, a) else None
        s0, before = play.s, visible(u, play.s)
        step = play.do(format(a), r)
        assert conforms(u, play.s) == []
        assert ended(play.s) or play.s.stat(PLAYER, "beats") < u.beats
        if step.rolled:
            assert pv is not None and pv.risk == step.risk and pv.mods.atoms() == step.mods
            assert step.result == outcome(r, pv.mods, pv.risk)
            assert visible(u, play.s) != before
        elif pv is not None:
            assert step.result == "blocked"
        check_time(u, a, s0, step)
        # A scene ends within B beat-raising steps and a deadline of n boxes arrives within n scenes (fun.md 3.3).
        chapter = s0.flag("chapter")
        beats[chapter] += paced(a, step)
        assert beats[chapter] <= u.boxes(f"deadline.{chapter}") * u.beats
    assert ended(play.s), "no ending within 300 steps"
    assert space(u, play.obs) is not None


def test_recommend_walks_toward_a_goal_place_out_of_reach(play):
    """With nothing to talk about, the button is the first step toward the chapter goal (rule.md 9)."""
    play.do("talk:yunseul:t_wall", (6, 6, 0))
    assert [format(x) for x in recommend(play.u, play.obs)] == ["go:yard"]


def test_recommend_heads_for_the_ending_obstacle_in_a_chapter_with_no_goal(u, creation):
    """The last chapter ends in an ending; away from its obstacle no button was left (play-3-talker 24)."""
    play = Play(u, creation)
    for st in path_steps(u, 0):
        aid, r = (st["do"], tuple(st["roll"])) if isinstance(st, dict) else (st, None)
        play.do(aid, r or (1, 1, 0))
    for aid in ("go:yard", "go:dock"):
        play.do(aid, (1, 1, 0))
    assert u.chapter_of(2).goal is None
    assert [format(x) for x in recommend(u, play.obs)] == ["talk:yunseul:t_wall", "go:yard"]


def _closed(u, delta_add, delta_remove, tags=()):
    seen = Seen(0, "give:key:dohae", None, "none", (PLAYER,), Delta(frozenset(delta_add), frozenset(delta_remove)), ())
    return [c["state"] for c in changes(u, {"tags": list(tags)}, seen, parse("give:key:dohae"), None) if c["kind"] == "promise"]


def test_a_promise_kept_at_full_trust_still_reads_as_kept(u):
    # Trust is already 3, so keeping the promise changes no regards atom.
    assert _closed(u, {("at", "key", "dohae")}, {("owes", PLAYER, "dohae", "promise"), ("at", "key", PLAYER)}) == ["kept"]


def test_a_broken_promise_reads_as_broken_even_at_lowest_trust(u):
    mark = ("mark", PLAYER, "snag", "chapter", 1)
    assert _closed(u, {mark}, {("owes", PLAYER, "dohae", "promise")}, [[list(mark), 0, "약속을 어김"]]) == ["broken"]


def test_a_threat_against_no_fear_names_the_missing_fear(u):
    assert atom_label(u, {}, ("regards", "dohae", PLAYER, "fear", -1)).endswith("겁 없음")
    assert atom_label(u, {}, ("regards", "dohae", PLAYER, "trust", -1)).endswith("경계")


def test_a_companion_goes_along_until_a_place_it_avoids(u, play):
    f = facts_of(u, play.s, PLAYER)
    assert rolls(u, f, play.log.hist, parse("talk:yunseul:come"))         # no trust yet: a charm roll
    assert play.do("talk:yunseul:come", (6, 6, 0)).result == "success"
    ids = {format(a) for a in candidates(u, play.obs)}
    assert "talk:yunseul:stay" in ids and "talk:yunseul:come" not in ids
    play.do("go:village")
    assert play.s.where("yunseul") == "village" and play.s.has("follows", "yunseul", PLAYER)
    moved = changes(u, {"tags": []}, play.log.seen[PLAYER][-1], parse("go:village"), None)
    assert [(c["id"], c["with"]) for c in moved if c["kind"] == "move"] == [("player", False), ("yunseul", True)]
    play.do("talk:dohae:chat")                                          # reveals the hound
    play.do("try:hound:wits", (6, 6, 0))
    play.do("give:letter:dohae")                                        # trust 1: dohae comes without a roll
    assert not rolls(u, facts_of(u, play.s, PLAYER), play.log.hist, parse("talk:dohae:come"))
    play.do("talk:dohae:come")
    play.do("go:yard")
    assert play.s.where("yunseul") == play.s.where("dohae") == "yard"
    # Someone at the player's side helps any roll but one aimed at them (play-4-talker 17).
    door = [format(a) for a in candidates(u, play.obs) if format(a).startswith("try:door:force;rely=with:")]
    assert door == ["try:door:force;rely=with:dohae", "try:door:force;rely=with:dohae;strain=forced",
                    "try:door:force;rely=with:yunseul", "try:door:force;rely=with:yunseul;strain=forced"]
    assert preview(u, play.obs, parse(door[0])).z == preview(u, play.obs, parse("try:door:force")).z + 1
    assert not any("rely=with:yunseul" in format(a) for a in candidates(u, play.obs)
                   if a.schema == "talk" and a.intent[0] == "yunseul")
    play.do("talk:yunseul:stay")
    play.do("try:door:finesse", (6, 6, 0))
    play.do("go:lamp_room")                                             # dohae fears climbing the lighthouse
    assert play.s.where("yunseul") == play.s.where("dohae") == "yard"
    assert not play.s.rows("follows") and conforms(u, play.s) == []
    seen = play.log.seen[PLAYER][-1]
    stops = [c["id"] for c in changes(u, {"tags": []}, seen, parse("go:lamp_room"), None) if c["kind"] == "follow"]
    assert stops == ["dohae"]


def test_a_missed_goal_costs_time_and_still_grows(u, creation):
    late = Run(u, creation)
    pass_until(late, lambda s: s.flag("chapter") == 2)
    assert late.s.fill("deadline.2") == 1 and late.s.stat(PLAYER, "growth") == 1
    on_time = Run(u, creation)
    for a, r in (("go:village", None), ("go:yard", None), ("try:door:finesse", (6, 6, 0)), ("go:lamp_room", None)):
        on_time.step(parse(a), r)
    assert on_time.s.flag("chapter") == 2 and on_time.s.fill("deadline.2") == 0
    assert on_time.s.stat(PLAYER, "growth") == 1


def test_the_crisis_comes_when_the_clock_is_full_not_before(play):
    play.do("go:village")
    play.do("go:yard")
    boxes = play.u.boxes("clock.1")
    for n in range(1, boxes):
        play.do("try:bridge:wits", (1, 1, 0))                             # a low-risk fail: clock +1, nothing else
        assert play.s.fill("clock.1") == n and not any(life == "chapter" for _, _, life in play.s.marks(PLAYER))
    play.do("try:bridge:wits", (1, 1, 0))
    assert play.s.fill("clock.1") == 0                                    # the crisis soaks the player for the chapter
    assert [(kind, life) for _, kind, life in play.s.marks(PLAYER)] == [("snag", "chapter")]


def test_a_scene_end_clears_scene_tags_and_keeps_chapter_tags(play):
    for aid, r in (("go:village", None), ("talk:dohae:chat", None), ("try:hound:wits", (6, 6, 0)),
                   ("talk:dohae:chat;claim=c_keeper;tone=deceive", None), ("go:yard", None)):
        play.do(aid, r)
    assert sorted(life for _, _, life in play.s.marks(PLAYER)) == ["chapter", "scene"]   # suspicion, spray
    play.do("cut:pass")
    assert [(kind, life) for _, kind, life in play.s.marks(PLAYER)] == [("snag", "chapter")]


def test_a_chapter_change_clears_chapter_tags(u, creation):
    """rule.md 4.3 step 1: the crisis that soaked the player in chapter 1 does not follow into chapter 2."""
    play = Play(u, creation)
    for aid in ("go:village", "go:yard", "try:bridge:wits", "try:bridge:wits", "try:bridge:wits", "try:bridge:wits"):
        play.do(aid, (1, 1, 0))
    assert [(kind, life) for _, kind, life in play.s.marks(PLAYER)] == [("snag", "chapter")]
    play.do("try:door:finesse", (6, 6, 0))
    play.do("go:lamp_room")
    assert play.s.flag("chapter") == 2 and play.s.marks(PLAYER) == []


def test_a_full_threat_arrives_and_leaves(u, creation):
    run = Run(u, creation)
    run.step(parse("go:yard"))                                            # the bridge starts to fall
    assert run.s.where("t_bridge_fall") == PLAYER and run.s.has("link", "yard", "village")
    pass_until(run, lambda s: s.where("t_bridge_fall") is None)
    assert not run.s.has("link", "yard", "village") and not run.s.has("link", "village", "yard")


def test_passing_time_alone_reaches_an_ending(u, creation):
    run = Run(u, creation)
    pass_until(run, ended)
    assert run.s.flag("ending") == "wreck"


def test_a_late_chapter_does_not_start_a_one_box_deadline_full(creation):
    """rule.md 4.3: lateness costs a box only of a next deadline with more than one, else it would arrive at once."""
    raw = skeleton_raw()
    raw["chapters"][1]["deadline"]["boxes"] = 1
    run = Run(build(raw, "sha256:x"), creation)
    pass_until(run, lambda s: s.flag("chapter") == 2)
    assert not ended(run.s) and run.s.fill("deadline.2") == 0
    run.step(parse("cut:pass"))
    assert run.s.flag("ending") == "wreck"


def test_a_repeating_trigger_fires_on_each_rise_not_while_it_holds(creation):
    """rule.md 8: story triggers are edge-fired, so a repeat one fires each time its condition becomes true."""
    raw = skeleton_raw()
    raw["triggers"]["tr_gust"] = {"when": {"at": ["player", "yard"]}, "repeat": True,
                                  "effects": [{"set": ["regards", "yunseul", "player", "trust", "+1"]}]}
    play = Play(build(raw, "sha256:x"), creation)
    trust = []
    for aid in ("go:yard", "look:door", "look:bridge", "go:village", "go:yard"):
        play.do(aid)
        trust.append(play.s.regards("yunseul", PLAYER, "trust"))
    assert trust == [1, 1, 1, 1, 2]


def test_one_scar_is_not_a_collapse(u, creation):
    """rule.md 6: collapse only once every slot is a scar."""
    play = Play(u, creation)
    for aid, r in (("go:village", None), ("go:yard", None), ("try:door:force;strain=forced", (1, 1, 0)),
                   ("try:door:finesse", (6, 6, 0)), ("go:lamp_room", None)):
        play.do(aid, r)
    assert play.s.flag("chapter") == 2 and play.s.stat(PLAYER, "wounds") == 1 and not play.s.marks(PLAYER)
    play.do("try:lens:finesse;strain=forced", (1, 1, 0))                  # high: u = 0 picks a wound, the second
    assert not ended(play.s) and play.s.marks(PLAYER) == [(1, "snag", "scar")] and play.s.stat(PLAYER, "wounds") == 0


def test_a_fall_and_the_scene_end_it_brings_are_named(u, creation):
    """Wounds reset by a fall read as a heal, and the clocks it moved had no cause (rule.md 6)."""
    from src.narrate import change_lines
    from src.view import step_record
    play = Play(u, creation)
    for aid, r in (("go:village", None), ("go:yard", None), ("try:door:force;strain=forced", (1, 1, 0)),
                   ("try:door:finesse", (6, 6, 0)), ("go:lamp_room", None), ("try:lens:finesse;strain=forced", (1, 1, 0))):
        play.do(aid, r)
    kinds = [c["kind"] for c in step_record(u, {"tags": []}, play.log.seen[PLAYER][-1], "", None)["changes"]]
    assert "fall" in kinds and "wound" not in kinds and kinds.index("scene_end") < kinds.index("clock")
    lines = change_lines(u, step_record(u, {"tags": []}, play.log.seen[PLAYER][-1], "", None)["changes"])
    assert "당신이 쓰러졌다가 간신히 몸을 일으킵니다" in lines and "당신의 상처가 조금 나았습니다" not in lines


def test_a_snag_never_pushes_out_an_edge_and_a_replaced_tag_is_told(u, s0):
    from src.onto.change import Work
    w = Work(u, s0)
    for kind in ("edge", "snag", "snag"):
        w.tag(PLAYER, kind, "scene")
    assert w.tag(PLAYER, "snag", "scene") == 2 and w.happen == [("tag_replaced", PLAYER, 2, "snag", "scene")]
    assert w.tag(PLAYER, "edge", "scene") == 2
    assert [k for _, k, _ in w.state().marks(PLAYER)] == ["edge", "edge", "snag"]


def test_an_attempt_names_its_target_and_approach(u, s0):
    from src.view import action_label
    o = observe(u, s0, Log())
    assert action_label(u, o, {}, parse("try:dohae:charm")) == "도해를 매력으로 상대한다"
    assert action_label(u, o, {}, parse("try:door:charm")) == "녹슨 등대 문을 매력으로 다룬다"
    # forcing the story's own way keeps its words (play-3 real UI: "무리해서 녹슨 등대 문에 완력으로 맞선다")
    assert action_label(u, o, {}, parse("try:door:force;strain=forced")) == "무리해서 어깨로 문을 들이받는다"
    # an empty attempt stands for the sentence, not an approach (play-3-odd 1: "재치로 해 본다" for a greeting)
    assert action_label(u, o, {}, parse("try:player:wits")) == "말한 대로 해 본다"


def test_a_fork_choice_says_where_a_thing_goes(u):
    from src.view import effect_names
    assert effect_names(u, [("set", "fill", ("lamp",), "+2"), ("move", "oil", "lamp_room")]) == \
        ["꺼진 등불 +2칸", "기름통을 등불실에 둠"]
    assert effect_names(u, [("move", "oil", "yunseul")]) == ["기름통이 윤슬에게 감"]


def test_every_help_chip_carries_its_option_name(u, play):
    """The roll card draws a help's or a guard's value beside the option of the same name (ui.md 4.2)."""
    from src.cards import roll_card
    play.do("talk:yunseul:come", (6, 6, 0))
    play.do("go:yard")
    card = roll_card(u, play.obs, {"tags": []}, parse("try:door:force"), [], [], {}, "c1")["public"]
    helped = [o for o in card["options"] if o["label"] != "기대지 않음"]
    assert "윤슬의 도움" in [o["label"] for o in helped]
    for o in helped:
        assert [(m["label"], m["kind"]) for m in o["preview"]["mods"] if m["kind"] in ("help", "guard")] == \
            [(o["label"], "guard" if o["consumed"] else "help")]


def test_forcing_is_offered_where_it_buys_a_box(u, play):
    from src.cards import roll_card
    for aid, r in (("go:village", None), ("go:yard", None), ("try:door:finesse", (6, 6, 0)), ("go:lamp_room", None)):
        play.do(aid, r)
    card = roll_card(u, play.obs, {"tags": []}, parse("try:lens:force"), [], [], {}, "c1")["public"]
    forced = next(o["preview"] for o in card["options"] if o["id"] == "try:lens:force;strain=forced")
    plain = next(o["preview"] for o in card["options"] if o["id"] == "try:lens:force")
    assert (plain["gain"]["boxes"], forced["gain"]["boxes"], forced["gain"]["forced"]) == (1, 2, 1)
    assert forced["dc"] == plain["dc"] + 1 and card["selected"] == "try:lens:force"
    fits = roll_card(u, play.obs, {"tags": []}, parse("try:lens:finesse"), [], [], {}, "c2")["public"]
    assert not any(o["forced"] for o in fits["options"])               # the fit already takes both boxes

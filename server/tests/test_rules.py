import random

import pytest
from src.onto.atoms import PLAYER
from src.onto.log import Delta, Log
from src.onto.universe import conforms, initial
from src.onto.view import Seen, facts_of, observe, record
from src.rules.acts import format, parse
from src.rules.candidates import admits, candidates, space
from src.rules.recommend import recommend
from src.rules.resolve import event_of, resolve
from src.rules.roll import DC, chance, outcome, preview, risk, roll, rolls
from src.rules.triggers import ended
from src.view import atom_label, changes


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
    "talk:dohae:t_oil;tone=friendly", "talk:dohae:favor", "talk:dohae:chat;claim=c_keeper;tone=deceive",
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
    from src.rules.roll import modifiers
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
    assert pv.risk == "normal" and [c[2] for c in pv.mods.chips()] == [2, 1, -1] and pv.z == 2
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


def path_steps(u, i):
    p = u.witnesses["paths"][i]
    before = path_steps(u, p["after"]) if "after" in p else []
    return before + p["steps"]


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
    from src.onto.change import Work
    w = Work(u, play.s)
    w.tag("door", "snag", "scene", None)
    w.tag("yard", "snag", "scene", None)
    from src.rules.roll import modifiers
    m = modifiers(u, w.state(), parse("try:door:finesse"))
    assert len(m.hinder) == 3 and m.z == 2 - 1


def test_risk_reads_only_the_action(u):
    assert risk(u, parse("try:door:force")) == "high"                 # normal + clash
    assert risk(u, parse("try:bridge:wits;strain=forced")) == "normal"
    assert risk(u, parse("try:door:force;strain=forced")) == "high"
    assert risk(u, parse("talk:dohae:chat;tone=threaten")) == "high"
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
    assert not admits(play.u, play.obs, parse("talk:dohae:favor"))
    play.do("give:key:dohae")
    assert not play.s.rows("owes") and play.s.regards("dohae", PLAYER, "trust") == 1


def test_deceit_is_caught_by_a_contrary_belief(play):
    play.do("go:village")
    play.do("talk:dohae:chat")
    play.do("try:hound:wits", (6, 6, 0))
    play.do("talk:dohae:chat;claim=c_keeper;tone=deceive")
    assert play.s.regards("dohae", PLAYER, "trust") == -2
    assert any(k == "snag" and life == "chapter" for _, k, life in play.s.marks(PLAYER))


def test_give_wanted_thing_earns_kindness(play):
    play.do("go:village")
    play.do("talk:dohae:chat")
    play.do("try:hound:wits", (6, 6, 0))
    play.do("give:letter:dohae")
    assert play.s.has("owes", "dohae", PLAYER, "kindness")
    assert not rolls(play.u, facts_of(play.u, play.s, PLAYER), play.log.hist, parse("talk:dohae:favor"))
    play.do("talk:dohae:favor")
    assert play.s.where("key") == PLAYER and not play.s.rows("owes")


def test_declare_brings_the_latent(play):
    play.do("go:village")
    assert admits(play.u, play.obs, parse("declare:l_baek"))
    play.do("declare:l_baek")
    assert play.s.where("baek") == "village" and play.s.fill("clock.1") == 1
    assert admits(play.u, play.obs, parse("talk:baek:chat"))
    play.do("go:yard")
    assert admits(play.u, play.obs, parse("try:door:wits;rely=bond:baek"))


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
    assert s.where("g_oil") == PLAYER
    grows = [format(a) for a in candidates(u, play.obs) if a.schema == "grow"]
    assert "grow:finesse" in grows and "grow:trait:sailor:islander" in grows
    play.do("grow:trait:sailor:islander")
    assert s.stat(PLAYER, "sailor") == 1 and play.s.stat(PLAYER, "sailor") is None
    assert play.s.stat(PLAYER, "islander") == 1 and play.s.stat(PLAYER, "growth") == 0


def pick(rng, k):
    """Schema first, then an action: a uniform pick over K is nearly all rely variants of try."""
    schema = rng.choice(sorted({a.schema for a in k}))
    return rng.choice([a for a in k if a.schema == schema])


def visible(u, s):
    return facts_of(u, s, PLAYER).atoms()


@pytest.mark.parametrize("seed", range(40))
def test_random_play_keeps_the_properties(u, creation, seed):
    rng = random.Random(seed)
    ap = rng.sample([2, 1, 1, 0], 4)
    traits = rng.sample(sorted(u.traits), u.pick)
    play = Play(u, {"approaches": dict(zip(("force", "finesse", "wits", "charm"), ap, strict=True)),
                    "traits": traits}, seed)
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
        before = visible(u, play.s)
        step = play.do(format(a), r)
        assert conforms(u, play.s) == []
        assert ended(play.s) or play.s.stat(PLAYER, "beats") < u.beats
        if step.rolled:
            assert pv is not None and pv.risk == step.risk and pv.mods.atoms() == step.mods
            assert step.result == outcome(r, pv.mods, pv.risk)
            assert visible(u, play.s) != before
        elif pv is not None:
            assert step.result == "blocked"
    assert space(u, play.obs) is not None


def test_recommend_walks_toward_a_goal_place_out_of_reach(play):
    """With nothing to talk about, the button is the first step toward the chapter goal (rule.md 9)."""
    play.do("talk:yunseul:t_wall", (6, 6, 0))
    assert [format(x) for x in recommend(play.u, play.obs)] == ["go:yard"]


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
    play.do("go:yard")                                                  # dohae avoids the yard
    assert play.s.where("yunseul") == "yard" and play.s.where("dohae") == "village"
    assert not play.s.has("follows", "dohae", PLAYER) and conforms(u, play.s) == []
    seen = play.log.seen[PLAYER][-1]
    assert [c["state"] for c in changes(u, {"tags": []}, seen, parse("go:yard"), None) if c["kind"] == "follow"] == ["stop"]
    play.do("talk:yunseul:stay")
    play.do("go:village")
    assert play.s.where("yunseul") == "yard" and not play.s.rows("follows")

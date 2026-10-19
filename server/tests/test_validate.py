import pytest
import yaml
from conftest import REPO, skeleton_raw
from src.onto.universe import build
from src.story import validate as V
from src.story.load import StoryError


def test_skeleton_passes():
    assert list(V.load_all(REPO / "scenarios")) == ["lighthouse"]


def first_path_door(raw, roll):
    raw["witnesses"]["paths"][0]["steps"][2]["roll"] = roll


BROKEN = [
    ("V1", lambda r: r["triggers"].__setitem__("tr_x", {"when": {"at": ["baek", "village"]}})),
    ("V1", lambda r: r["latents"]["l_baek"]["effects"].append({"move": ["key", "village"]})),
    ("V1", lambda r: r["places"]["dock"]["complications"].update(
        {f"c_{i}": {"name": "물", "weight": "light", "wound": 1} for i in range(58)})),
    ("V1", lambda r: r["places"]["dock"].__setitem__("smell", "x")),
    ("V2", lambda r: r["witnesses"]["creation"]["approaches"].__setitem__("charm", 3)),
    ("V3", lambda r: r["triggers"].__setitem__("tr_x", {"when": {"at": ["player", "dock"]}})),
    ("V3", lambda r: r["obstacles"]["door"]["solutions"]["s_shoulder"].__setitem__("when", {"flag": ["gale", 1]})),
    ("V3", lambda r: r["characters"]["yunseul"]["topics"]["t_wall"].__setitem__("free_when", {"at": ["key", "dohae"]})),
    ("V3", lambda r: r["obstacles"]["hound"].__setitem__("at", "dock")),
    ("V3", lambda r: r["obstacles"]["door"].__setitem__("at", "village")),
    ("V4", lambda r: r.__setitem__("style", r["style"] + "- 누렁이가 짖습니다.\n")),
    ("V4", lambda r: r["obstacles"]["bridge"].__setitem__("aliases", ["문"])),
    ("V4", lambda r: r["impossible"].append("열쇠")),
    ("V5", lambda r: first_path_door(r, [1, 1, 0])),
    ("V5", lambda r: r["witnesses"]["paths"].pop()),
    ("V5", lambda r: r["witnesses"]["paths"][0]["steps"].insert(0, "go:lamp_room")),
    ("V5", lambda r: r["witnesses"]["paths"][0]["steps"].__setitem__(2, "try:door:finesse")),
]


@pytest.mark.parametrize("stage, edit", BROKEN)
def test_broken_copy_fails_at_its_stage(tmp_path, stage, edit):
    raw = skeleton_raw()
    edit(raw)
    path = tmp_path / "broken" / "story.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with pytest.raises(StoryError) as e:
        V.load(path)
    assert str(e.value).startswith(stage), str(e.value)


def test_fuzzing_catches_a_broken_rule(u, monkeypatch):
    calls = {"n": 0}
    real = V.candidates

    def flaky(u_, o):
        calls["n"] += 1
        return [] if calls["n"] > 5 else real(u_, o)

    monkeypatch.setattr(V, "candidates", flaky)
    with pytest.raises(StoryError, match="^V6 run 0 step 5: no candidates"):
        V.v6(u)


def test_fuzzing_catches_a_preview_that_lies(u, monkeypatch):
    real = V.preview

    def lying(u_, o, a):
        p = real(u_, o, a)
        return p.__class__(**{**p.__dict__, "risk": "low" if p.risk != "low" else "high"})

    monkeypatch.setattr(V, "preview", lying)
    with pytest.raises(StoryError, match="^V6 .*preview differs"):
        V.v6(u)


def test_two_stories_with_one_id(tmp_path):
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "story.yaml").write_text((REPO / "scenarios/skeleton/story.yaml").read_text("utf-8"), "utf-8")
    with pytest.raises(StoryError, match="used twice"):
        V.load_all(tmp_path)


def test_the_round_trip_through_yaml_keeps_the_story(tmp_path):
    raw = skeleton_raw()
    path = tmp_path / "x" / "story.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert V.load(path).triggers == build(skeleton_raw(), "x").triggers

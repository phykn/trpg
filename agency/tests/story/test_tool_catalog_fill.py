"""catalog-fill subcommand copies fixed story support catalogs."""

import json
from pathlib import Path

from agency.story import tool


def test_catalog_fill_creates_fixed_catalogs(capsys, tmp_path):
    sd = tmp_path / "scen"
    sd.mkdir()

    rc = tool._main(["catalog-fill", str(sd)])

    assert rc == 0, capsys.readouterr().err
    assert capsys.readouterr().out.strip() == "OK"
    assert set(_read_json(sd / "actions.json")) == {
        "attack",
        "defend",
        "flee",
        "talk",
    }
    assert set(_read_json(sd / "effects.json")) == {
        "heal",
        "mp_restore",
        "dc_down",
        "dc_up",
    }
    assert len(_read_json(sd / "mbti.json")) == 16
    assert set(_read_json(sd / "slots.json")) == {"weapon", "armor", "accessory"}
    assert not (sd / "dialogue_styles.json").exists()
    assert not (sd / "statuses.json").exists()


def test_catalog_fill_replaces_effects_with_fixed_catalog(capsys, tmp_path):
    sd = tmp_path / "scen"
    sd.mkdir()
    (sd / "effects.json").write_text(
        json.dumps(
            {"custom_fog": {"id": "custom_fog", "name": "안개"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = tool._main(["catalog-fill", str(sd)])

    assert rc == 0, capsys.readouterr().err
    effects = _read_json(sd / "effects.json")
    assert "custom_fog" not in effects
    assert set(effects) == {"heal", "mp_restore", "dc_down", "dc_up"}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

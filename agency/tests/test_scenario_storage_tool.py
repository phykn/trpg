"""scenario_storage upload command maps local scenario files to bucket keys."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from agency.story.tools import storage


@pytest.fixture
def fake_storage_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "fake-key")
    monkeypatch.setenv("SUPABASE_SCENARIO_BUCKET", "fake-bucket")


def test_upload_uploads_every_file(capsys, tmp_path, fake_storage_env):
    sd = tmp_path / "default"
    sd.mkdir()
    (sd / "world.md").write_text("테스트", encoding="utf-8")
    (sd / "items").mkdir()
    (sd / "items" / "sword.json").write_text(
        json.dumps({"id": "sword"}), encoding="utf-8"
    )

    fake = AsyncMock()
    fake.put_bytes = AsyncMock(return_value=None)
    fake.aclose = AsyncMock(return_value=None)

    with patch("agency.story.tools.storage._Storage", return_value=fake):
        rc = storage._main(["upload", str(sd)])

    assert rc == 0, capsys.readouterr().err
    out_text = capsys.readouterr().out
    assert "OK" in out_text

    keys = [call.args[0] for call in fake.put_bytes.await_args_list]
    assert "default/world.md" in keys
    assert "default/items/sword.json" in keys

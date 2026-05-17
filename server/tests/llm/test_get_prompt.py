from pathlib import Path

from src.llm.calls import runner
from src.llm.calls.runner import get_prompt


def test_get_prompt_joins_kernel_and_agent(tmp_path, monkeypatch):
    (tmp_path / "_kernel.ko.md").write_text("KERNEL\n", encoding="utf-8")
    agent_dir = tmp_path / "agentX"
    agent_dir.mkdir()
    (agent_dir / "prompt.ko.md").write_text("AGENT\n", encoding="utf-8")

    monkeypatch.setattr(runner, "_PROMPTS_ROOT", tmp_path)
    get_prompt.cache_clear()

    out = get_prompt("agentX", "ko")
    assert out == "KERNEL\n\n\n---\n\nAGENT\n"


def test_get_prompt_falls_back_when_kernel_missing(tmp_path, monkeypatch):
    agent_dir = tmp_path / "agentY"
    agent_dir.mkdir()
    (agent_dir / "prompt.ko.md").write_text("AGENT_ONLY\n", encoding="utf-8")

    monkeypatch.setattr(runner, "_PROMPTS_ROOT", tmp_path)
    get_prompt.cache_clear()

    assert get_prompt("agentY", "ko") == "AGENT_ONLY\n"


def test_get_prompt_handles_nested_agent_path(tmp_path, monkeypatch):
    nested = tmp_path / "narrate" / "body"
    nested.mkdir(parents=True)
    (nested / "prompt.ko.md").write_text("BODY\n", encoding="utf-8")

    monkeypatch.setattr(runner, "_PROMPTS_ROOT", tmp_path)
    get_prompt.cache_clear()

    assert get_prompt("narrate/body", "ko") == "BODY\n"


def test_get_prompt_caches_per_locale(tmp_path, monkeypatch):
    (tmp_path / "_kernel.ko.md").write_text("K_KO\n", encoding="utf-8")
    (tmp_path / "_kernel.en.md").write_text("K_EN\n", encoding="utf-8")
    agent_dir = tmp_path / "agentZ"
    agent_dir.mkdir()
    (agent_dir / "prompt.ko.md").write_text("KO\n", encoding="utf-8")
    (agent_dir / "prompt.en.md").write_text("EN\n", encoding="utf-8")

    monkeypatch.setattr(runner, "_PROMPTS_ROOT", tmp_path)
    get_prompt.cache_clear()

    a = get_prompt("agentZ", "ko")
    b = get_prompt("agentZ", "ko")
    assert a is b  # same cached object
    c = get_prompt("agentZ", "en")
    assert a != c


def test_get_prompt_reloads_when_prompt_file_changes(tmp_path, monkeypatch):
    agent_dir = tmp_path / "agentHot"
    agent_dir.mkdir()
    prompt_path = agent_dir / "prompt.ko.md"
    prompt_path.write_text("ONE\n", encoding="utf-8")

    monkeypatch.setattr(runner, "_PROMPTS_ROOT", tmp_path)
    get_prompt.cache_clear()

    assert get_prompt("agentHot", "ko") == "ONE\n"

    prompt_path.write_text("TWO\n", encoding="utf-8")
    current = prompt_path.stat().st_mtime + 2
    import os

    os.utime(prompt_path, (current, current))

    assert get_prompt("agentHot", "ko") == "TWO\n"


def test_packaged_prompts_load_for_every_agent():
    """Every shipped agent under src/locale/prompts/ has a working ko build."""
    agents = [
        "classify",
    ]
    get_prompt.cache_clear()
    for agent in agents:
        text = get_prompt(agent, "ko")
        assert text, f"{agent} ko prompt is empty"
        assert "당신" in text or "합니다체" in text, (
            f"{agent} ko build missing 합니다체 register marker"
        )


def test_prompts_root_resolves_to_repo_path():
    expected = Path(__file__).resolve().parents[2] / "src" / "locale" / "prompts"
    assert runner._PROMPTS_ROOT == expected

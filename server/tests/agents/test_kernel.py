"""Unit tests for load_prompt — the kernel-prepending helper in agents/_runner.py."""

from src.llm.calls import _runner
from src.llm.calls._runner import load_prompt


def test_load_prompt_prepends_kernel(tmp_path, monkeypatch):
    """load_prompt prepends the kernel content before the agent's prompt.md."""
    agent_dir = tmp_path / "fake"
    agent_dir.mkdir()
    agent_file = agent_dir / "runner.py"
    agent_file.write_text("# stub", encoding="utf-8")
    (agent_dir / "prompt.md").write_text("AGENT\n", encoding="utf-8")

    monkeypatch.setattr(_runner, "_KERNEL", "KERNEL\n")

    out = load_prompt(str(agent_file))

    assert out == "KERNEL\n\n\n---\n\nAGENT\n"


def test_load_prompt_substitutes_placeholders(tmp_path, monkeypatch):
    """load_prompt replaces {{KEY}} tokens in the merged text."""
    agent_dir = tmp_path / "fake"
    agent_dir.mkdir()
    agent_file = agent_dir / "runner.py"
    agent_file.write_text("# stub", encoding="utf-8")
    (agent_dir / "prompt.md").write_text(
        "Forbidden: {{CHAR_FORBIDDEN}}\n", encoding="utf-8"
    )

    monkeypatch.setattr(_runner, "_KERNEL", "KERNEL\n")

    out = load_prompt(str(agent_file), substitutions={"CHAR_FORBIDDEN": "name/race"})

    assert "Forbidden: name/race" in out
    assert "{{CHAR_FORBIDDEN}}" not in out


def test_load_prompt_falls_back_when_kernel_empty(tmp_path, monkeypatch):
    """When _KERNEL is empty (file missing at boot), load_prompt returns the agent's prompt verbatim."""
    agent_dir = tmp_path / "fake"
    agent_dir.mkdir()
    agent_file = agent_dir / "runner.py"
    agent_file.write_text("# stub", encoding="utf-8")
    (agent_dir / "prompt.md").write_text("AGENT_ONLY\n", encoding="utf-8")

    monkeypatch.setattr(_runner, "_KERNEL", "")

    assert load_prompt(str(agent_file)) == "AGENT_ONLY\n"

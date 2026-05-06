from pathlib import Path
import tempfile

from src.llm.calls._runner import get_prompt


def test_get_prompt_substitutes_locale_blocks(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        agent_dir = Path(d) / "agentX"
        agent_dir.mkdir()
        (agent_dir / "prompt.md").write_text(
            "Output rules: {{LOCALE_OUTPUT_LANGUAGE}}\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            "src.llm.calls._runner._kernel_blocks_for",
            lambda locale: {"LOCALE_OUTPUT_LANGUAGE": f"<lang={locale}>"},
        )
        get_prompt.cache_clear()
        out_ko = get_prompt(str(agent_dir / "prompt.md"), "ko")
        out_en = get_prompt(str(agent_dir / "prompt.md"), "en")
        assert "<lang=ko>" in out_ko
        assert "<lang=en>" in out_en


def test_get_prompt_caches_per_locale(monkeypatch):
    calls = {"n": 0}

    def fake_blocks(locale: str) -> dict[str, str]:
        calls["n"] += 1
        return {}

    monkeypatch.setattr("src.llm.calls._runner._kernel_blocks_for", fake_blocks)
    get_prompt.cache_clear()
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "agentY" / "prompt.md"
        p.parent.mkdir()
        p.write_text("static body\n", encoding="utf-8")
        get_prompt(str(p), "ko")
        get_prompt(str(p), "ko")  # cached
        assert calls["n"] == 1
        get_prompt(str(p), "en")
        assert calls["n"] == 2

from src.llm.calls._runner import get_prompt


_AGENT_FILES = [
    "server/src/llm/calls/classify/runner.py",
    "server/src/llm/calls/recommend/runner.py",
    "server/src/llm/calls/summon/runner.py",
    "server/src/llm/calls/combat_narrate/runner.py",
    "server/src/llm/calls/narrate/body/runner.py",
    "server/src/llm/calls/narrate/extract/runner.py",
]


def _kernel_section(text: str) -> str:
    """Return only the kernel portion (before the --- separator)."""
    return text.split("\n---\n")[0]


def test_ko_kernel_includes_korean_register_marker():
    """ko로 빌드된 prompt에는 한국어 register 마커가 포함돼야 한다."""
    for af in _AGENT_FILES:
        get_prompt.cache_clear()
        text = get_prompt(af, "ko")
        assert "합니다체" in text or "당신" in text, f"{af} ko build missing register marker"


def test_en_kernel_locale_blocks_are_empty():
    """en은 v1에서 빈 문자열이라 kernel 섹션에 한국어 마커가 들어가면 안 됨."""
    for af in _AGENT_FILES:
        get_prompt.cache_clear()
        kernel = _kernel_section(get_prompt(af, "en"))
        assert "합니다체" not in kernel, f"{af} en build leaks 합니다체 marker in kernel section"


def test_no_unsubstituted_locale_tokens():
    """{{LOCALE_*}} 토큰이 빌드 후 남아 있으면 catalog 키가 빠진 것."""
    for af in _AGENT_FILES:
        get_prompt.cache_clear()
        for locale in ("ko", "en"):
            text = get_prompt(af, locale)
            assert "{{LOCALE_" not in text, f"{af} {locale}: unresolved LOCALE token"

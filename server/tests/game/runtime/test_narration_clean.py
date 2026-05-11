from src.game.runtime.narration_clean import clean_narration


def test_clean_narration_drops_exact_recent_repeat():
    recent = "테스트 가이드는 대답하지 않고 당신을 다시 봅니다."

    assert clean_narration(recent, max_chars=420, recent_texts=[recent]) == ""

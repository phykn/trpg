from collections.abc import Iterable


def clean_narration(
    text: str,
    *,
    max_chars: int,
    recent_texts: Iterable[str] = (),
) -> str:
    cleaned = " ".join(text.split())
    if _matches_recent(cleaned, recent_texts):
        return ""
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip()


def _matches_recent(text: str, recent_texts: Iterable[str]) -> bool:
    normalized = _normalize(text)
    if len(normalized) < 18:
        return False
    for recent in recent_texts:
        recent_normalized = _normalize(recent)
        if len(recent_normalized) < 18:
            continue
        if normalized == recent_normalized:
            return True
        shorter, longer = sorted(
            (normalized, recent_normalized),
            key=len,
        )
        if len(shorter) >= 24 and shorter in longer:
            return True
    return False


def _normalize(text: str) -> str:
    return "".join(text.split())

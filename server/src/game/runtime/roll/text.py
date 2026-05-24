import difflib
import re
from typing import Any

from src.game.domain.action import Action
from src.game.domain.content import node_label, node_text
from src.locale.render import render
from src.locale.terms import ROLL_MEANINGFUL_CLUE_TERMS, ROLL_NO_CLUE_MARKERS

from .pending import roll_action_target


def roll_result_texts(resolved: Any) -> list[str]:
    result_texts = [
        render(
            "runtime.roll.result.success"
            if resolved.outcome == "success"
            else "runtime.roll.result.failure",
            resolved.runtime.progress.locale,
            check=resolved.roll_entry.check,
        )
    ]
    result_texts.append(roll_resolution_text(resolved))
    result_texts.extend(_completed_quest_descriptions(resolved))
    return result_texts


def roll_fallback_text(resolved: Any) -> str:
    descriptions = _completed_quest_descriptions(resolved)
    if descriptions and resolved.outcome == "success":
        return descriptions[0]
    return roll_resolution_text(resolved)


def prepare_roll_narration_text(
    resolved: Any,
    text: str,
    *,
    ensure_resolution: bool,
) -> str:
    text = _clean_roll_meta_phrase(text)
    text = strip_repeated_preroll_text(resolved, text)
    text = _append_missing_completed_quest_text(resolved, text)
    text = _remove_success_contradiction(resolved, text)
    if ensure_resolution:
        text = _ensure_roll_resolution_text(resolved, text)
    return text


def strip_repeated_preroll_text(resolved: Any, text: str) -> str:
    preroll = resolved.pending.get("body")
    if not isinstance(preroll, str) or not preroll.strip() or not text.strip():
        return text

    body_sentences = _split_korean_sentences(preroll)
    if not body_sentences:
        return text
    out = _split_korean_sentences(text)
    removed = 0
    while out and _looks_like_preroll_repeat(out[0], body_sentences):
        out.pop(0)
        removed += 1
    if removed == 0 or not out:
        return text
    return " ".join(out).strip()


def roll_resolution_text(resolved: Any) -> str:
    locale = resolved.runtime.progress.locale
    key = _roll_resolution_key(resolved.action, resolved.outcome)
    if resolved.action.verb != "speak":
        return render(key, locale)
    target_id = roll_action_target(resolved.action)
    target = resolved.runtime.graph.nodes.get(target_id) if target_id else None
    if target is None:
        return render("runtime.roll.resolve.default." + resolved.outcome, locale)
    target_name = node_label(resolved.runtime.content, target)
    return render(key, locale, target=target_name)


def _roll_resolution_key(action: Action, outcome: str) -> str:
    if action.verb == "perceive":
        return f"runtime.roll.resolve.perceive.{outcome}"
    if action.verb == "speak":
        return f"runtime.roll.resolve.speak.{outcome}"
    return f"runtime.roll.resolve.default.{outcome}"


def _ensure_roll_resolution_text(resolved: Any, text: str) -> str:
    resolution_text = roll_resolution_text(resolved)
    if not resolution_text:
        return text
    normalized_resolution = _normalize_korean_sentence(resolution_text)
    normalized_text = _normalize_korean_sentence(text)
    if normalized_resolution and normalized_resolution in normalized_text:
        return text
    if not text.strip():
        return resolution_text
    return f"{resolution_text} {text.strip()}"


def _clean_roll_meta_phrase(text: str) -> str:
    return re.sub(
        _roll_meta_phrase_pattern(),
        "",
        text,
    ).strip()


def _remove_success_contradiction(resolved: Any, text: str) -> str:
    if resolved.outcome != "success":
        return text
    if resolved.action.verb != "perceive":
        return text
    sentences = _split_korean_sentences(text)
    if not sentences:
        return text
    kept = [
        sentence
        for sentence in sentences
        if not _looks_like_no_clue_contradiction(sentence)
    ]
    if len(kept) == len(sentences):
        return text
    return " ".join(kept).strip()


def _looks_like_no_clue_contradiction(sentence: str) -> bool:
    normalized = _normalize_korean_sentence(sentence)
    if not any(term in normalized for term in ROLL_MEANINGFUL_CLUE_TERMS):
        return False
    return any(marker in normalized for marker in ROLL_NO_CLUE_MARKERS)


def _looks_like_preroll_repeat(sentence: str, body_sentences: list[str]) -> bool:
    normalized = _normalize_korean_sentence(sentence)
    if not normalized:
        return False
    for body in body_sentences:
        body_normalized = _normalize_korean_sentence(body)
        if not body_normalized:
            continue
        if normalized in body_normalized or body_normalized in normalized:
            return True
        if difflib.SequenceMatcher(None, normalized, body_normalized).ratio() >= 0.72:
            return True
    return False


def _split_korean_sentences(text: str) -> list[str]:
    parts = re.findall(r"[^.!?。！？]+[.!?。！？]?", text)
    return [part.strip() for part in parts if part.strip()]


def _normalize_korean_sentence(text: str) -> str:
    return re.sub(_non_korean_sentence_chars_pattern(), "", text).lower()


def _roll_meta_phrase_pattern() -> str:
    stats = "|".join(
        [
            _codepoint_text(0xBAB8, 0xB825),
            _codepoint_text(0xBBFC, 0xCCA9),
            _codepoint_text(0xC9C0, 0xB825),
            _codepoint_text(0xB9E4, 0xB825),
            _codepoint_text(0xCCB4, 0xB825),
            _codepoint_text(0xADFC, 0xB825),
        ]
    )
    check = _codepoint_text(0xD310, 0xC815)
    possessive = _codepoint_text(0xC758)
    success = _codepoint_text(0xC131, 0xACF5)
    failure = _codepoint_text(0xC2E4, 0xD328)
    by = _codepoint_text(0xC73C, 0xB85C)
    return rf"(?:(?:{stats})\s*)?{check}(?:{possessive})?\s*(?:{success}|{failure})(?:{by})?[,，]?\s*"


def _non_korean_sentence_chars_pattern() -> str:
    return f"[^0-9A-Za-z{chr(0xAC00)}-{chr(0xD7A3)}]+"


def _codepoint_text(*values: int) -> str:
    return "".join(chr(value) for value in values)


def _append_missing_completed_quest_text(
    resolved: Any,
    text: str,
) -> str:
    descriptions = _completed_quest_descriptions(resolved)
    if resolved.outcome != "success" or not descriptions:
        return text
    missing = [description for description in descriptions if description not in text]
    if not missing:
        return text
    if not text.strip():
        return "\n\n".join(missing)
    return f"{text.rstrip()}\n\n{missing[0]}"


def _completed_quest_descriptions(resolved: Any) -> list[str]:
    out: list[str] = []
    for quest_id in resolved.completed_quest_ids:
        quest = resolved.runtime.graph.nodes.get(quest_id)
        if quest is None or quest.type != "quest":
            continue
        description = node_text(resolved.runtime.content, quest, "description")
        if description:
            out.append(description)
    return out

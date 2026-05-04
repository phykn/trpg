"""Narrate prompt input — world / session / history layers."""

from typing import TYPE_CHECKING

from ..domain.clock import day_phase
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from ..ontology.queries import quests_in_chapter

if TYPE_CHECKING:
    from ..persistence.repo import ScenarioRepo


_QUOTE_OPEN_TO_CLOSE = {"「": "」", "『": "』"}
_SUBJECT_JOSA = ("가", "이", "은", "는", "께서")
_PRONOUN_SUBJECTS = ("그가", "그는", "그녀가", "그녀는")

# History-block headers + per-line builders. Hoisted so the layer body stays free of inline Korean prompt fragments.
_HISTORY_HEADER_DEAD = "=== 사망 — 다시 등장시키거나 발화시키지 말 것 ==="
_HISTORY_HEADER_SUMMARY = "=== 이전 요약 ==="
_HISTORY_HEADER_DIALOGUE = "=== 최근 대화 ==="

# Cap recent_dialogue narrator bodies before they enter the narrate prompt:
# the LLM was verbatim-echoing prior-turn narrators as a prefix in the new
# turn (R2 D2). ~80-char opener (1-2 short sentences) is enough continuity
# context without giving the LLM a paste target.
_DIALOGUE_NARRATOR_MAX_CHARS = 80
_SENTENCE_END_CHARS = ".!?"


def _truncate_narrator(text: str) -> str:
    """Cap at _DIALOGUE_NARRATOR_MAX_CHARS, ending at the nearest sentence
    boundary at or before the cap when possible. Append a `…` marker only
    when truncated."""
    if len(text) <= _DIALOGUE_NARRATOR_MAX_CHARS:
        return text
    cap = _DIALOGUE_NARRATOR_MAX_CHARS
    for end_pos in range(cap, 0, -1):
        if text[end_pos - 1] in _SENTENCE_END_CHARS:
            return text[:end_pos].rstrip() + "…"
    return text[:cap].rstrip() + "…"


def _format_corpse_line(name: str) -> str:
    return f"- {name} (생전 발화가 아래 대화에 남아 있을 수 있으나 더 이상 말하지 않습니다)"


def _format_summary_entry(turn: int, summary: str) -> str:
    return f"[턴 {turn}] — {summary}"


def _format_dialogue_entry(turn: int, player: str, narrator_redacted: str) -> str:
    return f"[턴 {turn}]\n  플레이어: {player}\n  서술자: {_truncate_narrator(narrator_redacted)}"


def redact_dead_quotes(text: str, dead_names: list[str]) -> str:
    """Strip Korean direct-quote blocks attributed to dead NPCs. Stateful walk so pronoun continuation (그는 / 그녀는) keeps the named speaker beyond the immediate window."""
    if not dead_names or not text:
        return text
    name_set = {n for n in dead_names if n}
    out: list[str] = []
    i = 0
    n = len(text)
    speaker_is_dead = False
    while i < n:
        ch = text[i]
        close = _QUOTE_OPEN_TO_CLOSE.get(ch)
        if close is not None:
            close_idx = text.find(close, i + 1)
            if close_idx == -1:
                out.append(text[i:])
                break
            if speaker_is_dead:
                out.append("…")
            else:
                out.append(text[i : close_idx + 1])
            i = close_idx + 1
            continue

        kind, length = _classify_subject_at(text, i, name_set)
        if kind == "dead":
            speaker_is_dead = True
            out.append(text[i : i + length])
            i += length
            continue
        if kind == "alive":
            speaker_is_dead = False
            out.append(text[i : i + length])
            i += length
            continue
        if kind == "pronoun":
            # Continuation: don't update speaker_is_dead.
            out.append(text[i : i + length])
            i += length
            continue

        out.append(ch)
        i += 1
    return "".join(out)


def _classify_subject_at(
    text: str, i: int, dead_names: set[str]
) -> tuple[str | None, int]:
    """Return (kind, length) for a subject pattern at `text[i]`. Kinds: 'dead', 'alive', 'pronoun'."""
    # Match in priority order: dead names first, then 당신, then pronoun continuation, then generic subject.
    for name in dead_names:
        for josa in _SUBJECT_JOSA:
            pat = name + josa
            if text.startswith(pat, i):
                return "dead", len(pat)
    for josa in _SUBJECT_JOSA:
        pat = "당신" + josa
        if text.startswith(pat, i):
            return "alive", len(pat)
    for pat in _PRONOUN_SUBJECTS:
        if text.startswith(pat, i):
            return "pronoun", len(pat)
    j = i
    while j < len(text) and "가" <= text[j] <= "힣":
        j += 1
    if j > i and j < len(text):
        for josa in _SUBJECT_JOSA:
            if text.startswith(josa, j):
                return "alive", j - i + len(josa)
    return None, 0


async def build_world_layer(
    scenario_repo: "ScenarioRepo", profile: str, *, missing_ok: bool = False
) -> str:
    """Read <profile>/world.md via the ScenarioRepo. `missing_ok=True` returns empty string instead of raising."""
    return await scenario_repo.read_world_md(profile, missing_ok=missing_ok)


def build_session_layer(state: GameState, graph: GameGraph | None = None) -> dict:
    chapter_data = None
    # ssot-allow: active-chapter is a value predicate, not a relational scan.
    active_chapter = next(
        (c for c in state.chapters.values() if c.status == "active"),
        None,
    )
    if active_chapter:
        if graph is None:
            graph = state.graph()
        active_quests = []
        for qid in quests_in_chapter(graph, active_chapter.id):
            q = state.quests.get(qid)
            if q is None or q.status != "active":
                continue
            active_quests.append(
                {
                    "title": q.title,
                    "summary": q.summary,
                }
            )
        chapter_data = {
            "title": active_chapter.title,
            "summary": active_chapter.summary,
            "quests": active_quests,
        }
    return {"chapter": chapter_data, "day_phase": day_phase(state.turn_count)}


def build_history_layer(state: GameState, corpses: list[dict] | None = None) -> str:
    dialogue_turns = {d.turn for d in state.recent_dialogue}
    summary_entries = [e for e in state.turn_log if e.turn not in dialogue_turns]

    blocks: list[str] = []

    dead_names = [
        c["name"] for c in (corpses or []) if isinstance(c, dict) and c.get("name")
    ]

    if corpses:
        lines = [_HISTORY_HEADER_DEAD]
        for c in corpses:
            lines.append(_format_corpse_line(c["name"]))
        blocks.append("\n".join(lines))

    if summary_entries:
        lines = [_HISTORY_HEADER_SUMMARY]
        for e in summary_entries:
            lines.append(_format_summary_entry(e.turn, e.summary))
        blocks.append("\n".join(lines))

    if state.recent_dialogue:
        items = [
            _format_dialogue_entry(
                d.turn, d.player, redact_dead_quotes(d.narrator, dead_names)
            )
            for d in state.recent_dialogue
        ]
        blocks.append(_HISTORY_HEADER_DIALOGUE + "\n" + "\n".join(items))

    return "\n\n".join(blocks)

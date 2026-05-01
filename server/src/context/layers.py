"""Narrate prompt input — world / session / history layers."""

from typing import TYPE_CHECKING

from ..domain.clock import day_phase
from ..domain.state import GameState
from ..ontology.graph import GameGraph, build_graph
from ..ontology.queries import quests_in_chapter

if TYPE_CHECKING:
    from ..persistence.repo import ScenarioRepo


_QUOTE_OPEN_TO_CLOSE = {"「": "」", "『": "』"}
_SUBJECT_JOSA = ("가", "이", "은", "는", "께서")
_PRONOUN_SUBJECTS = ("그가", "그는", "그녀가", "그녀는")


def redact_dead_quotes(text: str, dead_names: list[str]) -> str:
    """Strip Korean direct-quote blocks attributed to dead NPCs.

    Walks `text` once, tracking the most recent named subject as state.
    Each `「` / `『` block inherits whoever was last marked as the speaker;
    if that speaker is in `dead_names`, the block is replaced with `…`.

    Subject classification at every position:
    - `<dead_name>{가|이|은|는|께서}` → speaker = dead.
    - `당신{가|이|은|는|께서}` → speaker = player (alive, resets dead).
    - `그(가|는)` / `그녀(가|는)` → continuation pronoun, doesn't change
      the recorded speaker. This is what catches `에드릭은 ... 「Q1」 그는
      ... 「Q2」` — the pronoun keeps Edrik as the attributed speaker for
      Q2 even though his name doesn't reappear in the immediate window.
    - any other `<hangul>+{subject_josa}` → resets to "not dead". A live
      NPC, a scene object (`안개가`, `분수는`), or 당신 all break the
      dead-subject inheritance the safe way (under-redact, never falsely
      redact a live speaker).
    - object / dative markers (`을/를/에/에게/한테/와/과/의 …`) don't
      participate — `노인을 떠올린다. 「잘 지내시오.」` correctly keeps the
      quote because the dead name only appears as the player's mental
      object, not as a subject.

    Earlier window-scan version missed the common pattern where the LLM
    introduces a corpse with a subject marker, opens a quote, then opens
    a second quote a few sentences later anchored only by the pronoun
    `그는`. Stateful walk handles that without an arbitrarily wide window.

    Two callers — same single root cause:
    - `build_history_layer` → strips from `recent_dialogue` so the LLM
      doesn't see resurrected speech as an in-context pattern to mimic.
    - `consume_narrate` → strips from the post-LLM body before persisting
      to log_entry / dialogue / turn_log so a one-off slip doesn't
      compound across turns.
    """
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
                # Unmatched opener — leave the rest as-is.
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
            # Continuation — don't change `speaker_is_dead`.
            out.append(text[i : i + length])
            i += length
            continue

        out.append(ch)
        i += 1
    return "".join(out)


def _classify_subject_at(
    text: str, i: int, dead_names: set[str]
) -> tuple[str | None, int]:
    """Return (kind, length) for a subject pattern starting at `text[i]`,
    or (None, 0) if no subject pattern starts here.

    kind ∈ {'dead', 'alive', 'pronoun'} — see `redact_dead_quotes`.
    """
    # 1. Dead-name + subject josa (most specific).
    for name in dead_names:
        for josa in _SUBJECT_JOSA:
            pat = name + josa
            if text.startswith(pat, i):
                return "dead", len(pat)
    # 2. 당신 (player) + subject josa.
    for josa in _SUBJECT_JOSA:
        pat = "당신" + josa
        if text.startswith(pat, i):
            return "alive", len(pat)
    # 3. 그/그녀 + 가/는 — continuation pronoun.
    for pat in _PRONOUN_SUBJECTS:
        if text.startswith(pat, i):
            return "pronoun", len(pat)
    # 4. Generic <hangul>+ + subject josa — any other subject. Reset to
    #    "not dead". We don't track who exactly; we only care that a new
    #    subject has taken over from the previous dead one.
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
    """Read <profile>/world.md via the ScenarioRepo. Strict by default — set
    missing_ok=True for callers (combat_auto narrate input, encounter summon)
    that should fall back to an empty string."""
    return await scenario_repo.read_world_md(profile, missing_ok=missing_ok)


def build_session_layer(state: GameState, graph: GameGraph | None = None) -> dict:
    chapter_data = None
    # ssot-allow: filtering chapters by status is an attribute lookup —
    # active-chapter is a value predicate, not a relational scan.
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
        lines = ["=== 사망 — 다시 등장시키거나 발화시키지 말 것 ==="]
        for c in corpses:
            lines.append(
                f"- {c['name']} (생전 발화가 아래 대화에 남아 있을 수 있으나 더 이상 말하지 않습니다)"
            )
        blocks.append("\n".join(lines))

    if summary_entries:
        lines = ["=== 이전 요약 ==="]
        for e in summary_entries:
            lines.append(f"[턴 {e.turn}] — {e.summary}")
        blocks.append("\n".join(lines))

    if state.recent_dialogue:
        items = [
            f"[턴 {d.turn}]\n  플레이어: {d.player}\n  서술자: {redact_dead_quotes(d.narrator, dead_names)}"
            for d in state.recent_dialogue
        ]
        blocks.append("=== 최근 대화 ===\n" + "\n".join(items))

    return "\n\n".join(blocks)

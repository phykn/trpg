"""Generic entity writer — LLM call + Pydantic validation + self-correction loop + disk write.

Entity-level rules (stat invariants, HP/MP formula, NPC skill, equipment slot
matching, carry weight, etc.) live in `server/src/engines/invariants.py`.
This module only handles cross-ref between entity manifests during the
incremental build (race_id ∈ races, etc.); the rest is dispatched to `check.X`.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ValidationError

from src.domain.entities import Chapter, Character, Item, Location, Quest, Race, Skill
from src.engines.invariants import check_character, check_item, check_seed_character
from src.llm import LLMClient

# --- types & errors --------------------------------------------------------

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


def strip_code_fences(text: str) -> str:
    """Strip leading/trailing ```...``` fences if present. Smaller local models
    sometimes emit fenced JSON despite explicit "no fences" instructions; the
    pipeline normalizes the response shape rather than relying on prompt
    discipline."""
    s = text.strip()
    if not s.startswith("```"):
        return s
    lines = s.splitlines()
    if lines[0].lstrip("`").strip().lower() in ("", "json"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


class EntityWriterError(Exception):
    """Raised on semantic-validation failures or on-disk conflicts."""


def _noop_check(entity: BaseModel, refs: dict[str, set[str]]) -> None:
    return None


@dataclass(frozen=True)
class EntitySpec:
    kind: str
    model: type[BaseModel]
    sub_dir: str
    fragment: str
    ref_kinds: tuple[str, ...] = ()
    check_refs: Callable[[BaseModel, dict[str, set[str]]], None] = field(
        default=_noop_check
    )


# --- manifest cross-ref checks --------------------------------------------

def _check_location_refs(loc: Location, refs: dict[str, set[str]]) -> None:
    location_ids = refs.get("location", set())
    item_ids = refs.get("item", set())
    for c in loc.connections:
        if c.target_id == loc.id:
            raise EntityWriterError(
                f"location.connections points at itself ({loc.id})."
            )
        if c.target_id not in location_ids:
            raise EntityWriterError(
                f"location.connections.target_id={c.target_id!r} not found in scenario locations. "
                f"Valid ids: {sorted(location_ids)}"
            )
    for iid in loc.item_ids:
        if iid not in item_ids:
            raise EntityWriterError(
                f"location.item_ids entry {iid!r} not found in scenario items."
            )
    for iid in loc.hidden_items:
        if iid not in item_ids:
            raise EntityWriterError(
                f"location.hidden_items entry {iid!r} not found in scenario items."
            )


def _check_character_refs(ch: Character, refs: dict[str, set[str]]) -> None:
    """Manifest cross-ref only — race_id/location_id/skill_ids pool checks.
    Other rules (stats, HP/MP, equipment slots, carry, NPC seed extras) are
    dispatched to `check_seed_character` in `write_entity`."""
    races = refs.get("race", set())
    if ch.race_id not in races:
        raise EntityWriterError(
            f"character.race_id={ch.race_id!r} not found in scenario races. "
            f"Valid ids: {sorted(races)}"
        )
    locations = refs.get("location", set())
    if ch.location_id is not None and ch.location_id not in locations:
        raise EntityWriterError(
            f"character.location_id={ch.location_id!r} not found in scenario locations. "
            f"Valid ids: {sorted(locations)}"
        )
    skills = refs.get("skill", set())
    for sid in (*ch.racial_skill_ids, *ch.learned_skill_ids):
        if sid not in skills:
            raise EntityWriterError(
                f"character.skill_id={sid!r} not found in scenario skills. "
                "Create that skill first."
            )


def _check_race_refs(r: Race, refs: dict[str, set[str]]) -> None:
    skills = refs.get("skill", set())
    for sid in r.racial_skill_ids:
        if sid not in skills:
            raise EntityWriterError(
                f"race.racial_skill_id={sid!r} not found in scenario skills."
            )


TRIGGER_TARGET_KIND = {
    "character_death": "character",
    "location_enter": "location",
    "item_use": "item",
}


def _check_quest_refs(q: Quest, refs: dict[str, set[str]]) -> None:
    characters = refs.get("character", set())
    if q.giver_id not in characters:
        raise EntityWriterError(
            f"quest.giver_id={q.giver_id!r} not found in scenario characters."
        )
    for t in [*q.triggers, *q.fail_triggers]:
        target_kind = TRIGGER_TARGET_KIND.get(t.type)
        if target_kind is None:
            raise EntityWriterError(
                f"quest trigger (id={t.id}) type={t.type!r} unknown. "
                f"Valid values: {sorted(TRIGGER_TARGET_KIND)}"
            )
        pool = refs.get(target_kind, set())
        if t.target_id not in pool:
            raise EntityWriterError(
                f"quest trigger (id={t.id}) target_id={t.target_id!r} not found in the "
                f"{target_kind} pool."
            )
    quests = refs.get("quest", set())
    for pid in q.prerequisite_ids:
        if pid not in quests:
            raise EntityWriterError(
                f"quest.prerequisite_ids entry {pid!r} not found in scenario quests."
            )


def _check_chapter_refs(ch: Chapter, refs: dict[str, set[str]]) -> None:
    quests = refs.get("quest", set())
    for qid in ch.quest_ids:
        if qid not in quests:
            raise EntityWriterError(
                f"chapter.quest_ids entry {qid!r} not found in scenario quests."
            )


# --- spec table ------------------------------------------------------------

SPECS: dict[str, EntitySpec] = {
    "race": EntitySpec(
        kind="race", model=Race, sub_dir="races", fragment="race.md",
        ref_kinds=("skill",), check_refs=_check_race_refs,
    ),
    "location": EntitySpec(
        kind="location", model=Location, sub_dir="locations", fragment="location.md",
        ref_kinds=("location", "item"), check_refs=_check_location_refs,
    ),
    "skill": EntitySpec(
        kind="skill", model=Skill, sub_dir="skills", fragment="skill.md",
    ),
    "item": EntitySpec(
        kind="item", model=Item, sub_dir="items", fragment="item.md",
    ),
    "character": EntitySpec(
        kind="character", model=Character, sub_dir="characters", fragment="character.md",
        ref_kinds=("race", "location", "item", "skill"),
        check_refs=_check_character_refs,
    ),
    "quest": EntitySpec(
        kind="quest", model=Quest, sub_dir="quests", fragment="quest.md",
        ref_kinds=("character", "location", "item", "quest"),
        check_refs=_check_quest_refs,
    ),
    "chapter": EntitySpec(
        kind="chapter", model=Chapter, sub_dir="chapters", fragment="chapter.md",
        ref_kinds=("quest",), check_refs=_check_chapter_refs,
    ),
}


# --- build helpers ---------------------------------------------------------

def _load_dir(scenario_dir: Path, sub_dir: str) -> list[dict]:
    d = scenario_dir / sub_dir
    if not d.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]


def _build_system(
    *,
    base_path: Path,
    fragment_path: Path,
    scenario_dir: Path,
    spec: EntitySpec,
) -> str:
    parts = [
        base_path.read_text(encoding="utf-8"),
        "",
        "---",
        "",
        fragment_path.read_text(encoding="utf-8"),
        "",
        "---",
        "",
        "## scenario world.md",
        "",
        (scenario_dir / "world.md").read_text(encoding="utf-8"),
        "",
        f"## existing {spec.kind} list (JSON)",
        "",
        json.dumps(_load_dir(scenario_dir, spec.sub_dir), ensure_ascii=False, indent=2),
    ]
    for ref_kind in spec.ref_kinds:
        if ref_kind == spec.kind:
            continue
        ref_spec = SPECS[ref_kind]
        parts.append("")
        parts.append(f"## reference {ref_kind} list (JSON)")
        parts.append("")
        parts.append(
            json.dumps(
                _load_dir(scenario_dir, ref_spec.sub_dir), ensure_ascii=False, indent=2
            )
        )
    return "\n".join(parts)


def _collect_refs(scenario_dir: Path, spec: EntitySpec) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {
        spec.kind: {e["id"] for e in _load_dir(scenario_dir, spec.sub_dir)}
    }
    for rk in spec.ref_kinds:
        if rk == spec.kind:
            continue
        refs[rk] = {e["id"] for e in _load_dir(scenario_dir, SPECS[rk].sub_dir)}
    return refs


def _items_pool(scenario_dir: Path) -> dict[str, Item]:
    return {
        e["id"]: Item.model_validate(e)
        for e in _load_dir(scenario_dir, "items")
    }


def _skills_pool(scenario_dir: Path) -> dict[str, Skill]:
    return {
        e["id"]: Skill.model_validate(e)
        for e in _load_dir(scenario_dir, "skills")
    }


def _check_entity_invariants(
    entity: BaseModel, scenario_dir: Path, *, skeleton: bool = False
) -> None:
    """Dispatch to server.engines.invariants — all entity-level rules.

    Cross-ref between manifests is already done by spec.check_refs above; this
    runs the rule layer (stat invariants, HP/MP formula, NPC seed extras, etc).

    skeleton=True: only stateless rules (pair-trade, HP/MP formula). The
    items/skills pool isn't yet on disk, and character.inventory_ids /
    skill_ids are intentionally empty — pool-based checks would false-fire.
    """
    if isinstance(entity, Character):
        if skeleton:
            violations = check_character(entity)
        else:
            violations = check_seed_character(
                entity, _items_pool(scenario_dir), _skills_pool(scenario_dir)
            )
    elif isinstance(entity, Item):
        violations = check_item(entity)
    else:
        return
    if violations:
        raise EntityWriterError("invariant violation:\n" + "\n".join(violations))


def _check_id(
    entity: BaseModel, existing: set[str], force_id: str | None = None
) -> None:
    eid: str = entity.id  # type: ignore[attr-defined]
    if not ID_PATTERN.match(eid):
        raise EntityWriterError(
            f"id={eid!r} does not match the required pattern. ASCII snake_case ([a-z][a-z0-9_]{{1,30}}) required."
        )
    if force_id is not None and eid != force_id:
        raise EntityWriterError(
            f"id={eid!r} differs from the forced id={force_id!r}. "
            "Follow the hint's id directive exactly — do not change a single character."
        )
    if eid in existing:
        raise EntityWriterError(
            f"id={eid!r} collides with existing ids. Existing: {sorted(existing)}"
        )


# --- entry points ----------------------------------------------------------

async def write_entity(
    *,
    kind: str,
    scenario_dir: Path,
    agents_dir: Path,
    hint: str,
    llm: LLMClient,
    retries: int = 5,
    force_id: str | None = None,
    extra_check: Callable[[BaseModel], None] | None = None,
    think: bool = True,
    critic_prompt_path: Path | None = None,
    decomp_summary: str = "",
    skeleton: bool = False,
) -> tuple[BaseModel, list[dict]]:
    """Have the LLM produce one entity. On validation failure, self-correct
    up to `retries` times. After invariants pass, optionally run a single
    critic pass (`critic_prompt_path`); on critic NG, retry the writer
    once with the feedback. If the critic-retry result fails invariants,
    keep the first one (critic is advisory)."""
    if kind not in SPECS:
        raise EntityWriterError(
            f"unknown kind: {kind!r}. valid values: {sorted(SPECS)}"
        )
    spec = SPECS[kind]
    base_path = agents_dir / "_base.md"
    fragment_path = agents_dir / spec.fragment

    refs = _collect_refs(scenario_dir, spec)
    existing_ids = refs[spec.kind]

    system = _build_system(
        base_path=base_path,
        fragment_path=fragment_path,
        scenario_dir=scenario_dir,
        spec=spec,
    )
    user_msg = (
        hint.strip()
        if hint
        else f"(No hint — author one {spec.kind} using your own judgment.)"
    )
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]
    last_error: Exception | None = None
    final_entity: BaseModel | None = None
    final_answer: str | None = None
    agent_tag = f"story_write_{kind}"
    base_len = len(messages)  # system + initial hint; retries trim back to this.
    for _ in range(retries + 1):
        result = await llm.chat(messages=messages, think=think, agent=agent_tag)
        answer = strip_code_fences(result["answer"] or "")
        try:
            entity = spec.model.model_validate_json(answer)
            _check_id(entity, existing_ids, force_id=force_id)
            spec.check_refs(entity, refs)
            _check_entity_invariants(entity, scenario_dir, skeleton=skeleton)
            if extra_check is not None:
                extra_check(entity)
            final_entity = entity
            final_answer = answer
            break
        except (ValidationError, EntityWriterError, json.JSONDecodeError) as e:
            last_error = e
            # Roll back to base + only the latest assistant attempt + error so the
            # retry context stays bounded — without this the prior attempts pile
            # up and the cumulative input can exceed the server ctx window.
            messages = messages[:base_len]
            messages.append({"role": "assistant", "content": answer})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"The previous response failed validation: {e}. "
                        "Re-read the rules and output the corrected JSON only."
                    ),
                }
            )
    if final_entity is None:
        assert last_error is not None
        raise last_error

    messages.append({"role": "assistant", "content": final_answer})

    if critic_prompt_path is not None:
        from .critic import run_critic
        world_md = (scenario_dir / "world.md").read_text(encoding="utf-8")
        verdict = await run_critic(
            entity_kind=kind,
            entity_json=final_answer or "",
            world_md=world_md,
            decomp_summary=decomp_summary,
            prompt_path=critic_prompt_path,
            llm=llm,
        )
        if not verdict.ok:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Critic feedback:\n{verdict.feedback}\n"
                        "Apply the feedback above and output the corrected JSON only."
                    ),
                }
            )
            result = await llm.chat(messages=messages, think=think, agent=agent_tag)
            answer = strip_code_fences(result["answer"] or "")
            try:
                entity_v2 = spec.model.model_validate_json(answer)
                _check_id(entity_v2, existing_ids, force_id=force_id)
                spec.check_refs(entity_v2, refs)
                _check_entity_invariants(entity_v2, scenario_dir, skeleton=skeleton)
                if extra_check is not None:
                    extra_check(entity_v2)
                final_entity = entity_v2
                messages.append({"role": "assistant", "content": answer})
            except (ValidationError, EntityWriterError, json.JSONDecodeError):
                pass

    return final_entity, messages


def write_entity_to_disk(entity: BaseModel, scenario_dir: Path, kind: str) -> Path:
    """Write to scenarios/<scenario>/<sub_dir>/<id>.json. Raises EntityWriterError if the file already exists (no overwrite)."""
    spec = SPECS[kind]
    eid: str = entity.id  # type: ignore[attr-defined]
    out_path = scenario_dir / spec.sub_dir / f"{eid}.json"
    if out_path.exists():
        raise EntityWriterError(f"{out_path} already exists. Will not overwrite.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(entity.model_dump_json(indent=2), encoding="utf-8")
    return out_path

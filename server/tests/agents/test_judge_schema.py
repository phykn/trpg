import json

import pytest
from pydantic import ValidationError

from src.llm_calls.classify.schema import (
    ChainAction,
    CombatAction,
    PassAction,
    RollAction,
    coerce_judge_output,
    output_adapter,
    validate_judge_output,
)
from src.llm_calls.classify.semantics import (
    JudgeSemanticError,
    _surroundings_target_ids,
    check_semantics,
)


def test_korean_tier_accepted():
    r = output_adapter.validate_json(
        json.dumps(
            {
                "action": "roll",
                "tier": "보통",
                "stat": "CHA",
                "targets": ["g"],
                "reason": "설득 시도",
            },
            ensure_ascii=False,
        )
    )
    assert isinstance(r, RollAction) and r.tier == "보통" and r.reason == "설득 시도"


def test_old_english_tier_rejected():
    with pytest.raises(ValidationError):
        output_adapter.validate_json(
            json.dumps(
                {
                    "action": "roll",
                    "tier": "normal",
                    "stat": "CHA",
                    "targets": ["g"],
                    "reason": "x",
                }
            )
        )


def test_all_seven_tiers_accepted():
    for tier in ("매우 쉬움", "쉬움", "보통", "어려움", "매우 어려움", "전설", "신화"):
        output_adapter.validate_json(
            json.dumps(
                {
                    "action": "roll",
                    "tier": tier,
                    "stat": "STR",
                    "targets": ["x"],
                    "reason": "테스트",
                },
                ensure_ascii=False,
            )
        )


def test_roll_missing_reason_falls_back_to_default():
    # Schema-level safety net: if `reason` is omitted and the coerce hook is
    # bypassed (e.g. validate_json path on fenced answer), the field default
    # absorbs the miss instead of raising.
    r = output_adapter.validate_json(
        json.dumps(
            {"action": "roll", "tier": "보통", "stat": "CHA", "targets": ["g"]},
            ensure_ascii=False,
        )
    )
    assert isinstance(r, RollAction) and r.reason == "행동 판정"


def test_roll_rejects_empty_reason():
    with pytest.raises(ValidationError):
        output_adapter.validate_json(
            json.dumps(
                {
                    "action": "roll",
                    "tier": "보통",
                    "stat": "CHA",
                    "targets": ["g"],
                    "reason": "",
                },
                ensure_ascii=False,
            )
        )


def test_combat_targets_only_no_extras():
    c = output_adapter.validate_json(json.dumps({"action": "combat", "targets": ["x"]}))
    assert isinstance(c, CombatAction)
    with pytest.raises(ValidationError):
        output_adapter.validate_json(
            json.dumps(
                {"action": "combat", "targets": ["x"], "tier": "보통"},
                ensure_ascii=False,
            )
        )


def test_pass_action_no_extras():
    p = output_adapter.validate_json(json.dumps({"action": "pass"}))
    assert isinstance(p, PassAction)
    with pytest.raises(ValidationError):
        output_adapter.validate_json(
            json.dumps({"action": "pass", "tier": "보통"}, ensure_ascii=False)
        )


def test_surroundings_target_ids():
    sur = {
        "location": {"id": "tavern"},
        "entities": [{"id": "g"}, {"id": "i"}],
    }
    assert _surroundings_target_ids(sur) == {"tavern", "g", "i"}


def test_semantic_check_passes_when_targets_in_surroundings():
    sur = {"location": {"id": "tavern"}, "entities": [{"id": "g"}]}
    r = output_adapter.validate_json(
        json.dumps(
            {
                "action": "roll",
                "tier": "보통",
                "stat": "CHA",
                "targets": ["g"],
                "reason": "설득",
            },
            ensure_ascii=False,
        )
    )
    check_semantics(r, sur)


def test_semantic_check_rejects_hallucinated_target():
    sur = {"location": {"id": "tavern"}, "entities": [{"id": "g"}]}
    bad = output_adapter.validate_json(
        json.dumps(
            {
                "action": "roll",
                "tier": "보통",
                "stat": "CHA",
                "targets": ["ghost"],
                "reason": "설득",
            },
            ensure_ascii=False,
        )
    )
    with pytest.raises(JudgeSemanticError):
        check_semantics(bad, sur)


def _combat_action(target: str) -> CombatAction:
    return output_adapter.validate_json(
        json.dumps({"action": "combat", "targets": [target]}, ensure_ascii=False)
    )


def test_combat_rejects_friendly_npc_target():
    sur = {
        "location": {"id": "village_square"},
        "entities": [
            {"id": "player_01", "name": "p", "type": "player"},
            {
                "id": "gyeryun_chief",
                "name": "정운",
                "type": "npc",
                "friendly": True,
            },
        ],
    }
    with pytest.raises(JudgeSemanticError, match="friendly"):
        check_semantics(_combat_action("gyeryun_chief"), sur)


def test_combat_rejects_location_as_target():
    sur = {
        "location": {"id": "village_square"},
        "entities": [{"id": "bandit_01", "name": "산적", "type": "npc"}],
    }
    with pytest.raises(JudgeSemanticError, match="not an NPC entity"):
        check_semantics(_combat_action("village_square"), sur)


def test_combat_rejects_player_self_target():
    sur = {
        "location": {"id": "village_square"},
        "entities": [
            {"id": "player_01", "name": "p", "type": "player"},
            {"id": "bandit_01", "name": "산적", "type": "npc"},
        ],
    }
    with pytest.raises(JudgeSemanticError, match="only NPCs"):
        check_semantics(_combat_action("player_01"), sur)


def test_combat_accepts_neutral_npc_target():
    sur = {
        "location": {"id": "village_square"},
        "entities": [{"id": "bandit_01", "name": "산적", "type": "npc"}],
    }
    check_semantics(_combat_action("bandit_01"), sur)


def test_combat_accepts_hostile_npc_target():
    sur = {
        "location": {"id": "village_square"},
        "entities": [
            {
                "id": "bandit_01",
                "name": "산적",
                "type": "npc",
            }
        ],
    }
    check_semantics(_combat_action("bandit_01"), sur)


def test_combat_rejects_item_as_target():
    sur = {
        "location": {"id": "village_square"},
        "entities": [
            {"id": "shrine_stone", "name": "돌탁자", "type": "item"},
            {"id": "bandit_01", "name": "산적", "type": "npc"},
        ],
    }
    with pytest.raises(JudgeSemanticError, match="only NPCs"):
        check_semantics(_combat_action("shrine_stone"), sur)


def test_pass_accepts_corpse_id_target():
    """Addressing a corpse routes through pass + target_view (dead-marker).
    Without this, the corpse rule had to use targets=[] which left narrate
    with no explicit identity to anchor — the LLM degraded to alive-NPC-0
    fallback ('받을 사람이 보이지 않는다') instead of corpse-tone prose."""
    sur = {
        "location": {"id": "plaza_01"},
        "entities": [{"id": "player_01", "name": "p", "type": "player"}],
        "corpses": [{"id": "old_woman_01", "name": "노파"}],
    }
    p = output_adapter.validate_json(
        json.dumps({"action": "pass", "targets": ["old_woman_01"]}, ensure_ascii=False)
    )
    check_semantics(p, sur)


def test_pass_rejects_corpse_id_when_not_present():
    sur = {
        "location": {"id": "plaza_01"},
        "entities": [{"id": "player_01", "name": "p", "type": "player"}],
        "corpses": [],
    }
    p = output_adapter.validate_json(
        json.dumps({"action": "pass", "targets": ["ghost_id"]}, ensure_ascii=False)
    )
    with pytest.raises(JudgeSemanticError):
        check_semantics(p, sur)


def test_roll_still_rejects_corpse_id_target():
    """Corpse ids only unlock for pass. roll/combat/buy/sell on a corpse stays
    forbidden — you cannot persuade or fight the dead."""
    sur = {
        "location": {"id": "plaza_01"},
        "entities": [{"id": "player_01", "name": "p", "type": "player"}],
        "corpses": [{"id": "old_woman_01", "name": "노파"}],
    }
    r = output_adapter.validate_json(
        json.dumps(
            {
                "action": "roll",
                "tier": "보통",
                "stat": "CHA",
                "targets": ["old_woman_01"],
                "reason": "설득",
            },
            ensure_ascii=False,
        )
    )
    with pytest.raises(JudgeSemanticError):
        check_semantics(r, sur)


def test_coerce_promotes_phase_changing_chain_part_to_top_level():
    # LLM occasionally wraps a phase-changing action (combat / roll / rest /
    # flee / reject / summon_combat) inside chain.parts even though the schema
    # rejects it. The coerce hook promotes the first such part to be the
    # top-level action, dropping the rest.
    raw = {
        "action": "chain",
        "parts": [
            {"action": "use", "item_id": "herb_01"},
            {
                "action": "roll",
                "tier": "보통",
                "stat": "CHA",
                "targets": ["g"],
                "reason": "설득",
            },
        ],
    }
    coerced = coerce_judge_output(raw)
    assert coerced["action"] == "roll"
    assert "parts" not in coerced


def test_coerce_fills_missing_roll_reason():
    raw = {"action": "roll", "tier": "보통", "stat": "CHA", "targets": ["g"]}
    coerced = coerce_judge_output(raw)
    assert coerced["reason"] == "행동 판정"


def test_coerce_passes_through_well_formed_output():
    raw = {
        "action": "roll",
        "tier": "보통",
        "stat": "CHA",
        "targets": ["g"],
        "reason": "원래 이유",
    }
    assert coerce_judge_output(raw) == raw


def test_chain_with_combat_at_tail_preserved():
    """[Equip, Combat] is the canonical "단검을 뽑아 공격한다" shape — both parts
    must survive so the engine can equip then transition to combat. Promoting
    Combat alone (the old behavior) drops the equip step and the player's
    intent."""
    answer = json.dumps(
        {
            "action": "chain",
            "parts": [
                {"action": "equip", "item_id": "sword_01"},
                {"action": "combat", "targets": ["bandit_01"]},
            ],
        },
        ensure_ascii=False,
    )
    out = validate_judge_output(answer)
    assert isinstance(out, ChainAction)
    assert len(out.parts) == 2
    assert out.parts[-1].action == "combat"
    assert out.parts[-1].targets == ["bandit_01"]


def test_chain_with_combat_in_middle_promoted():
    """Combat in a non-tail slot is illegal — coerce promotes it so the attack
    isn't lost when classify mis-orders parts."""
    answer = json.dumps(
        {
            "action": "chain",
            "parts": [
                {"action": "combat", "targets": ["bandit_01"]},
                {"action": "equip", "item_id": "sword_01"},
            ],
        },
        ensure_ascii=False,
    )
    out = validate_judge_output(answer)
    assert isinstance(out, CombatAction)
    assert out.targets == ["bandit_01"]


def test_validate_absorbs_roll_missing_reason():
    answer = json.dumps(
        {"action": "roll", "tier": "보통", "stat": "CHA", "targets": ["g"]},
        ensure_ascii=False,
    )
    out = validate_judge_output(answer)
    assert isinstance(out, RollAction)
    assert out.reason == "행동 판정"


def test_validate_invalid_json_raises_validation_error():
    with pytest.raises(ValidationError):
        validate_judge_output("not json at all {{{")


def test_validate_preserves_well_formed_chain():
    answer = json.dumps(
        {
            "action": "chain",
            "parts": [
                {"action": "use", "item_id": "herb_01"},
                {"action": "equip", "item_id": "sword_01"},
            ],
        },
        ensure_ascii=False,
    )
    out = validate_judge_output(answer)
    assert isinstance(out, ChainAction)
    assert len(out.parts) == 2


def test_chain_recurses_into_parts():
    # Standalone use of a non-existent item is rejected by check_semantics —
    # the same id wrapped in ChainAction.parts must be rejected too. Without
    # recursion, a chain like ["사용 ghost", "지나간다"] would slip past
    # judge-side validation and surface as the engine's worse "InventoryInvalid".
    sur = {
        "location": {"id": "village_square"},
        "entities": [{"id": "village_square"}],
        "inventory": [],
    }
    chain = output_adapter.validate_json(
        json.dumps(
            {
                "action": "chain",
                "parts": [
                    {"action": "use", "item_id": "ghost"},
                    {"action": "pass"},
                ],
            },
            ensure_ascii=False,
        )
    )
    with pytest.raises(JudgeSemanticError):
        check_semantics(chain, sur)

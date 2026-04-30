import json

import pytest
from pydantic import ValidationError

from src.agents.dc_judge.schema import (
    CombatAction,
    PassAction,
    RollAction,
    output_adapter,
)
from src.agents.dc_judge.semantics import (
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


def test_roll_requires_reason():
    with pytest.raises(ValidationError):
        output_adapter.validate_json(
            json.dumps(
                {"action": "roll", "tier": "보통", "stat": "CHA", "targets": ["g"]},
                ensure_ascii=False,
            )
        )


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
                "state_tags": ["우호적(affinity 60)"],
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
                "state_tags": ["경계중(affinity -60)"],
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
        json.dumps(
            {"action": "pass", "targets": ["old_woman_01"]}, ensure_ascii=False
        )
    )
    check_semantics(p, sur)


def test_pass_rejects_corpse_id_when_not_present():
    sur = {
        "location": {"id": "plaza_01"},
        "entities": [{"id": "player_01", "name": "p", "type": "player"}],
        "corpses": [],
    }
    p = output_adapter.validate_json(
        json.dumps(
            {"action": "pass", "targets": ["ghost_id"]}, ensure_ascii=False
        )
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

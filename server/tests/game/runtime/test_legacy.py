from src.game.domain.entities import (
    Chapter,
    Character,
    Item,
    Location,
    Quest,
    QuestRewards,
    QuestTrigger,
    Race,
    Skill,
    WeaponEffect,
)
from src.game.domain.memory import DialoguePair, GMLogEntry, TurnLogEntry
from src.game.domain.state import CombatState
from src.game.flow.init import PlayerInput
from src.game.runtime import GameRuntimeState, runtime_to_legacy_state
from src.game.seed.graph_seed import build_seed_graph


def test_runtime_to_legacy_state_restores_entities_from_graph_edges():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={
            "human": Race(
                id="human",
                name="인간",
                description="",
                racial_skill_ids=["slash"],
            )
        },
        locations={
            "town": Location(id="town", name="마을"),
            "forest": Location(id="forest", name="숲"),
        },
        items={
            "starter_sword": Item(
                id="starter_sword",
                name="낡은 검",
                effects=WeaponEffect(type="weapon", weapon_dice="1d6"),
            ),
            "reward_sword": Item(id="reward_sword", name="보상 검"),
        },
        skills={
            "slash": Skill(
                id="slash",
                name="베기",
                type="attack",
                target="single",
                primary_stat="STR",
            )
        },
        npcs={
            "elder": Character(
                id="elder",
                name="장로",
                race_id="human",
                location_id="town",
                level=1,
            )
        },
        quests={
            "quest_01": Quest(
                id="quest_01",
                title="첫 의뢰",
                giver_id="elder",
                difficulty="easy",
                triggers=[
                    QuestTrigger(
                        id="reach_forest",
                        name="숲 도착",
                        type="location_enter",
                        target_id="forest",
                    )
                ],
                rewards=QuestRewards(items=["reward_sword"]),
                status="active",
            )
        },
        chapters={
            "chapter_01": Chapter(
                id="chapter_01",
                title="첫 장",
                quest_ids=["quest_01"],
            )
        },
        start={
            "start_location_id": "town",
            "active_subject_id": "elder",
            "active_quest_id": "quest_01",
        },
        template={
            "id": "player_01",
            "inventory_ids": ["starter_sword"],
            "equipment": {"weapon": "starter_sword"},
        },
        game_id="game-1",
        locale="ko",
    )
    progress = bundle.progress.model_copy(
        update={
            "pending_confirmation": {"id": "confirm-1", "kind": "attack_start"},
            "combat_state": CombatState(round=2, enemy_ids=["rat"]),
            "next_log_id": 9,
        }
    )
    runtime = GameRuntimeState(
        graph=bundle.graph,
        progress=progress,
        log_entries=[GMLogEntry(id=8, kind="gm", text="기록")],
        turn_log=[TurnLogEntry(turn=1, target="elder", summary="장로와 대화")],
        recent_dialogue=[
            DialoguePair(turn=1, player="묻는다", narrator="장로가 답합니다.")
        ],
    )

    state = runtime_to_legacy_state(runtime, profile_name="default")

    player = state.characters["player_01"]
    assert state.profile == "default"
    assert state.player_id == "player_01"
    assert state.active_subject_id == "elder"
    assert state.active_quest_id == "quest_01"
    assert state.combat_state.round == 2
    assert state.next_log_id == 9
    assert player.location_id == "town"
    assert player.inventory_ids == ["starter_sword"]
    assert player.equipment.weapon == "starter_sword"
    assert player.racial_skill_ids == ["slash"]
    assert state.races["human"].racial_skill_ids == ["slash"]
    assert state.quests["quest_01"].giver_id == "elder"
    assert state.quests["quest_01"].triggers[0].target_id == "forest"
    assert state.quests["quest_01"].rewards.items == ["reward_sword"]
    assert state.chapters["chapter_01"].quest_ids == ["quest_01"]
    assert state.log_entries[0].text == "기록"
    assert state.turn_log[0].summary == "장로와 대화"
    assert state.recent_dialogue[0].player == "묻는다"

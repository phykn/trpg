from src.db.repo import ScenarioRepo
from src.game.domain.content import RuntimeContent, runtime_content_from_records


async def load_runtime_content(
    scenario_repo: ScenarioRepo,
    profile_id: str,
) -> RuntimeContent:
    return runtime_content_from_records(
        races=await scenario_repo.load_seed_records(profile_id, "races"),
        locations=await scenario_repo.load_seed_records(profile_id, "locations"),
        items=await scenario_repo.load_seed_records(profile_id, "items"),
        skills=await scenario_repo.load_seed_records(profile_id, "skills"),
        support_effects=await scenario_repo.load_seed_records(
            profile_id, "support_effects"
        ),
        statuses=await scenario_repo.load_seed_records(profile_id, "statuses"),
        factions=await scenario_repo.load_seed_records(profile_id, "factions"),
        actions=await scenario_repo.load_seed_records(profile_id, "actions"),
        knowledge=await scenario_repo.load_seed_records(profile_id, "knowledge"),
        dialogue_styles=await scenario_repo.load_seed_records(
            profile_id, "dialogue_styles"
        ),
        mbti=await scenario_repo.load_seed_records(profile_id, "mbti"),
        characters=await scenario_repo.load_seed_records(profile_id, "characters"),
        quests=await scenario_repo.load_seed_records(profile_id, "quests"),
        chapters=await scenario_repo.load_seed_records(profile_id, "chapters"),
    )

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
        characters=await scenario_repo.load_seed_records(profile_id, "characters"),
        quests=await scenario_repo.load_seed_records(profile_id, "quests"),
        chapters=await scenario_repo.load_seed_records(profile_id, "chapters"),
    )

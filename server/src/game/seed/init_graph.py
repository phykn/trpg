import asyncio
import secrets
from datetime import datetime, timezone

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.errors import ProfileMalformed, ProfileNotFound, RaceNotFound
from src.game.seed.graph_seed import SeedGraphBundle, build_seed_graph
from src.game.seed.player import PlayerInput
from src.game.seed.validation import seed_violations


async def init_graph_game(
    profile_name: str,
    player: PlayerInput,
    graph_repo: GraphRepo,
    scenario_repo: ScenarioRepo,
    locale: str = "ko",
) -> SeedGraphBundle:
    if not await scenario_repo.profile_exists(profile_name):
        raise ProfileNotFound(profile_name)

    (
        races,
        locations,
        items,
        skills,
        support_effects,
        statuses,
        factions,
        action_categories,
        knowledge,
        dialogue_styles,
        mbti,
        npcs,
        quests,
        chapters,
        start,
        template,
    ) = await asyncio.gather(
        scenario_repo.load_seed_records(profile_name, "races"),
        scenario_repo.load_seed_records(profile_name, "locations"),
        scenario_repo.load_seed_records(profile_name, "items"),
        scenario_repo.load_seed_records(profile_name, "skills"),
        scenario_repo.load_seed_records(profile_name, "support_effects"),
        scenario_repo.load_seed_records(profile_name, "statuses"),
        scenario_repo.load_seed_records(profile_name, "factions"),
        scenario_repo.load_seed_records(profile_name, "action_categories"),
        scenario_repo.load_seed_records(profile_name, "knowledge"),
        scenario_repo.load_seed_records(profile_name, "dialogue_styles"),
        scenario_repo.load_seed_records(profile_name, "mbti"),
        scenario_repo.load_seed_records(profile_name, "characters"),
        scenario_repo.load_seed_records(profile_name, "quests"),
        scenario_repo.load_seed_records(profile_name, "chapters"),
        scenario_repo.read_start_json(profile_name),
        scenario_repo.read_player_template(profile_name),
    )

    violations = seed_violations(
        races=races,
        locations=locations,
        items=items,
        skills=skills,
        support_effects=support_effects,
        statuses=statuses,
        factions=factions,
        action_categories=action_categories,
        knowledge=knowledge,
        dialogue_styles=dialogue_styles,
        mbti=mbti,
        npcs=npcs,
        quests=quests,
        chapters=chapters,
        start=start,
    )
    if violations:
        raise ProfileMalformed(
            f"profile {profile_name!r} invariant violations:\n" + "\n".join(violations)
        )

    if player.race_id not in races:
        raise RaceNotFound(player.race_id)

    game_id = datetime.now(timezone.utc).strftime(
        "game_%y%m%d_%H%M%S_"
    ) + secrets.token_hex(3)
    bundle = build_seed_graph(
        profile_name=profile_name,
        player=player,
        races=races,
        locations=locations,
        items=items,
        skills=skills,
        support_effects=support_effects,
        statuses=statuses,
        factions=factions,
        action_categories=action_categories,
        knowledge=knowledge,
        dialogue_styles=dialogue_styles,
        mbti=mbti,
        npcs=npcs,
        quests=quests,
        chapters=chapters,
        start=start,
        template=template,
        game_id=game_id,
        locale=locale,
    )

    await graph_repo.save_graph(bundle.progress.game_id, bundle.graph)
    await graph_repo.save_progress(bundle.progress)
    return bundle

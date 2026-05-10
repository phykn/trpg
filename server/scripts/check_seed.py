"""CLI — run scenario invariants on a seed directory.

Usage (cwd: repo root):
    .venv/bin/python -m server.scripts.check_seed scenarios/redcliff

Exit code 0 if no violations; 1 otherwise. Each violation is one line, format
fed back to the LLM verbatim during story-team self-correction loops.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from src.db.local_fs import LocalFsScenarioRepo  # noqa: E402
from src.game.seed.validation import seed_violations  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: python -m server.scripts.check_seed <scenario_dir>", file=sys.stderr
        )
        return 2
    scenario_dir = Path(argv[1])
    if not scenario_dir.is_dir():
        print(f"not a directory: {scenario_dir}", file=sys.stderr)
        return 2

    repo = LocalFsScenarioRepo(str(scenario_dir.parent))
    violations = _load_violations(repo, scenario_dir.name)
    if not violations:
        print(f"OK: {scenario_dir} ({len(violations)} violations)")
        return 0
    print(f"FAIL: {scenario_dir} ({len(violations)} violations)")
    for v in violations:
        print(f"  {v}")
    return 1


def _load_violations(repo: LocalFsScenarioRepo, profile: str) -> list[str]:
    async def _load() -> list[str]:
        try:
            start = await repo.read_start_json(profile)
        except FileNotFoundError:
            start = {}
        return seed_violations(
            races=await repo.load_seed_records(profile, "races"),
            locations=await repo.load_seed_records(profile, "locations"),
            items=await repo.load_seed_records(profile, "items"),
            skills=await repo.load_seed_records(profile, "skills"),
            npcs=await repo.load_seed_records(profile, "characters"),
            quests=await repo.load_seed_records(profile, "quests"),
            chapters=await repo.load_seed_records(profile, "chapters"),
            start=start,
        )

    return asyncio.run(_load())


if __name__ == "__main__":
    sys.exit(main(sys.argv))

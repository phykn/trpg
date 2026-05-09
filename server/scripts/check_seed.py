"""CLI — run scenario invariants on a seed directory.

Usage (cwd: repo root):
    .venv/bin/python -m server.scripts.check_seed scenarios/redcliff

Exit code 0 if no violations; 1 otherwise. Each violation is one line, format
fed back to the LLM verbatim during story-team self-correction loops.
"""

import sys
from pathlib import Path

from src.game.engines.invariants import Scenario, check_scenario


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

    violations = check_scenario(Scenario.from_dir(scenario_dir))
    if not violations:
        print(f"OK: {scenario_dir} ({len(violations)} violations)")
        return 0
    print(f"FAIL: {scenario_dir} ({len(violations)} violations)")
    for v in violations:
        print(f"  {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

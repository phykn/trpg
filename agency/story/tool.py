"""Story team CLI — deterministic helpers for the SKILL-driven scenario build.

Each subcommand reads input, runs a check or transform, and exits with:
  0 + "OK" on stdout            -- pass
  1 + human-readable error      -- validation failed
  2 + usage on stderr           -- bad invocation

Subcommands are added in subsequent tasks. This file currently has only the
argparse skeleton + bootstrap.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT))

# sys.path must be set first; decompose.py transitively imports src.llm
from agency.story.harness.decompose import (  # noqa: E402
    DecomSetup,
    DecomCast,
    DecomArc,
    _check_setup,
    _check_cast,
    _check_arc,
)
from agency.story.harness._common import EntityWriterError  # noqa: E402
from agency.story.harness.scenario import copy_fixed_catalogs, fill_equipment  # noqa: E402
from src.db.scenario.local_fs import LocalFsScenarioRepo  # noqa: E402
from src.env import load_server_env  # noqa: E402
from src.game.seed.validation import seed_violations  # noqa: E402
from agency.story.harness.runner import (  # noqa: E402
    SPECS,
    _check_entity_invariants,
    _check_id,
    _collect_refs,
)

# env loading mirrors server startup so SUPABASE_* / LLM_ROUTE_* provider keys
# resolve here. Subcommands that don't need env (decompose-*, check-entity,
# equip-fill, sweep) still pay this cheap one-time cost.
load_server_env(ROOT / "server")
load_dotenv(ROOT / "server" / ".env.local")
load_dotenv(ROOT / "server" / ".env.google")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agency.story.tool",
        description="Deterministic helpers for the story SKILL.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)  # noqa: F841 — populated by subcommand tasks
    # decompose-setup
    sp_setup = sub.add_parser(
        "decompose-setup",
        help="DecomSetup JSON 검증 (Phase A)",
    )
    sp_setup.add_argument("setup_json", help="path to setup.json")
    sp_setup.set_defaults(func=_cmd_decompose_setup)
    # decompose-cast
    sp_cast = sub.add_parser(
        "decompose-cast",
        help="DecomCast JSON 검증 (Phase B). setup JSON 컨텍스트 필요.",
    )
    sp_cast.add_argument("setup_json", help="path to setup.json")
    sp_cast.add_argument("cast_json", help="path to cast.json")
    sp_cast.set_defaults(func=_cmd_decompose_cast)
    # decompose-arc
    sp_arc = sub.add_parser(
        "decompose-arc",
        help="DecomArc JSON 검증 (Phase C). setup + cast 컨텍스트 필요.",
    )
    sp_arc.add_argument("setup_json", help="path to setup.json")
    sp_arc.add_argument("cast_json", help="path to cast.json")
    sp_arc.add_argument("arc_json", help="path to arc.json")
    sp_arc.set_defaults(func=_cmd_decompose_arc)
    # check-entity
    sp_chk = sub.add_parser(
        "check-entity",
        help="한 엔티티 cross-ref + invariant 검사",
    )
    sp_chk.add_argument("kind", choices=sorted(SPECS), help="entity kind")
    sp_chk.add_argument(
        "scenario_dir", help="scenario directory (already partially populated)"
    )
    sp_chk.add_argument("entity_json", help="path to the entity JSON to check")
    sp_chk.add_argument(
        "--decomp",
        default=None,
        help="decompose dir (setup/cast/arc.json). 있으면 그 명단도 valid ID 풀에 합침",
    )
    sp_chk.add_argument(
        "--skeleton",
        action="store_true",
        help="풀-의존 검사 건너뜀 (character의 inventory/skill 풀 검증을 sweep까지 미룸)",
    )
    sp_chk.set_defaults(func=_cmd_check_entity)
    # equip-fill
    sp_eq = sub.add_parser(
        "equip-fill",
        help="NPC character.equipment를 서버 규칙에 맞게 비움",
    )
    sp_eq.add_argument("scenario_dir", help="scenario directory")
    sp_eq.set_defaults(func=_cmd_equip_fill)
    # catalog-fill
    sp_cat = sub.add_parser(
        "catalog-fill",
        help="story 고정 support catalog(actions/effects/mbti/slots)를 복사",
    )
    sp_cat.add_argument("scenario_dir", help="scenario directory")
    sp_cat.set_defaults(func=_cmd_catalog_fill)
    # sweep
    sp_sw = sub.add_parser(
        "sweep",
        help="최종 시나리오 graph seed record 검사",
    )
    sp_sw.add_argument("scenario_dir", help="scenario directory")
    sp_sw.set_defaults(func=_cmd_sweep)
    return parser


def _fail(cmd: str, e: Exception) -> int:
    """Print a failure line and return exit code 1.

    EntityWriterError / FileNotFoundError carry their own self-explanatory
    messages — passed through as-is. Other exceptions get the class name
    prepended so 'ValidationError: ...' / 'JSONDecodeError: ...' is visible.
    """
    if isinstance(e, (FileNotFoundError, EntityWriterError)):
        prefix = ""
    else:
        prefix = f"{type(e).__name__}: "
    print(f"{cmd} failed: {prefix}{e}", file=sys.stderr)
    return 1


def _merge_decomp_pool(refs: dict, decomp_dir: Path) -> None:
    """decompose 디렉토리의 setup/cast/arc JSON에서 명단을 읽어 valid ID 풀에 합침.

    Each phase JSON contributes its own roster; existence is optional (a
    skill check before cast.json is written should still work).
    """
    setup_path = decomp_dir / "setup.json"
    cast_path = decomp_dir / "cast.json"
    arc_path = decomp_dir / "arc.json"
    if setup_path.is_file():
        s = DecomSetup.model_validate_json(setup_path.read_text(encoding="utf-8"))
        refs.setdefault("race", set()).update(r.id for r in s.races)
        refs.setdefault("skill", set()).update(sk.id for sk in s.skills)
        refs.setdefault("location", set()).update(loc.id for loc in s.locations)
    if cast_path.is_file():
        c = DecomCast.model_validate_json(cast_path.read_text(encoding="utf-8"))
        refs.setdefault("character", set()).update(ch.id for ch in c.characters)
        refs.setdefault("item", set()).update(it.id for it in c.items)
    if arc_path.is_file():
        a = DecomArc.model_validate_json(arc_path.read_text(encoding="utf-8"))
        refs.setdefault("quest", set()).update(q.id for q in a.quests)
        refs.setdefault("chapter", set()).update(ch.id for ch in a.chapters)


def _cmd_check_entity(args: argparse.Namespace) -> int:
    spec = SPECS[args.kind]
    sd = Path(args.scenario_dir)
    if not sd.is_dir():
        print(
            f"check-entity failed: scenario_dir not a directory: {sd}", file=sys.stderr
        )
        return 1
    try:
        entity = json.loads(Path(args.entity_json).read_text(encoding="utf-8"))
        refs = _collect_refs(sd, spec)
        if args.decomp:
            _merge_decomp_pool(refs, Path(args.decomp))
        existing_ids = refs[spec.kind]
        # remove the entity-being-checked id from `existing_ids` so it doesn't
        # trip the collision check against its own future on-disk file.
        existing_ids.discard(entity.get("id"))
        _check_id(entity, existing_ids, force_id=None)
        spec.check_refs(entity, refs)
        _check_entity_invariants(entity, sd, kind=args.kind, skeleton=args.skeleton)
    except Exception as e:
        return _fail("check-entity", e)
    print("OK")
    return 0


def _cmd_decompose_arc(args: argparse.Namespace) -> int:
    try:
        setup = DecomSetup.model_validate_json(
            Path(args.setup_json).read_text(encoding="utf-8")
        )
        cast = DecomCast.model_validate_json(
            Path(args.cast_json).read_text(encoding="utf-8")
        )
        arc = DecomArc.model_validate_json(
            Path(args.arc_json).read_text(encoding="utf-8")
        )
        _check_arc(setup, cast, arc)
    except Exception as e:
        return _fail("decompose-arc", e)
    print("OK")
    return 0


def _cmd_decompose_cast(args: argparse.Namespace) -> int:
    try:
        setup = DecomSetup.model_validate_json(
            Path(args.setup_json).read_text(encoding="utf-8")
        )
        cast = DecomCast.model_validate_json(
            Path(args.cast_json).read_text(encoding="utf-8")
        )
        _check_cast(setup, cast)
    except Exception as e:
        return _fail("decompose-cast", e)
    print("OK")
    return 0


def _cmd_decompose_setup(args: argparse.Namespace) -> int:
    try:
        raw = Path(args.setup_json).read_text(encoding="utf-8")
        setup = DecomSetup.model_validate_json(raw)
        _check_setup(setup)
    except Exception as e:
        return _fail("decompose-setup", e)
    print("OK")
    return 0


def _cmd_equip_fill(args: argparse.Namespace) -> int:
    sd = Path(args.scenario_dir)
    if not sd.is_dir():
        print(f"equip-fill failed: scenario_dir not a directory: {sd}", file=sys.stderr)
        return 1
    try:
        fill_equipment(sd)
    except Exception as e:
        return _fail("equip-fill", e)
    print("OK")
    return 0


def _cmd_catalog_fill(args: argparse.Namespace) -> int:
    sd = Path(args.scenario_dir)
    if not sd.is_dir():
        print(
            f"catalog-fill failed: scenario_dir not a directory: {sd}",
            file=sys.stderr,
        )
        return 1
    try:
        copy_fixed_catalogs(sd, ROOT / "agency" / "story" / "catalogs")
    except Exception as e:
        return _fail("catalog-fill", e)
    print("OK")
    return 0


async def _load_scenario_async(profile: str, profile_root: Path) -> dict:
    repo = LocalFsScenarioRepo(str(profile_root))
    return {
        "races": await repo.load_seed_records(profile, "races"),
        "locations": await repo.load_seed_records(profile, "locations"),
        "items": await repo.load_seed_records(profile, "items"),
        "skills": await repo.load_seed_records(profile, "skills"),
        "effects": await repo.load_seed_records(profile, "effects"),
        "statuses": await repo.load_seed_records(profile, "statuses"),
        "slots": await repo.load_seed_records(profile, "slots"),
        "factions": await repo.load_seed_records(profile, "factions"),
        "actions": await repo.load_seed_records(profile, "actions"),
        "knowledge": await repo.load_seed_records(profile, "knowledge"),
        "dialogue_styles": await repo.load_seed_records(profile, "dialogue_styles"),
        "mbti": await repo.load_seed_records(profile, "mbti"),
        "npcs": await repo.load_seed_records(profile, "characters"),
        "quests": await repo.load_seed_records(profile, "quests"),
        "chapters": await repo.load_seed_records(profile, "chapters"),
        "start": await _read_optional_start(repo, profile),
        "player": await _read_optional_player(repo, profile),
    }


def _cmd_sweep(args: argparse.Namespace) -> int:
    sd = Path(args.scenario_dir).resolve()
    if not sd.is_dir():
        print(f"sweep failed: scenario_dir not a directory: {sd}", file=sys.stderr)
        return 1
    try:
        scenario = asyncio.run(_load_scenario_async(sd.name, sd.parent))
        violations = seed_violations(**scenario)
    except Exception as e:
        return _fail("sweep", e)
    if violations:
        print("sweep failed:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("OK")
    return 0


async def _read_optional_start(repo: LocalFsScenarioRepo, profile: str) -> dict:
    try:
        return await repo.read_start_json(profile)
    except FileNotFoundError:
        return {}


async def _read_optional_player(repo: LocalFsScenarioRepo, profile: str) -> dict | None:
    try:
        return await repo.read_player(profile)
    except FileNotFoundError:
        return None


def _main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def main() -> None:
    sys.exit(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()

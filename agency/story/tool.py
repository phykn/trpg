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
import mimetypes
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT))

# sys.path must be set first; decompose.py transitively imports src.llm
from agency.story.harness.decompose import (
    DecomSetup,
    DecomCast,
    DecomArc,
    _check_setup,
    _check_cast,
    _check_arc,
)  # noqa: E402
from agency.story.harness._common import EntityWriterError  # noqa: E402
from agency.story.harness.scenario import fill_equipment  # noqa: E402
from src.game.engines.invariants import Scenario, check_scenario  # noqa: E402
from src.game.domain.entities import (  # noqa: E402
    Chapter,
    Character,
    Item,
    Location,
    Quest,
    Race,
    Skill,
)
from src.db.local_fs import LocalFsScenarioRepo  # noqa: E402
from agency.story.harness.runner import (  # noqa: E402
    SPECS,
    _check_entity_invariants,
    _check_id,
    _collect_refs,
)
from src.db._supabase_http import _Storage  # noqa: E402

# env loading mirrors run_qa.py / run_story.py so SUPABASE_* / BASE_URL
# / LLM_ROUTE_* resolve here. Subcommands that don't need env (decompose-*,
# check-entity, equip-fill, sweep) still pay this cheap one-time cost.
_APP_ENV = os.environ.get("APP_ENV", "dev")
load_dotenv(ROOT / "server" / f".env.{_APP_ENV}")
load_dotenv(ROOT / "server" / ".env.llama_cpp")
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
        help="character.equipment 슬롯을 inventory 아이템 effect 보고 자동 배치",
    )
    sp_eq.add_argument("scenario_dir", help="scenario directory")
    sp_eq.set_defaults(func=_cmd_equip_fill)
    # sweep
    sp_sw = sub.add_parser(
        "sweep",
        help="최종 시나리오 invariant sweep (engines.invariants.check_scenario)",
    )
    sp_sw.add_argument("scenario_dir", help="scenario directory")
    sp_sw.set_defaults(func=_cmd_sweep)
    # upload
    sp_up = sub.add_parser(
        "upload",
        help="prod Supabase Storage bucket에 시나리오 디렉토리 업로드",
    )
    sp_up.add_argument("scenario_dir", help="local scenario directory")
    sp_up.set_defaults(func=_cmd_upload)
    # download
    sp_dl = sub.add_parser(
        "download",
        help="prod Supabase Storage bucket에서 시나리오 디렉토리 다운로드",
    )
    sp_dl.add_argument("profile", help="scenario profile (bucket key prefix)")
    sp_dl.add_argument(
        "--out",
        dest="out",
        default=None,
        help="저장 경로 (기본 scenarios/<profile>). 이미 존재하면 실패",
    )
    sp_dl.set_defaults(func=_cmd_download)
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


def _cmd_check_entity(args: argparse.Namespace) -> int:
    spec = SPECS[args.kind]
    sd = Path(args.scenario_dir)
    if not sd.is_dir():
        print(
            f"check-entity failed: scenario_dir not a directory: {sd}", file=sys.stderr
        )
        return 1
    try:
        entity = spec.model.model_validate_json(
            Path(args.entity_json).read_text(encoding="utf-8")
        )
        refs = _collect_refs(sd, spec)
        if args.decomp:
            _merge_decomp_pool(refs, Path(args.decomp))
        existing_ids = refs[spec.kind]
        # remove the entity-being-checked id from `existing_ids` so it doesn't
        # trip the collision check against its own future on-disk file.
        existing_ids.discard(entity.id)
        _check_id(entity, existing_ids, force_id=None)
        spec.check_refs(entity, refs)
        _check_entity_invariants(entity, sd, skeleton=args.skeleton)
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


async def _load_scenario_async(profile: str, profile_root: Path) -> Scenario:
    repo = LocalFsScenarioRepo(str(profile_root))
    return Scenario(
        races=await repo.load_seed_entities(profile, "races", Race),
        locations=await repo.load_seed_entities(profile, "locations", Location),
        items=await repo.load_seed_entities(profile, "items", Item),
        skills=await repo.load_seed_entities(profile, "skills", Skill),
        characters=await repo.load_seed_entities(profile, "characters", Character),
        quests=await repo.load_seed_entities(profile, "quests", Quest),
        chapters=await repo.load_seed_entities(profile, "chapters", Chapter),
        start=await repo.read_start_json(profile),
        player_template=await repo.read_player_template(profile),
    )


def _cmd_sweep(args: argparse.Namespace) -> int:
    sd = Path(args.scenario_dir).resolve()
    if not sd.is_dir():
        print(f"sweep failed: scenario_dir not a directory: {sd}", file=sys.stderr)
        return 1
    try:
        scenario = asyncio.run(_load_scenario_async(sd.name, sd.parent))
        violations = check_scenario(scenario)
    except Exception as e:
        return _fail("sweep", e)
    if violations:
        print("sweep failed:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("OK")
    return 0


def _content_type(path: Path) -> str:
    guess, _ = mimetypes.guess_type(path.name)
    if guess:
        return guess
    if path.suffix == ".md":
        return "text/markdown"
    return "application/octet-stream"


async def _upload_async(local: Path) -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    bucket = os.environ["SUPABASE_SCENARIO_BUCKET"]
    fs = _Storage(url, key, bucket)
    profile = local.name
    print(f"uploading {local} -> {bucket}/{profile}/")
    files = sorted(p for p in local.rglob("*") if p.is_file())
    if not files:
        print("  (no files)")
        await fs.aclose()
        return
    for f in files:
        rel = f.relative_to(local).as_posix()
        bucket_key = f"{profile}/{rel}"
        blob = f.read_bytes()
        await fs.put_bytes(bucket_key, blob, content_type=_content_type(f))
        print(f"  {bucket_key}  ({len(blob)}B)")
    await fs.aclose()
    print(f"done — {len(files)} files uploaded")


def _cmd_upload(args: argparse.Namespace) -> int:
    local = Path(args.scenario_dir).resolve()
    if not local.is_dir():
        print(f"upload failed: not a directory: {local}", file=sys.stderr)
        return 1
    try:
        asyncio.run(_upload_async(local))
    except KeyError as e:
        print(f"upload failed: missing env var: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        return _fail("upload", e)
    print("OK")
    return 0


async def _walk_storage(fs: _Storage, prefix: str) -> list[str]:
    """Recursively list every object key under prefix/ (one prefix per level)."""
    out: list[str] = []
    files = await fs.list_prefix(prefix)
    out.extend(f"{prefix}/{name}" for name in files)
    for sub in await fs.list_dirs(prefix):
        out.extend(await _walk_storage(fs, f"{prefix}/{sub}"))
    return out


async def _download_async(profile: str, dest: Path) -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    bucket = os.environ["SUPABASE_SCENARIO_BUCKET"]
    fs = _Storage(url, key, bucket)
    print(f"downloading {bucket}/{profile}/ -> {dest}")
    try:
        keys = await _walk_storage(fs, profile)
        if not keys:
            raise FileNotFoundError(f"profile not found in bucket: {profile}")
        for k in keys:
            rel = k[len(profile) + 1 :]
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            blob = await fs.get_bytes(k)
            out.write_bytes(blob)
            print(f"  {rel}  ({len(blob)}B)")
        print(f"done — {len(keys)} files downloaded")
    finally:
        await fs.aclose()


def _cmd_download(args: argparse.Namespace) -> int:
    profile = args.profile
    dest = (
        Path(args.out).resolve()
        if args.out
        else (ROOT / "scenarios" / profile).resolve()
    )
    if dest.exists():
        print(
            f"download failed: dest already exists (remove first to avoid mixing stale files): {dest}",
            file=sys.stderr,
        )
        return 1
    try:
        asyncio.run(_download_async(profile, dest))
    except KeyError as e:
        print(f"download failed: missing env var: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        return _fail("download", e)
    print("OK")
    return 0


def _main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def main() -> None:
    sys.exit(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()

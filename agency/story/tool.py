"""Story team CLI — deterministic helpers for the SKILL-driven scenario build.

Each subcommand reads input, runs a check or transform, and exits with:
  0 + "OK" on stdout            -- pass
  1 + human-readable error      -- validation failed
  2 + usage on stderr           -- bad invocation

Subcommands are added in subsequent tasks. This file currently has only the
argparse skeleton + bootstrap.
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT))

# sys.path must be set first; decompose.py transitively imports src.llm
from agency.story.harness.decompose import DecomSetup, DecomCast, DecomArc, _check_setup, _check_cast, _check_arc  # noqa: E402
from agency.story.harness._common import EntityWriterError  # noqa: E402
from agency.story.harness.runner import (  # noqa: E402
    SPECS,
    _check_entity_invariants,
    _check_id,
    _collect_refs,
)

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
    sp_chk.add_argument("scenario_dir", help="scenario directory (already partially populated)")
    sp_chk.add_argument("entity_json", help="path to the entity JSON to check")
    sp_chk.set_defaults(func=_cmd_check_entity)
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


def _cmd_check_entity(args: argparse.Namespace) -> int:
    spec = SPECS[args.kind]
    sd = Path(args.scenario_dir)
    if not sd.is_dir():
        print(f"check-entity failed: scenario_dir not a directory: {sd}", file=sys.stderr)
        return 1
    try:
        entity = spec.model.model_validate_json(
            Path(args.entity_json).read_text(encoding="utf-8")
        )
        refs = _collect_refs(sd, spec)
        existing_ids = refs[spec.kind]
        # remove the entity-being-checked id from `existing_ids` so it doesn't
        # trip the collision check against its own future on-disk file.
        existing_ids.discard(entity.id)
        _check_id(entity, existing_ids, force_id=None)
        spec.check_refs(entity, refs)
        _check_entity_invariants(entity, sd, skeleton=False)
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


def _main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def main() -> None:
    sys.exit(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()

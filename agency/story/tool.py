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

from agency.story.harness.decompose import DecomSetup, _check_setup  # noqa: E402
from agency.story.harness._common import EntityWriterError  # noqa: E402

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
    return parser


def _cmd_decompose_setup(args: argparse.Namespace) -> int:
    try:
        raw = Path(args.setup_json).read_text(encoding="utf-8")
        setup = DecomSetup.model_validate_json(raw)
        _check_setup(setup)
    except (FileNotFoundError, EntityWriterError) as e:
        print(f"decompose-setup failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # ValidationError, JSONDecodeError 등
        print(f"decompose-setup failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
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

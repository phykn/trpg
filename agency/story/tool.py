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
    # subcommands registered in later tasks
    return parser


def _main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def main() -> None:
    sys.exit(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()

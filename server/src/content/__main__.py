"""Check story folders from the command line: python -m src.content validate ../scenarios/<name>."""

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from .load import load_story
from .validate import validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate"])
    parser.add_argument("folders", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for folder in args.folders:
        try:
            errors = validate(load_story(folder).story)
        except (OSError, ValidationError) as exc:
            errors = [str(exc)]
        failed |= bool(errors)
        print(f"{folder}: {'ok' if not errors else f'{len(errors)} error(s)'}")
        for error in errors:
            print(f"  - {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

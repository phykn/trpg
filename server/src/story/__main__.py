"""Validate stories from the command line: python -m src.story ../scenarios [more roots or story.yaml files]."""

import argparse
import sys
from pathlib import Path

from .load import StoryError, story_files
from .validate import load


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    failed = False
    for root in parser.parse_args().paths:
        for path in [root] if root.is_file() else story_files(root):
            try:
                u = load(path)
                print(f"{path}: ok ({u.id})")
            except (OSError, StoryError) as e:
                failed = True
                print(f"{path}: {e}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

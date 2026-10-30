import argparse
import sys
from pathlib import Path

from .load import StoryError, story_files
from .validate import load, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate story.yaml files or roots of them.")
    parser.add_argument("paths", nargs="+", type=Path)
    failed = False
    for root in parser.parse_args().paths:
        # A story folder, its story.yaml, or a folder of story folders.
        paths = [root] if root.is_file() else [root / "story.yaml"] if (root / "story.yaml").is_file() \
            else story_files(root) if root.is_dir() else []
        if not paths:
            failed = True
            print(f"{root}: no story.yaml")
        for path in paths:
            try:
                u = load(path)
                print(f"{path}: ok ({u.id})")
                for w in warnings(u):
                    print(f"{path}: warning: {w}")
            except (OSError, StoryError) as e:
                failed = True
                print(f"{path}: {e}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

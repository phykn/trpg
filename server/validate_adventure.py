"""Validate the harbor story content."""

from pathlib import Path

from src.content import load_story

if __name__ == "__main__":
    pack = load_story(
        Path(__file__).resolve().parents[1] / "scenarios/harbor/adventure.json"
    )
    print(
        f"{pack.id} v{pack.version}: {len(pack.graph.nodes)} nodes, {len(pack.choices)} choices, {len(pack.endings)} endings OK"
    )

"""Read story.yaml in the strict YAML subset of story.md 2.1."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml
from yaml.events import AliasEvent, CollectionStartEvent, ScalarEvent
from yaml.nodes import MappingNode, ScalarNode, SequenceNode


class StoryError(ValueError):
    """A story that breaks the format or validation (messages in English)."""


INT = re.compile(r"[-+]?\d+")
DEFAULT_TAGS = {"tag:yaml.org,2002:str", "tag:yaml.org,2002:seq", "tag:yaml.org,2002:map",
                "tag:yaml.org,2002:int", "tag:yaml.org,2002:bool", "tag:yaml.org,2002:null",
                "tag:yaml.org,2002:float", "tag:yaml.org,2002:timestamp"}


def parse(text: str, where: str = "story") -> object:
    """Parse YAML without anchors, aliases or tags; plain scalars read as YAML 1.2 core."""
    try:
        for ev in yaml.parse(text, Loader=yaml.SafeLoader):
            if isinstance(ev, AliasEvent):
                raise StoryError(f"{where}: aliases are not allowed")
            if isinstance(ev, (ScalarEvent, CollectionStartEvent)):
                if ev.anchor:
                    raise StoryError(f"{where}: anchors are not allowed")
                if ev.tag and not (isinstance(ev, ScalarEvent) and ev.tag == "!"):
                    raise StoryError(f"{where}: tags are not allowed ({ev.tag})")
        node = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as e:
        raise StoryError(f"{where}: {e}") from None
    return _value(node, where) if node is not None else None


def _value(node, where: str):
    if isinstance(node, ScalarNode):
        v = node.value
        if node.style:  # quoted or block scalars stay strings
            return v
        if INT.fullmatch(v):
            return int(v)
        if v in ("true", "false"):
            return v == "true"
        if v in ("null", "~", ""):
            return None
        return v
    if isinstance(node, SequenceNode):
        return [_value(n, where) for n in node.value]
    if isinstance(node, MappingNode):
        out: dict = {}
        for k, v in node.value:
            key = _value(k, where)
            if not isinstance(key, (str, int)):
                raise StoryError(f"{where}: map keys must be scalars")
            key = str(key)
            if key in out:
                raise StoryError(f"{where}: duplicate key {key}")
            out[key] = _value(v, where)
        return out
    raise StoryError(f"{where}: unsupported node")


def read(path: Path) -> tuple[dict, str]:
    """The parsed story file and the digest of its bytes."""
    data = path.read_bytes()
    raw = parse(data.decode("utf-8"), path.parent.name)
    if not isinstance(raw, dict):
        raise StoryError(f"{path.parent.name}: story.yaml must be a map")
    return raw, "sha256:" + hashlib.sha256(data).hexdigest()


def story_files(root: Path) -> list[Path]:
    return sorted(p / "story.yaml" for p in root.iterdir() if (p / "story.yaml").is_file())

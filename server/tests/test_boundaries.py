"""Layering and story-independence of the engine code."""

import ast
import json
import re
from pathlib import Path

from conftest import REPO, SERVER

SRC = SERVER / "src"
PURE = ["rules", "world", "scene"]
IO_MODULES = {"httpx", "asyncio", "os", "pathlib", "src.models", "src.store", "src.service", "src.api"}
TOKEN = re.compile(r"[a-z_][a-z0-9_]*")


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_pure_layers_do_no_io():
    for folder in PURE:
        for path in (SRC / folder).glob("*.py"):
            found = {m for m in imports(path) if any(m == b or m.startswith(b + ".") for b in IO_MODULES)}
            assert not found, f"{path.relative_to(SERVER)} imports {found}"
            assert "open(" not in path.read_text(encoding="utf-8"), path


def test_only_interpret_and_narrate_call_models():
    callers = {
        p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if any(m.startswith("src.models") for m in imports(p)) and not p.is_relative_to(SRC / "models")
    }
    assert callers <= {"interpret.py", "narrate.py", "service.py", "api.py"}


def story_words() -> tuple[set[str], set[str]]:
    ids, names = set(), set()
    for path in (REPO / "scenarios").glob("*/scenario.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for table in ("places", "characters", "items", "knowledge", "skills", "obstacles", "quests"):
            for key, value in data.get(table, {}).items():
                ids.add(key)
                names.add(value.get("name") or value.get("title") or "")
        for listed in ("topics", "chapters", "endings", "actions", "traits"):
            for value in data.get(listed, []):
                ids.add(value["id"])
                names.add(value.get("title") or value.get("name") or "")
        ids.add(data["id"])
    return ids, {n for n in names if len(n) >= 2}


def test_engine_has_no_story_text():
    ids, names = story_words()
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                leaked = (set(TOKEN.findall(node.value)) & ids) | {n for n in names if n in node.value}
                assert not leaked, f"{path.relative_to(SERVER)} mentions story words {leaked}"

import importlib.util
from pathlib import Path


def _load_smoke_move_module():
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "smoke_move.py"
    spec = importlib.util.spec_from_file_location("smoke_move", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_strip_fence_removes_dangling_backtick_after_json():
    smoke_move = _load_smoke_move_module()

    assert smoke_move._strip_fence('{"actions":[{"verb":"attack"}]}`') == (
        '{"actions":[{"verb":"attack"}]}'
    )

import copy
import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))

from src.onto.universe import initial
from src.story.compile import build
from src.story.load import read

REPO = SERVER.parent
SKELETON = REPO / "scenarios" / "skeleton" / "story.yaml"
_RAW, _DIGEST = read(SKELETON)


def skeleton_raw() -> dict:
    return copy.deepcopy(_RAW)


@pytest.fixture(scope="session")
def u():
    return build(skeleton_raw(), _DIGEST)


@pytest.fixture(scope="session")
def creation(u):
    return u.witnesses["creation"]


@pytest.fixture
def s0(u, creation):
    return initial(u, creation)

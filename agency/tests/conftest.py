"""sys.path bootstrap so `agency.*` and `src.*` resolve regardless of pytest cwd."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))

"""Generate wire JSON Schema bundle for client codegen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.wire.export import dump_schemas  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "client" / "types" / "wire.schema.json"
dump_schemas(OUT)
print(f"wrote {OUT}")

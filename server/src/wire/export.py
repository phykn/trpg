import json
import re
from pathlib import Path

from .models.combat import CombatEndPayload, CombatStartPayload, CombatTurnPayload
from .models.done import DonePayload
from .models.error import ErrorPayload
from .models.hero import HeroPayload
from .models.judge import JudgePayload
from .models.log_entry import LogEntryPayload
from .models.narrative_delta import NarrativeDeltaPayload
from .models.pending_check import PendingCheckPayload
from .models.place import PlacePayload
from .models.quest import QuestPayload
from .models.subject import SubjectPayload
from .models.suggestions import SuggestionsPayload

_MODELS = [
    ErrorPayload,
    PendingCheckPayload,
    HeroPayload,
    SubjectPayload,
    QuestPayload,
    PlacePayload,
    JudgePayload,
    LogEntryPayload,
    NarrativeDeltaPayload,
    SuggestionsPayload,
    DonePayload,
    CombatStartPayload,
    CombatTurnPayload,
    CombatEndPayload,
]


def _flatten(schema: dict, definitions: dict) -> dict:
    """Hoist Pydantic-v2 $defs into the bundle definitions and rewrite $refs.

    Pydantic v2 places nested-model schemas in a per-model $defs block and
    emits $ref: "#/$defs/Name". The draft-07 bundle uses definitions at the
    root, so we must lift those entries up and rewrite the refs accordingly.
    Sub-schemas hoisted from $defs may themselves contain $ref: "#/$defs/..."
    (e.g. Equipment referencing EquipItem), so the ref rewrite must cover
    the whole bundle dump, not just the top-level schema body.
    """
    nested = schema.pop("$defs", {})
    for name, sub in nested.items():
        definitions[name] = sub
    # rewrite refs in the main schema body
    raw = json.dumps(schema)
    fixed = re.sub(r'"#/\$defs/', '"#/definitions/', raw)
    schema = json.loads(fixed)
    # rewrite refs inside any sub-schemas that were just hoisted
    for name, sub in nested.items():
        raw_sub = json.dumps(sub)
        fixed_sub = re.sub(r'"#/\$defs/', '"#/definitions/', raw_sub)
        definitions[name] = json.loads(fixed_sub)
    return schema


def dump_schemas(out_path: Path) -> None:
    definitions: dict = {}
    for m in _MODELS:
        definitions[m.__name__] = _flatten(m.model_json_schema(), definitions)
    bundle = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": definitions,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

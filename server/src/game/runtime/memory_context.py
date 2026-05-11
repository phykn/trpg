from .state import GameRuntimeState


def important_history_payload(
    runtime: GameRuntimeState,
    *,
    limit: int = 20,
) -> list[dict]:
    ranked = sorted(
        enumerate(runtime.turn_log),
        key=lambda item: (item[1].importance, item[1].turn, item[0]),
        reverse=True,
    )
    selected = sorted(ranked[:limit], key=lambda item: (item[1].turn, item[0]))
    return [entry.model_dump(mode="json") for _, entry in selected]


def recent_dialogue_payload(
    runtime: GameRuntimeState,
    *,
    limit: int = 5,
) -> list[dict]:
    return [
        entry.model_dump(mode="json") for entry in runtime.recent_dialogue[-limit:]
    ]

"""Supabase adapters for SaveRepo / ScenarioRepo — Phase 2 stub.

Phase 1 only needs these classes to exist so `factory.py` can dispatch on
`APP_ENV=release`. Construction itself raises so `APP_ENV=release` fails at
startup until Phase 2 fills in the implementations.

Phase 2 will implement:
- `SupabaseSaveRepo`: rows in `entities(game_id, kind, id, data jsonb)`,
  `games(game_id, meta jsonb)`, append-only log/history/dialogue tables.
- `SupabaseStorageScenarioRepo`: read profile dirs from a Storage bucket
  (e.g. `scenarios/<profile>/world.md`, `scenarios/<profile>/items/*.json`).
"""


class SupabaseSaveRepo:
    def __init__(self, *, url: str, service_key: str) -> None:
        raise NotImplementedError(
            "SupabaseSaveRepo: implement in Phase 2 "
            "(set APP_ENV=dev to use the local-fs adapter for now)"
        )


class SupabaseStorageScenarioRepo:
    def __init__(self, *, url: str, service_key: str, bucket: str) -> None:
        raise NotImplementedError(
            "SupabaseStorageScenarioRepo: implement in Phase 2 "
            "(set APP_ENV=dev to use the local-fs adapter for now)"
        )

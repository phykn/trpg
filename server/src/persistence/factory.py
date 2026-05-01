"""Factory: build SaveRepo / ScenarioRepo from env.

The running server always uses Supabase — both `APP_ENV=dev` and
`APP_ENV=release` are Supabase-backed; the env files differ only in
config knobs (basic auth, CORS, LLM routes), not in storage choice.

Tests construct `LocalFsSaveRepo` / `LocalFsScenarioRepo` directly with
tmp paths, so they bypass this factory and never hit a real Supabase.
"""

import os

from .repo import SaveRepo, ScenarioRepo
from .supabase import SupabaseSaveRepo, SupabaseStorageScenarioRepo


def build_save_repo() -> SaveRepo:
    return SupabaseSaveRepo(
        url=os.environ["SUPABASE_URL"],
        service_key=os.environ["SUPABASE_SERVICE_KEY"],
    )


def build_scenario_repo() -> ScenarioRepo:
    return SupabaseStorageScenarioRepo(
        url=os.environ["SUPABASE_URL"],
        service_key=os.environ["SUPABASE_SERVICE_KEY"],
        bucket=os.environ["SUPABASE_SCENARIO_BUCKET"],
    )

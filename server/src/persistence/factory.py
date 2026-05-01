"""Factory: pick a SaveRepo / ScenarioRepo pair based on `APP_ENV`.

- `APP_ENV=dev` (default): LocalFs adapters reading `SAVES_DIR`, `PROFILE_DIR`.
- `APP_ENV=release`: Supabase adapters reading `SUPABASE_URL`,
  `SUPABASE_SERVICE_KEY`, `SUPABASE_SCENARIO_BUCKET`.

Phase 1: the release branch instantiates the Supabase stubs which raise at
__init__ time, surfacing the missing implementation at startup rather than
at first request.
"""

import os

from .local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from .repo import SaveRepo, ScenarioRepo
from .supabase import SupabaseSaveRepo, SupabaseStorageScenarioRepo


def build_save_repo() -> SaveRepo:
    app_env = os.environ.get("APP_ENV", "dev")
    if app_env == "dev":
        return LocalFsSaveRepo(saves_dir=os.environ["SAVES_DIR"])
    if app_env == "release":
        return SupabaseSaveRepo(
            url=os.environ["SUPABASE_URL"],
            service_key=os.environ["SUPABASE_SERVICE_KEY"],
        )
    raise ValueError(f"unknown APP_ENV: {app_env!r}")


def build_scenario_repo() -> ScenarioRepo:
    app_env = os.environ.get("APP_ENV", "dev")
    if app_env == "dev":
        return LocalFsScenarioRepo(profile_dir=os.environ["PROFILE_DIR"])
    if app_env == "release":
        return SupabaseStorageScenarioRepo(
            url=os.environ["SUPABASE_URL"],
            service_key=os.environ["SUPABASE_SERVICE_KEY"],
            bucket=os.environ["SUPABASE_SCENARIO_BUCKET"],
        )
    raise ValueError(f"unknown APP_ENV: {app_env!r}")

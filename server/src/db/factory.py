"""Factory: build persistence repos from env.

Repos default to Supabase. Each repo can use LocalFs for dev by setting
`SAVE_REPO=local`, `SCENARIO_REPO=local`, or `GRAPH_REPO=local`.

Tests construct `LocalFsSaveRepo` / `LocalFsScenarioRepo` directly with
tmp paths, so they bypass this factory and never hit a real Supabase.
"""

import os

from .graph_local_fs import LocalFsGraphRepo
from .graph_supabase import SupabaseGraphRepo
from .local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from .repo import GraphRepo, SaveRepo, ScenarioRepo
from .supabase import SupabaseSaveRepo, SupabaseStorageScenarioRepo


def build_save_repo() -> SaveRepo:
    if os.environ.get("SAVE_REPO") == "local":
        return LocalFsSaveRepo(os.environ["SAVE_DIR"])
    return SupabaseSaveRepo(
        url=os.environ["SUPABASE_URL"],
        service_key=os.environ["SUPABASE_SERVICE_KEY"],
    )


def build_scenario_repo() -> ScenarioRepo:
    if os.environ.get("SCENARIO_REPO") == "local":
        return LocalFsScenarioRepo(os.environ["SCENARIO_DIR"])
    return SupabaseStorageScenarioRepo(
        url=os.environ["SUPABASE_URL"],
        service_key=os.environ["SUPABASE_SERVICE_KEY"],
        bucket=os.environ["SUPABASE_SCENARIO_BUCKET"],
    )


def build_graph_repo() -> GraphRepo:
    if os.environ.get("GRAPH_REPO") == "local":
        return LocalFsGraphRepo(os.environ["GRAPH_SAVE_DIR"])
    return SupabaseGraphRepo(
        url=os.environ["SUPABASE_URL"],
        service_key=os.environ["SUPABASE_SERVICE_KEY"],
    )

"""Factory: build persistence repos from env.

Repos default to Supabase. Scenario and graph repos can use LocalFs for dev by
setting `SCENARIO_REPO=local` or `GRAPH_REPO=local`.

Tests construct LocalFs repos directly with tmp paths, so they bypass this
factory and never hit a real Supabase.
"""

import os

from .graph.local_fs import LocalFsGraphRepo
from .graph.supabase import SupabaseGraphRepo
from .repo import GraphRepo, ScenarioRepo
from .scenario.local_fs import LocalFsScenarioRepo
from .scenario.supabase import SupabaseStorageScenarioRepo


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

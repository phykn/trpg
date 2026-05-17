"""Supabase Storage ScenarioRepo adapter."""

import asyncio
import json

from .._supabase_http import _Storage


class SupabaseStorageScenarioRepo:
    """ScenarioRepo over a Supabase Storage bucket. Per-process caches are process-lifetime; restart to reload."""

    def __init__(self, *, url: str, service_key: str, bucket: str) -> None:
        self._fs = _Storage(url, service_key, bucket)
        self._object_cache: dict[str, bytes] = {}
        self._listing_cache: dict[str, list[str]] = {}

    async def _get_bytes_cached(self, path: str) -> bytes:
        if path in self._object_cache:
            return self._object_cache[path]
        blob = await self._fs.get_bytes(path)
        self._object_cache[path] = blob
        return blob

    async def _list_prefix_cached(self, prefix: str) -> list[str]:
        if prefix in self._listing_cache:
            return self._listing_cache[prefix]
        files = await self._fs.list_prefix(prefix)
        self._listing_cache[prefix] = files
        return files

    async def profile_exists(self, profile: str) -> bool:
        try:
            await self._get_bytes_cached(f"{profile}/profile.json")
            return True
        except FileNotFoundError:
            return False

    async def list_profiles(self) -> list[dict]:
        profile_ids = await self._fs.list_dirs("")

        async def _build_one(pid: str) -> dict | None:
            try:
                meta_blob = await self._get_bytes_cached(f"{pid}/profile.json")
            except FileNotFoundError:
                return None
            meta = json.loads(meta_blob.decode("utf-8"))
            races: list[dict] = []
            for rd in (await self.load_seed_records(pid, "races")).values():
                if rd.get("playable", True) is False:
                    continue
                races.append(
                    {
                        "id": rd.get("id"),
                        "name": rd.get("name"),
                        "description": rd.get("description", ""),
                    }
                )
            return {
                "id": meta.get("id", pid),
                "name": meta.get("name", pid),
                "description": meta.get("description", ""),
                "races": races,
            }

        results = await asyncio.gather(
            *(_build_one(pid) for pid in sorted(profile_ids))
        )
        return [r for r in results if r is not None]

    async def read_world_md(self, profile: str, *, missing_ok: bool = False) -> str:
        try:
            blob = await self._get_bytes_cached(f"{profile}/world.md")
        except FileNotFoundError:
            if missing_ok:
                return ""
            raise
        return blob.decode("utf-8")

    async def read_start_json(self, profile: str) -> dict:
        blob = await self._get_bytes_cached(f"{profile}/start.json")
        return json.loads(blob.decode("utf-8"))

    async def read_player(self, profile: str) -> dict:
        blob = await self._get_bytes_cached(f"{profile}/player.json")
        return json.loads(blob.decode("utf-8"))

    async def load_seed_records(self, profile: str, kind: str) -> dict[str, dict]:
        try:
            blob = await self._get_bytes_cached(f"{profile}/{kind}.json")
        except FileNotFoundError:
            pass
        else:
            return _records_from_json(json.loads(blob.decode("utf-8")))

        files = await self._list_prefix_cached(f"{profile}/{kind}")
        json_files = sorted(f for f in files if f.endswith(".json"))

        async def _load_one(name: str) -> dict:
            blob = await self._get_bytes_cached(f"{profile}/{kind}/{name}")
            return json.loads(blob.decode("utf-8"))

        objs = await asyncio.gather(*(_load_one(f) for f in json_files))
        return {obj["id"]: obj for obj in objs if isinstance(obj.get("id"), str)}


def _records_from_json(value: object) -> dict[str, dict]:
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, dict):
        candidates = list(value.values())
    else:
        return {}

    records: dict[str, dict] = {}
    for obj in candidates:
        if not isinstance(obj, dict):
            continue
        record_id = obj.get("id")
        if isinstance(record_id, str):
            records[record_id] = obj
    return records

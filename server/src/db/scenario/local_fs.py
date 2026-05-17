"""Local filesystem ScenarioRepo used by tests and local dev."""

import json
from pathlib import Path

FileSignature = tuple[int, int]
DirectorySignature = tuple[tuple[str, int, int], ...]
RecordsSignature = tuple[str, FileSignature | DirectorySignature]


class LocalFsScenarioRepo:
    """Filesystem-backed ScenarioRepo over a single `profile_dir` root."""

    def __init__(self, profile_dir: str) -> None:
        self.profile_dir = profile_dir
        self._json_cache: dict[Path, tuple[FileSignature, dict]] = {}
        self._text_cache: dict[Path, tuple[FileSignature, str]] = {}
        self._records_cache: dict[
            tuple[str, str],
            tuple[RecordsSignature, dict[str, dict]],
        ] = {}

    def _root(self, profile: str) -> Path:
        return Path(self.profile_dir) / profile

    @staticmethod
    def _file_signature(path: Path) -> FileSignature:
        stat = path.stat()
        return (stat.st_mtime_ns, stat.st_size)

    @classmethod
    def _directory_signature(cls, files: list[Path]) -> DirectorySignature:
        return tuple((path.name, *cls._file_signature(path)) for path in files)

    def _read_json_cached(self, path: Path) -> dict:
        signature = self._file_signature(path)
        cached = self._json_cache.get(path)
        if cached is not None and cached[0] == signature:
            return cached[1]
        value = json.loads(path.read_text(encoding="utf-8"))
        self._json_cache[path] = (signature, value)
        return value

    def _read_text_cached(self, path: Path) -> str:
        signature = self._file_signature(path)
        cached = self._text_cache.get(path)
        if cached is not None and cached[0] == signature:
            return cached[1]
        value = path.read_text(encoding="utf-8")
        self._text_cache[path] = (signature, value)
        return value

    async def profile_exists(self, profile: str) -> bool:
        return self._root(profile).is_dir()

    async def list_profiles(self) -> list[dict]:
        pdir = Path(self.profile_dir)
        out: list[dict] = []
        if not pdir.is_dir():
            return out
        for sub in sorted(pdir.iterdir()):
            meta_file = sub / "profile.json"
            if not sub.is_dir() or not meta_file.exists():
                continue
            meta = self._read_json_cached(meta_file)
            races = [
                {
                    "id": rd.get("id"),
                    "name": rd.get("name"),
                    "description": rd.get("description", ""),
                }
                for rd in (await self.load_seed_records(sub.name, "races")).values()
                if rd.get("playable", True) is not False
            ]
            out.append(
                {
                    "id": meta.get("id", sub.name),
                    "name": meta.get("name", sub.name),
                    "description": meta.get("description", ""),
                    "races": races,
                }
            )
        return out

    async def read_world_md(self, profile: str, *, missing_ok: bool = False) -> str:
        p = self._root(profile) / "world.md"
        if missing_ok and not p.exists():
            return ""
        return self._read_text_cached(p)

    async def read_start_json(self, profile: str) -> dict:
        return self._read_json_cached(self._root(profile) / "start.json")

    async def read_player(self, profile: str) -> dict:
        return self._read_json_cached(self._root(profile) / "player.json")

    async def load_seed_records(self, profile: str, kind: str) -> dict[str, dict]:
        aggregate_path = self._root(profile) / f"{kind}.json"
        if aggregate_path.is_file():
            signature: RecordsSignature = (
                "file",
                self._file_signature(aggregate_path),
            )
            cache_key = (profile, kind)
            cached = self._records_cache.get(cache_key)
            if cached is not None and cached[0] == signature:
                return dict(cached[1])

            records = _records_from_json(self._read_json_cached(aggregate_path))
            self._records_cache[cache_key] = (signature, records)
            return dict(records)

        dirpath = self._root(profile) / kind
        if not dirpath.is_dir():
            return {}
        files = sorted(dirpath.glob("*.json"))
        signature = ("directory", self._directory_signature(files))
        cache_key = (profile, kind)
        cached = self._records_cache.get(cache_key)
        if cached is not None and cached[0] == signature:
            return dict(cached[1])

        records: dict[str, dict] = {}
        for f in files:
            obj = self._read_json_cached(f)
            record_id = obj.get("id")
            if isinstance(record_id, str):
                records[record_id] = obj
        self._records_cache[cache_key] = (signature, records)
        return dict(records)


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

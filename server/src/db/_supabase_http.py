"""httpx wrappers around Supabase PostgREST + Storage; supabase-py would pull deps that don't fit Pyodide. Non-2xx → PersistenceFailed."""

import json
from typing import Any
from urllib.parse import quote

import httpx

from src.game.domain.errors import PersistenceFailed


class _PostgREST:
    """Subset of PostgREST we need: upsert, bulk insert, select with filter+order+limit."""

    def __init__(self, base_url: str, service_key: str) -> None:
        self._base = base_url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(timeout=30.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def upsert(
        self, table: str, rows: list[dict[str, Any]], *, on_conflict: str
    ) -> None:
        """INSERT … ON CONFLICT (on_conflict) DO UPDATE."""
        if not rows:
            return
        url = f"{self._base}/{table}?on_conflict={on_conflict}"
        headers = {**self._headers, "Prefer": "resolution=merge-duplicates"}
        r = await self._client.post(url, headers=headers, content=json.dumps(rows))
        if r.status_code >= 300:
            raise PersistenceFailed(f"upsert {table}: {r.status_code} {r.text}")

    async def insert(self, table: str, rows: list[dict[str, Any]]) -> None:
        """Plain INSERT — fails on duplicate PK. Use for append-only tables."""
        if not rows:
            return
        url = f"{self._base}/{table}"
        r = await self._client.post(
            url, headers=self._headers, content=json.dumps(rows)
        )
        if r.status_code >= 300:
            raise PersistenceFailed(f"insert {table}: {r.status_code} {r.text}")

    async def delete(self, table: str, *, filters: dict[str, str]) -> None:
        params: list[tuple[str, str]] = []
        for col, expr in filters.items():
            params.append((col, expr))
        url = f"{self._base}/{table}"
        r = await self._client.delete(url, headers=self._headers, params=params)
        if r.status_code >= 300:
            raise PersistenceFailed(f"delete {table}: {r.status_code} {r.text}")

    async def select(
        self,
        table: str,
        *,
        filters: dict[str, str],
        select: str = "*",
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """GET with PostgREST filter syntax: filters {col: 'op.value'}."""
        params: list[tuple[str, str]] = [("select", select)]
        for col, expr in filters.items():
            params.append((col, expr))
        if order is not None:
            params.append(("order", order))
        if limit is not None:
            params.append(("limit", str(limit)))
        url = f"{self._base}/{table}"
        r = await self._client.get(url, headers=self._headers, params=params)
        if r.status_code >= 300:
            raise PersistenceFailed(f"select {table}: {r.status_code} {r.text}")
        return r.json()

    async def select_one(
        self, table: str, *, filters: dict[str, str], select: str = "*"
    ) -> dict[str, Any] | None:
        rows = await self.select(table, filters=filters, select=select, limit=1)
        return rows[0] if rows else None


class _Storage:
    """Subset of Supabase Storage we need: get one object, list under a prefix."""

    def __init__(self, base_url: str, service_key: str, bucket: str) -> None:
        self._base = base_url.rstrip("/") + "/storage/v1"
        self._bucket = bucket
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
        }
        self._client = httpx.AsyncClient(timeout=30.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_bytes(self, path: str) -> bytes:
        """Returns the raw object bytes. Raises PersistenceFailed on non-2xx
        (including 404 — caller catches if missing-ok semantics are needed)."""
        encoded = "/".join(quote(seg, safe="") for seg in path.split("/"))
        url = f"{self._base}/object/{self._bucket}/{encoded}"
        r = await self._client.get(url, headers=self._headers)
        if r.status_code == 404 or _is_storage_not_found(r):
            raise FileNotFoundError(path)
        if r.status_code >= 300:
            raise PersistenceFailed(f"storage get {path}: {r.status_code} {r.text}")
        return r.content

    async def put_bytes(
        self,
        path: str,
        blob: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload (or overwrite) a single object. Used by the scenario
        upload script — the server itself is read-only against scenarios."""
        encoded = "/".join(quote(seg, safe="") for seg in path.split("/"))
        url = f"{self._base}/object/{self._bucket}/{encoded}"
        headers = {
            **self._headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        r = await self._client.post(url, headers=headers, content=blob)
        if r.status_code >= 300:
            raise PersistenceFailed(f"storage put {path}: {r.status_code} {r.text}")

    async def _list_objects(self, prefix: str, *, label: str) -> list[dict[str, Any]]:
        url = f"{self._base}/object/list/{self._bucket}"
        body = {
            "prefix": prefix,
            "limit": 1000,
            "offset": 0,
            "sortBy": {"column": "name", "order": "asc"},
        }
        r = await self._client.post(
            url,
            headers={**self._headers, "Content-Type": "application/json"},
            content=json.dumps(body),
        )
        if r.status_code >= 300:
            raise PersistenceFailed(
                f"storage {label} {prefix}: {r.status_code} {r.text}"
            )
        return r.json()

    async def list_prefix(self, prefix: str) -> list[str]:
        """List object names directly under `prefix/` (one level, no recursion).

        Returns names relative to `prefix` (e.g. for prefix='default/items'
        returns ['sword.json', 'shield.json']). Subdirectories show up as
        names without `metadata` in the response — we filter to files only
        by checking `metadata` is non-null.
        """
        objs = await self._list_objects(prefix, label="list")
        return [obj["name"] for obj in objs if obj.get("metadata") is not None]

    async def list_dirs(self, prefix: str) -> list[str]:
        """List subdirectory names directly under `prefix/`. Folders are
        returned by Storage with `metadata: null`."""
        objs = await self._list_objects(prefix, label="list-dirs")
        return [obj["name"] for obj in objs if obj.get("metadata") is None]


def _is_storage_not_found(response: httpx.Response) -> bool:
    if response.status_code != 400:
        return False
    try:
        body = response.json()
    except json.JSONDecodeError:
        return False
    return body.get("statusCode") == "404" or body.get("error") == "not_found"

"""Upload a local scenario directory to the Supabase Storage bucket.

Usage (from the repo root):

    APP_ENV=release ../.venv/bin/python scripts/upload_scenarios.py ../scenarios/default

The script:
- Loads `.env.<APP_ENV>` (default 'release') for SUPABASE_URL /
  SUPABASE_SERVICE_KEY / SUPABASE_SCENARIO_BUCKET. APP_ENV defaults to
  `release` here because dev never uploads.
- Walks the given local dir recursively, uploading every file with a
  bucket key of `<dir-name>/<relpath>`. So `scenarios/default/items/sword.json`
  becomes `default/items/sword.json` in the bucket.
- Re-uploading is safe: x-upsert is on, files get overwritten in place.
- Files removed locally are NOT deleted from the bucket — clean stale
  uploads in the dashboard if needed.
"""

import asyncio
import mimetypes
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from src.persistence._supabase_http import _Storage  # noqa: E402


def _load_env() -> None:
    app_env = os.environ.setdefault("APP_ENV", "release")
    env_path = SERVER_DIR / f".env.{app_env}"
    if not env_path.is_file():
        sys.exit(f"env file not found: {env_path}")
    load_dotenv(env_path)


def _content_type(path: Path) -> str:
    guess, _ = mimetypes.guess_type(path.name)
    if guess:
        return guess
    if path.suffix == ".md":
        return "text/markdown"
    return "application/octet-stream"


async def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <local-profile-dir>")

    local = Path(sys.argv[1]).resolve()
    if not local.is_dir():
        sys.exit(f"not a directory: {local}")

    _load_env()
    try:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        bucket = os.environ["SUPABASE_SCENARIO_BUCKET"]
    except KeyError as e:
        sys.exit(f"missing env var: {e}")

    fs = _Storage(url, key, bucket)
    profile = local.name
    print(f"uploading {local} -> {bucket}/{profile}/")

    files = sorted(p for p in local.rglob("*") if p.is_file())
    if not files:
        print("  (no files)")
        await fs.aclose()
        return

    for f in files:
        rel = f.relative_to(local).as_posix()
        bucket_key = f"{profile}/{rel}"
        blob = f.read_bytes()
        await fs.put_bytes(bucket_key, blob, content_type=_content_type(f))
        print(f"  {bucket_key}  ({len(blob)}B)")

    await fs.aclose()
    print(f"done — {len(files)} files uploaded")


if __name__ == "__main__":
    asyncio.run(main())

"""Upload/download local scenario directories to release Supabase Storage."""

import argparse
import asyncio
import mimetypes
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT))

from src.db._supabase_http import _Storage  # noqa: E402
from src.env import load_server_env  # noqa: E402

load_server_env(ROOT / "server")
load_dotenv(ROOT / "server" / ".env.local")
load_dotenv(ROOT / "server" / ".env.google")


def _fail(cmd: str, e: Exception) -> int:
    if isinstance(e, FileNotFoundError):
        prefix = ""
    else:
        prefix = f"{type(e).__name__}: "
    print(f"{cmd} failed: {prefix}{e}", file=sys.stderr)
    return 1


def _content_type(path: Path) -> str:
    guess, _ = mimetypes.guess_type(path.name)
    if guess:
        return guess
    if path.suffix == ".md":
        return "text/markdown"
    return "application/octet-stream"


async def _upload_async(local: Path) -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    bucket = os.environ["SUPABASE_SCENARIO_BUCKET"]
    fs = _Storage(url, key, bucket)
    profile = local.name
    print(f"uploading {local} -> {bucket}/{profile}/")
    try:
        files = sorted(p for p in local.rglob("*") if p.is_file())
        if not files:
            print("  (no files)")
            return
        for f in files:
            rel = f.relative_to(local).as_posix()
            bucket_key = f"{profile}/{rel}"
            blob = f.read_bytes()
            await fs.put_bytes(bucket_key, blob, content_type=_content_type(f))
            print(f"  {bucket_key}  ({len(blob)}B)")
        print(f"done - {len(files)} files uploaded")
    finally:
        await fs.aclose()


def _cmd_upload(args: argparse.Namespace) -> int:
    local = Path(args.scenario_dir).resolve()
    if not local.is_dir():
        print(f"upload failed: not a directory: {local}", file=sys.stderr)
        return 1
    try:
        asyncio.run(_upload_async(local))
    except KeyError as e:
        print(f"upload failed: missing env var: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        return _fail("upload", e)
    print("OK")
    return 0


async def _walk_storage(fs: _Storage, prefix: str) -> list[str]:
    out: list[str] = []
    files = await fs.list_prefix(prefix)
    out.extend(f"{prefix}/{name}" for name in files)
    for sub in await fs.list_dirs(prefix):
        out.extend(await _walk_storage(fs, f"{prefix}/{sub}"))
    return out


async def _download_async(profile: str, dest: Path) -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    bucket = os.environ["SUPABASE_SCENARIO_BUCKET"]
    fs = _Storage(url, key, bucket)
    print(f"downloading {bucket}/{profile}/ -> {dest}")
    try:
        keys = await _walk_storage(fs, profile)
        if not keys:
            raise FileNotFoundError(f"profile not found in bucket: {profile}")
        for k in keys:
            rel = k[len(profile) + 1 :]
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            blob = await fs.get_bytes(k)
            out.write_bytes(blob)
            print(f"  {rel}  ({len(blob)}B)")
        print(f"done - {len(keys)} files downloaded")
    finally:
        await fs.aclose()


def _cmd_download(args: argparse.Namespace) -> int:
    profile = args.profile
    dest = (
        Path(args.out).resolve()
        if args.out
        else (ROOT / "scenarios" / profile).resolve()
    )
    if dest.exists():
        print(
            f"download failed: dest already exists (remove first to avoid mixing stale files): {dest}",
            file=sys.stderr,
        )
        return 1
    try:
        asyncio.run(_download_async(profile, dest))
    except KeyError as e:
        print(f"download failed: missing env var: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        return _fail("download", e)
    print("OK")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agency.story.tools.storage",
        description="Upload/download scenario directories to Supabase Storage.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp_up = sub.add_parser("upload", help="upload a local scenario directory")
    sp_up.add_argument("scenario_dir", help="local scenario directory")
    sp_up.set_defaults(func=_cmd_upload)

    sp_dl = sub.add_parser("download", help="download a scenario directory")
    sp_dl.add_argument("profile", help="scenario profile")
    sp_dl.add_argument(
        "--out",
        dest="out",
        default=None,
        help="output path (default: scenarios/<profile>); must not exist",
    )
    sp_dl.set_defaults(func=_cmd_download)
    return parser


def _main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def main() -> None:
    sys.exit(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()

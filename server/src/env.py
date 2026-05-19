import os
from pathlib import Path

from dotenv import dotenv_values


def load_server_env(server_dir: Path, app_env: str | None = None) -> None:
    """Load shared then environment-specific dotenv files.

    Values already present in the process environment, such as Render dashboard
    settings, keep priority over local files. Later dotenv files override
    earlier dotenv files.
    """
    existing_keys = set(os.environ)
    env_name = app_env or os.environ.get("APP_ENV", "dev")
    for path in (server_dir / ".env.shared", server_dir / f".env.{env_name}"):
        if path.is_file():
            _load_dotenv_values(path, existing_keys)


def _load_dotenv_values(path: Path, existing_keys: set[str]) -> None:
    for key, value in dotenv_values(path).items():
        if value is None or key in existing_keys:
            continue
        os.environ[key] = value

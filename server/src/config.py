"""Server settings from dotenv files and the process environment. Missing keys fail at startup."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


def load_server_env(server_dir: Path, app_env: str | None = None) -> None:
    """Load shared then environment-specific dotenv files; process values keep priority."""
    existing = set(os.environ)
    env_name = app_env or os.environ.get("APP_ENV", "dev")
    for path in (server_dir / ".env.shared", server_dir / f".env.{env_name}"):
        if path.is_file():
            for key, value in dotenv_values(path).items():
                if value is not None and key not in existing:
                    os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    basic_auth_user: str
    basic_auth_pass: str
    cors_origins: list[str]
    scenario_dir: Path
    save_dir: Path
    kev_base_url: str
    kev_min_confidence: float
    kev_api_key: str
    qwen_base_url: str
    qwen_model: str
    qwen_sampling: dict | None


def _path(server_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (server_dir / path).resolve()


def settings(server_dir: Path) -> Settings:
    env = os.environ
    sampling = env.get("QWEN_SAMPLING", "")
    return Settings(
        host=env["HOST"],
        port=int(env["PORT"]),
        basic_auth_user=env["BASIC_AUTH_USER"],
        basic_auth_pass=env["BASIC_AUTH_PASS"],
        cors_origins=[o.strip() for o in env["CORS_ORIGINS"].split(",") if o.strip()],
        scenario_dir=_path(server_dir, env["SCENARIO_DIR"]),
        save_dir=_path(server_dir, env["SAVE_DIR"]),
        kev_base_url=env["KEV_BASE_URL"],
        kev_min_confidence=float(env.get("KEV_MIN_CONFIDENCE") or 0.5),
        kev_api_key=env.get("KEV_API_KEY", ""),
        qwen_base_url=env["QWEN_BASE_URL"],
        qwen_model=env.get("QWEN_MODEL") or "auto",
        qwen_sampling=json.loads(sampling) if sampling else None,
    )

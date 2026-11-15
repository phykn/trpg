import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


def load_server_env(server_dir):
    """Process environment values win over the dotenv files."""
    existing = set(os.environ)
    for path in (server_dir / ".env.shared", server_dir / f".env.{os.environ.get('APP_ENV', 'dev')}"):
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
    decision_model: str
    decision_base_url: str
    llm_model: str
    llm_base_url: str


def _path(server_dir, value):
    path = Path(value)
    return path if path.is_absolute() else (server_dir / path).resolve()


def settings(server_dir):
    env = os.environ
    return Settings(
        host=env["HOST"],
        port=int(env["PORT"]),
        basic_auth_user=env["BASIC_AUTH_USER"],
        basic_auth_pass=env["BASIC_AUTH_PASS"],
        cors_origins=[o.strip() for o in env["CORS_ORIGINS"].split(",") if o.strip()],
        scenario_dir=_path(server_dir, env["SCENARIO_DIR"]),
        save_dir=_path(server_dir, env["SAVE_DIR"]),
        decision_model=env["DECISION_MODEL"],
        decision_base_url=env["DECISION_BASE_URL"],
        llm_model=env["LLM_MODEL"],
        llm_base_url=env["LLM_BASE_URL"],
    )

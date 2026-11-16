import os
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

SERVER_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Every setting. pydantic-settings reads the process environment over .env.shared over .env.<APP_ENV>."""

    model_config = SettingsConfigDict(
        env_file=(SERVER_DIR / ".env.shared", SERVER_DIR / f".env.{os.environ.get('APP_ENV', 'dev')}"),
        extra="ignore", frozen=True)

    host: str
    port: int
    basic_auth_user: str
    basic_auth_pass: str
    cors_origins: Annotated[list[str], NoDecode]
    scenario_dir: Path
    save_dir: Path
    decision_model: str
    decision_base_url: str
    llm_model: str
    llm_base_url: str

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        return [o.strip() for o in value.split(",") if o.strip()] if isinstance(value, str) else value

    @field_validator("scenario_dir", "save_dir", mode="after")
    @classmethod
    def from_server_dir(cls, value):
        return (SERVER_DIR / value).resolve()


def local_settings():
    # Personal env files never reach `--local`; only the models and their addresses may come from the process.
    env = os.environ
    return Settings(
        _env_file=None,
        host="127.0.0.1", port=8000, basic_auth_user="local", basic_auth_pass="local",
        cors_origins=["http://localhost:8090", "http://127.0.0.1:8090"],
        scenario_dir=SERVER_DIR.parent / "scenarios", save_dir=SERVER_DIR.parent / "saves" / "game",
        decision_model=env.get("DECISION_MODEL", "kanana"),
        decision_base_url=env.get("DECISION_BASE_URL", "http://127.0.0.1:8081"),
        llm_model=env.get("LLM_MODEL", "gemma4"),
        llm_base_url=env.get("LLM_BASE_URL", "http://127.0.0.1:8082/v1"),
    )


def env_settings():
    return Settings()

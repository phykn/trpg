import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


def load_server_env(server_dir: Path, app_env: str | None = None) -> None:
    """Process environment values win over the dotenv files."""
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
    decision_model: str           # malkuth (models/decision.py)
    decision_base_url: str
    decision_min_confidence: float | None
    decision_api_key: str
    llm_model: str                # qwen, gemma4 or minicpm (models/llm.py)
    llm_base_url: str
    llm_sampling: dict | None


def _path(server_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (server_dir / path).resolve()


def settings(server_dir: Path) -> Settings:
    env = os.environ
    sampling = env.get("LLM_SAMPLING", "")
    confidence = env.get("DECISION_MIN_CONFIDENCE", "")
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
        decision_min_confidence=float(confidence) if confidence else None,
        decision_api_key=env.get("DECISION_API_KEY", ""),
        llm_model=env["LLM_MODEL"],
        llm_base_url=env["LLM_BASE_URL"],
        llm_sampling=json.loads(sampling) if sampling else None,
    )

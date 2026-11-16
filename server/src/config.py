import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

SERVER_DIR = Path(__file__).resolve().parents[1]
KEYS = ("HOST", "PORT", "BASIC_AUTH_USER", "BASIC_AUTH_PASS", "CORS_ORIGINS", "SCENARIO_DIR", "SAVE_DIR",
        "DECISION_MODEL", "DECISION_BASE_URL", "LLM_MODEL", "LLM_BASE_URL")


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    basic_auth_user: str
    basic_auth_pass: str
    cors_origins: list
    scenario_dir: Path
    save_dir: Path
    decision_model: str
    decision_base_url: str
    llm_model: str
    llm_base_url: str


def local_settings():
    # Personal env files never reach `--local`; only the models and their addresses may come from the process.
    env = os.environ
    return Settings(
        host="127.0.0.1", port=8000, basic_auth_user="local", basic_auth_pass="local",
        cors_origins=["http://localhost:8090", "http://127.0.0.1:8090"],
        scenario_dir=SERVER_DIR.parent / "scenarios", save_dir=SERVER_DIR.parent / "saves" / "game",
        decision_model=env.get("DECISION_MODEL", "kanana"),
        decision_base_url=env.get("DECISION_BASE_URL", "http://127.0.0.1:8081"),
        llm_model=env.get("LLM_MODEL", "gemma4"),
        llm_base_url=env.get("LLM_BASE_URL", "http://127.0.0.1:8082/v1"),
    )


def env_settings():
    env = {}
    for path in (SERVER_DIR / ".env.shared", SERVER_DIR / f".env.{os.environ.get('APP_ENV', 'dev')}"):
        if path.is_file():
            env.update({k: v for k, v in dotenv_values(path).items() if v is not None})
    env.update(os.environ)
    missing = [k for k in KEYS if k not in env]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    return Settings(
        host=env["HOST"], port=int(env["PORT"]),
        basic_auth_user=env["BASIC_AUTH_USER"], basic_auth_pass=env["BASIC_AUTH_PASS"],
        cors_origins=[o.strip() for o in env["CORS_ORIGINS"].split(",") if o.strip()],
        scenario_dir=(SERVER_DIR / env["SCENARIO_DIR"]).resolve(), save_dir=(SERVER_DIR / env["SAVE_DIR"]).resolve(),
        decision_model=env["DECISION_MODEL"], decision_base_url=env["DECISION_BASE_URL"],
        llm_model=env["LLM_MODEL"], llm_base_url=env["LLM_BASE_URL"],
    )

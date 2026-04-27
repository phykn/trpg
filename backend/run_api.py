import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from src.api.routes import router
from src.llm import LLMClient

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_app(
    llm: LLMClient,
    basic_auth_user: str,
    basic_auth_pass: str,
    saves_dir: str,
    profile_dir: str,
) -> FastAPI:
    app = FastAPI(title="TRPG Backend API")
    app.state.llm = llm
    app.state.basic_auth_user = basic_auth_user
    app.state.basic_auth_pass = basic_auth_pass
    app.state.saves_dir = saves_dir
    app.state.profile_dir = profile_dir
    app.include_router(router)
    return app


def main() -> None:
    load_dotenv()

    host = os.environ["HOST"]
    port = int(os.environ["PORT"])
    base_url = os.environ["BASE_URL"]
    basic_auth_user = os.environ["BASIC_AUTH_USER"]
    basic_auth_pass = os.environ["BASIC_AUTH_PASS"]
    saves_dir = os.environ["SAVES_DIR"]
    profile_dir = os.environ["PROFILE_DIR"]

    llm = LLMClient(
        base_url=base_url,
        model="local",
        api_key="none",
        log_dir=REPO_ROOT / "logs",
    )
    app = build_app(
        llm=llm,
        basic_auth_user=basic_auth_user,
        basic_auth_pass=basic_auth_pass,
        saves_dir=saves_dir,
        profile_dir=profile_dir,
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from src.api.routes import router
from src.llm_client import LLMClient


def build_app(llm: LLMClient) -> FastAPI:
    app = FastAPI(title="TRPG Backend API")
    app.state.llm = llm
    app.include_router(router)
    return app


def main() -> None:
    load_dotenv()

    host = os.environ["HOST"]
    port = int(os.environ["PORT"])
    base_url = os.environ["BASE_URL"]

    llm = LLMClient(base_url=base_url, model="local", api_key="none")
    app = build_app(llm=llm)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

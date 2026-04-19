import argparse
import asyncio

import uvicorn
from fastapi import FastAPI

from src.api.routes import router
from src.llm_client import LLMClient


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", default="local")
    parser.add_argument("--api-key", default="none")
    parser.add_argument("--max-concurrency", type=int, default=2)
    return parser.parse_args()


def build_app(llm: LLMClient, max_concurrency: int) -> FastAPI:
    app = FastAPI(title="TRPG Backend API")
    app.state.llm = llm
    app.state.chat_sem = asyncio.Semaphore(max_concurrency)
    app.include_router(router)
    return app


def main() -> None:
    args = _parse_args()

    llm = LLMClient(base_url=args.base_url, model=args.model, api_key=args.api_key)
    app = build_app(llm=llm, max_concurrency=args.max_concurrency)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

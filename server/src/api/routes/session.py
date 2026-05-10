"""Session route aggregate."""

from fastapi import APIRouter

from . import session_graph, session_legacy

router = APIRouter()
router.include_router(session_graph.router)
router.include_router(session_legacy.router)

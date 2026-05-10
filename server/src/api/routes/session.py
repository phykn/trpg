"""Session route aggregate."""

from fastapi import APIRouter

from . import session_graph

router = APIRouter()
router.include_router(session_graph.router)

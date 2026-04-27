"""Top-level router that mounts every area-specific subrouter.
Public auth applies to everything except /health."""
from fastapi import APIRouter, Depends

from ..auth import require_basic_auth
from . import debug, health, profiles, session

router = APIRouter()
router.include_router(health.router)

protected = APIRouter(dependencies=[Depends(require_basic_auth)])
protected.include_router(profiles.router)
protected.include_router(session.router)
protected.include_router(debug.router)

router.include_router(protected)

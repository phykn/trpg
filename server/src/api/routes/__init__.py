"""Top-level router that mounts every area-specific subrouter.
Public auth applies to everything except /health and /version."""

from fastapi import APIRouter, Depends

from ..auth import require_basic_auth
from . import debug, health, profiles, session, version

router = APIRouter()
router.include_router(health.router)
router.include_router(version.router)

protected = APIRouter(dependencies=[Depends(require_basic_auth)])
protected.include_router(profiles.router)
protected.include_router(session.router)
protected.include_router(debug.router)

router.include_router(protected)

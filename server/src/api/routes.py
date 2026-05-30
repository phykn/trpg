"""Top-level router that mounts every area-specific subrouter.
Public auth applies to everything except /health and /version."""

import secrets

from fastapi import APIRouter, Depends
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import base_routes, session_graph_routes, story_dev_routes

security = HTTPBasic()


def require_basic_auth(
    request: Request,
    creds: HTTPBasicCredentials = Depends(security),
) -> None:
    expected_user: str = request.app.state.basic_auth_user
    expected_pass: str = request.app.state.basic_auth_pass
    user_ok = secrets.compare_digest(creds.username, expected_user)
    pass_ok = secrets.compare_digest(creds.password, expected_pass)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


router = APIRouter()
router.include_router(base_routes.public_router)

protected = APIRouter(dependencies=[Depends(require_basic_auth)])
protected.include_router(base_routes.protected_router)
protected.include_router(session_graph_routes.router)
protected.include_router(story_dev_routes.router)

router.include_router(protected)

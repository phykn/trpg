import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

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

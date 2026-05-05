import re

from ..locale import render
from .models import ErrorPayload

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _to_snake(name: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def emit_error(exc: Exception) -> dict:
    """SSE error event. Catalog miss falls back to error.runtime_generic."""
    cls = type(exc).__name__
    key = f"error.{_to_snake(cls)}"
    try:
        message = render(key, "ko")
    except KeyError:
        message = render("error.runtime_generic", "ko")
    payload = ErrorPayload(code=cls, message=message)
    return {"type": "error", "data": payload.model_dump()}

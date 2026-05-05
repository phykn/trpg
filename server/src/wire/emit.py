import re

from ..locale import render
from .models import ErrorPayload

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _to_snake(name: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def emit_error(
    code_or_exc: str | Exception,
    *,
    locale: str = "ko",
    message: str | None = None,
    **vars: object,
) -> dict:
    """SSE error event.

    - `code_or_exc` is an Exception (uses class name as code) or a string code.
    - `message` overrides catalog lookup when provided.
    - `**vars` pass to render() for catalog template interpolation.
    - Catalog miss without explicit message falls back to error.runtime_generic.
    """
    if isinstance(code_or_exc, Exception):
        code = type(code_or_exc).__name__
    else:
        code = code_or_exc

    if message is None:
        key = f"error.{_to_snake(code)}"
        try:
            message = render(key, locale, **vars)
        except KeyError:
            message = render("error.runtime_generic", locale)

    payload = ErrorPayload(code=code, message=message)
    return {"type": "error", "data": payload.model_dump()}

"""Global error handling: consistent envelope + request-id, no stack leaks.

Every error response has the same shape:
    {"error": {"code": <http_status>, "message": <str>, "request_id": <str>}}

Validation errors (422) include a ``details`` field. Unhandled exceptions are
logged with the request id and returned as an opaque 500 — the stack trace is
never sent to the client.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.observability.logging import get_logger

_log = get_logger("api.errors")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _envelope(code: int, message: str, request_id: str, **extra) -> dict:
    body = {"error": {"code": code, "message": message, "request_id": request_id}}
    body["error"].update(extra)
    return body


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        rid = _request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.status_code, str(exc.detail), rid),
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        rid = _request_id(request)
        return JSONResponse(
            status_code=422,
            content=_envelope(
                422, "Request validation failed", rid, details=exc.errors()
            ),
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        rid = _request_id(request)
        # Log the real error server-side; never leak internals to the client.
        _log.error("unhandled_exception", error=str(exc), error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=_envelope(500, "Internal server error", rid),
            headers={"X-Request-ID": rid},
        )

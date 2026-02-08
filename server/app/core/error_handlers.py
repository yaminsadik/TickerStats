"""
Standardized error response handlers for FastAPI.

All error responses include BOTH:
- "detail": <original FastAPI shape> (backward compatible)
- "error": { "code", "message", "request_id", "details"? } (new structured shape)

This is additive and non-breaking: consumers that read `detail` keep working,
and new consumers can use the structured `error` object.
"""

import logging
import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.middleware import request_id_var

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status code -> error code mapping
# ---------------------------------------------------------------------------

_STATUS_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _status_to_code(status_code: int) -> str:
    return _STATUS_CODE_MAP.get(status_code, f"HTTP_{status_code}")


# ---------------------------------------------------------------------------
# Custom application error (optional, for future use in routes)
# ---------------------------------------------------------------------------

class AppError(Exception):
    """Structured application error that routes can raise directly."""

    def __init__(
        self,
        status_code: int = 500,
        code: str | None = None,
        message: str = "An unexpected error occurred",
        details: object = None,
    ):
        self.status_code = status_code
        self.code = code or _status_to_code(status_code)
        self.message = message
        self.details = details
        super().__init__(message)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """Wrap FastAPI HTTPException: preserve detail, add error object."""
    req_id = request_id_var.get(None)
    detail = exc.detail  # original value (str or dict)
    message = detail if isinstance(detail, str) else str(detail)

    body = {
        "detail": detail,
        "error": {
            "code": _status_to_code(exc.status_code),
            "message": message,
            "request_id": req_id,
        },
    }
    return JSONResponse(status_code=exc.status_code, content=body)


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Wrap Pydantic validation errors: preserve detail, add error object."""
    req_id = request_id_var.get(None)
    errors = exc.errors()

    body = {
        "detail": errors,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "request_id": req_id,
            "details": errors,
        },
    }
    return JSONResponse(status_code=422, content=body)


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Handle custom AppError exceptions."""
    req_id = request_id_var.get(None)

    body = {
        "detail": exc.message,
        "error": {
            "code": exc.code,
            "message": exc.message,
            "request_id": req_id,
            **({"details": exc.details} if exc.details else {}),
        },
    }
    return JSONResponse(status_code=exc.status_code, content=body)


async def _handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions. Log traceback, never expose to client."""
    req_id = request_id_var.get(None)

    logger.error(
        "Unhandled exception: %s",
        exc,
        exc_info=True,
        extra={"request_id": req_id, "path": request.url.path},
    )

    body = {
        "detail": "Internal server error",
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "Internal server error",
            "request_id": req_id,
        },
    }
    return JSONResponse(status_code=500, content=body)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""
    app.add_exception_handler(HTTPException, _handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unhandled_exception)  # type: ignore[arg-type]

"""
Request timing middleware for FastAPI.

Provides:
- request_id_var: contextvar with the current request ID (UUID4 or from X-Request-ID header)
- current_user_id_var: contextvar set by auth dependency after successful authentication
- RequestTimingMiddleware: ASGI middleware that logs method, path, status, duration_ms, request_id, user_id
"""

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Context variables accessible from any downstream code
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
current_user_id_var: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that:
    - Generates or reads X-Request-ID header
    - Stores request_id in a ContextVar for structured logging
    - Times request duration
    - Logs completion with method, path, status_code, duration_ms, request_id, user_id

    Does NOT read request body or re-parse JWT.
    user_id is set by the auth dependency via current_user_id_var.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate request ID
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        # Set contextvars for this request
        rid_token = request_id_var.set(req_id)
        uid_token = current_user_id_var.set(None)

        # Also push into the Flask-style request context so the shared
        # JSONFormatter picks it up automatically
        try:
            from app.deck.utils.logging import set_request_context
            set_request_context(req_id)
        except ImportError:
            pass

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            user_id = current_user_id_var.get(None)
            logger.error(
                "Request failed",
                extra={
                    "request_id": req_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    **({"user_id": user_id} if user_id else {}),
                },
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)

            # Inject X-Request-ID into response
            response.headers["X-Request-ID"] = req_id

            # Read user_id that was set by auth dependency during this request
            user_id = current_user_id_var.get(None)

            log_data = {
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }
            if user_id:
                log_data["user_id"] = user_id

            logger.info(
                "%s %s %d %.0fms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                extra=log_data,
            )

            return response
        finally:
            request_id_var.reset(rid_token)
            current_user_id_var.reset(uid_token)
            try:
                from app.deck.utils.logging import clear_request_context
                clear_request_context()
            except ImportError:
                pass

"""
Structured JSON logging with request context for deck generation service.
"""

import json
import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from typing import Any, Optional

# Context variable for request-scoped data
_request_context: ContextVar[dict] = ContextVar("request_context", default={})


def set_request_context(request_id: str, **kwargs) -> None:
    """Set request context for logging."""
    ctx = {"request_id": request_id, **kwargs}
    _request_context.set(ctx)


def get_request_context() -> dict:
    """Get current request context."""
    return _request_context.get()


def clear_request_context() -> None:
    """Clear request context."""
    _request_context.set({})


class RequestContextFilter(logging.Filter):
    """Inject request_id into log records so text formatters never fail."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = get_request_context()
        request_id = ctx.get("request_id") if ctx else None
        if not getattr(record, "request_id", None):
            record.request_id = request_id or "-"
        return True


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    Outputs log records as JSON objects with consistent fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request context
        ctx = get_request_context()
        if ctx:
            log_data["request_id"] = ctx.get("request_id")
            if "ticker" in ctx:
                log_data["ticker"] = ctx["ticker"]
            if "provider" in ctx:
                log_data["provider"] = ctx["provider"]

        # Add extra fields from the record
        if hasattr(record, "extra_data") and record.extra_data:
            log_data["data"] = record.extra_data

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add location info
        log_data["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        return json.dumps(log_data, default=str)


class ContextLogger(logging.LoggerAdapter):
    """
    Logger adapter that automatically includes request context.
    """

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        # Merge context into extra
        extra = kwargs.get("extra", {})
        ctx = get_request_context()
        extra.update(ctx)
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> ContextLogger:
    """
    Get a context-aware logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        ContextLogger instance with JSON formatting
    """
    logger = logging.getLogger(name)
    return ContextLogger(logger, {})


def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
    stream: Any = None,
) -> None:
    """
    Configure root logger for the deck service.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Whether to use JSON formatting
        stream: Output stream (defaults to sys.stdout)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setLevel(root_logger.level)
    handler.addFilter(RequestContextFilter())

    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(handler)


def log_with_data(logger: logging.Logger, level: int, message: str, **data) -> None:
    """
    Log a message with additional structured data.
    
    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        **data: Additional data to include
    """
    record = logger.makeRecord(
        logger.name,
        level,
        "",
        0,
        message,
        (),
        None,
    )
    record.extra_data = data
    logger.handle(record)


def log_operation(operation: str, include_result: bool = False):
    """
    Decorator for logging function entry/exit with timing.
    
    Args:
        operation: Operation name for logging
        include_result: Whether to log return value
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = datetime.utcnow()
            
            logger.info(f"Starting {operation}", extra={
                "operation": operation,
                "phase": "start",
            })
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                log_extra = {
                    "operation": operation,
                    "phase": "complete",
                    "duration_ms": round(duration_ms, 2),
                }
                if include_result and result is not None:
                    log_extra["result_summary"] = str(result)[:200]
                
                logger.info(f"Completed {operation}", extra=log_extra)
                return result
                
            except Exception as e:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.error(
                    f"Failed {operation}: {e}",
                    extra={
                        "operation": operation,
                        "phase": "error",
                        "duration_ms": round(duration_ms, 2),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                raise
                
        return wrapper
    return decorator


def log_operation_async(operation: str, include_result: bool = False):
    """
    Async decorator for logging function entry/exit with timing.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = datetime.utcnow()
            
            logger.info(f"Starting {operation}", extra={
                "operation": operation,
                "phase": "start",
            })
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                log_extra = {
                    "operation": operation,
                    "phase": "complete",
                    "duration_ms": round(duration_ms, 2),
                }
                if include_result and result is not None:
                    log_extra["result_summary"] = str(result)[:200]
                
                logger.info(f"Completed {operation}", extra=log_extra)
                return result
                
            except Exception as e:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.error(
                    f"Failed {operation}: {e}",
                    extra={
                        "operation": operation,
                        "phase": "error",
                        "duration_ms": round(duration_ms, 2),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                raise
                
        return wrapper
    return decorator

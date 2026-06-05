"""Unified error handling middleware and exception handlers."""
import traceback
import logging
from typing import Union, Dict, Any, Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

logger = logging.getLogger("vllm-dashboard")


class AppError(Exception):
    """Base application error with error code and HTTP status."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND", details: dict = None):
        super().__init__(message=message, code=code, status_code=404, details=details)


class ValidationError_(AppError):
    def __init__(self, message: str = "Validation failed", code: str = "VALIDATION_ERROR", details: dict = None):
        super().__init__(message=message, code=code, status_code=400, details=details)


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication required", code: str = "AUTHENTICATION_ERROR", details: dict = None):
        super().__init__(message=message, code=code, status_code=401, details=details)


class AuthorizationError(AppError):
    def __init__(self, message: str = "Insufficient permissions", code: str = "AUTHORIZATION_ERROR", details: dict = None):
        super().__init__(message=message, code=code, status_code=403, details=details)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT_ERROR", details: dict = None):
        super().__init__(message=message, code=code, status_code=409, details=details)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str = "Service unavailable", code: str = "SERVICE_UNAVAILABLE", details: dict = None):
        super().__init__(message=message, code=code, status_code=503, details=details)


def build_error_response(
    code: str,
    message: str,
    status_code: int,
    details: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None
) -> JSONResponse:
    """Build standardized error response."""
    body = {
        "error": {
            "code": code,
            "message": message,
            "status": status_code,
        }
    }
    if details:
        body["error"]["details"] = details
    if path:
        body["error"]["path"] = path
    return JSONResponse(status_code=status_code, content=body)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle custom application errors."""
    logger.warning(
        f"AppError: {exc.code} - {exc.message}",
        extra={"path": str(request.url), "details": exc.details}
    )
    return build_error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        path=str(request.url.path)
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard HTTP exceptions."""
    logger.warning(
        f"HTTPException: {exc.status_code} - {exc.detail}",
        extra={"path": str(request.url)}
    )
    return build_error_response(
        code="HTTP_ERROR",
        message=str(exc.detail),
        status_code=exc.status_code,
        path=str(request.url.path)
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    logger.warning(
        f"ValidationError: {len(errors)} errors",
        extra={"path": str(request.url), "errors": errors}
    )
    return build_error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"errors": errors},
        path=str(request.url.path)
    )


async def pydantic_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    logger.warning(
        f"PydanticValidationError: {len(errors)} errors",
        extra={"path": str(request.url), "errors": errors}
    )
    return build_error_response(
        code="VALIDATION_ERROR",
        message="Data validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"errors": errors},
        path=str(request.url.path)
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    logger.error(
        f"UnhandledException: {type(exc).__name__}: {str(exc)}",
        extra={
            "path": str(request.url),
            "traceback": traceback.format_exc()
        },
        exc_info=True
    )
    return build_error_response(
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        path=str(request.url.path)
    )


def register_error_handlers(app):
    """Register all error handlers on the FastAPI app."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    logger.info("Error handlers registered successfully")
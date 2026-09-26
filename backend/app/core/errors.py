import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    message = "Something went wrong."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or type(self).message
        self.code = code or type(self).code
        self.details = details or {}
        super().__init__(self.message)


class UnauthenticatedError(AppError):
    status_code = 401
    code = "UNAUTHENTICATED"
    message = "Authentication is required."


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "You do not have permission to do this."


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Resource not found."


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "The request conflicts with the current state."


class UnprocessableError(AppError):
    status_code = 422
    code = "UNPROCESSABLE"
    message = "The request cannot be processed."


# Constraint name (see core/base.py naming convention) -> error raised to the client.
_CONSTRAINT_ERRORS: dict[str, Callable[[], AppError]] = {
    "uq_users_email": lambda: ConflictError(
        "This email is already registered.", code="EMAIL_TAKEN"
    ),
    "ex_bookings_provider_overlap": lambda: ConflictError(
        "This time was just booked by someone else.", code="SLOT_TAKEN"
    ),
    "ex_bookings_client_overlap": lambda: ConflictError(
        "You already have a booking at this time.", code="CLIENT_OVERLAP"
    ),
}


@contextmanager
def translate_integrity_errors(db: Session) -> Iterator[None]:
    try:
        yield
    except IntegrityError as exc:
        db.rollback()
        diagnostics = getattr(exc.orig, "diag", None)
        constraint = getattr(diagnostics, "constraint_name", None)
        make_error = _CONSTRAINT_ERRORS.get(constraint or "")
        if make_error is None:
            raise
        raise make_error() from exc


_HTTP_STATUS_CODES = {
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


def error_response(
    status_code: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    return JSONResponse(status_code=status_code, content=body)


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(AppError, exc)
    return error_response(error.status_code, error.code, error.message, error.details)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    errors = cast(RequestValidationError, exc).errors()
    fields = {".".join(str(part) for part in error["loc"]): error["msg"] for error in errors}
    return error_response(422, "VALIDATION_ERROR", "Some fields are invalid.", {"fields": fields})


async def _handle_http_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(StarletteHTTPException, exc)
    code = _HTTP_STATUS_CODES.get(error.status_code, "HTTP_ERROR")
    return error_response(error.status_code, code, str(error.detail))


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(500, AppError.code, AppError.message)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)

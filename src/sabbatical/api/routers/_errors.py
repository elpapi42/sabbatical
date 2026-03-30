"""Shared exception-to-response mapping for API routers."""

from fastapi import Request
from fastapi.responses import JSONResponse

from sabbatical.core.exceptions import (
    ConflictError,
    NotFoundError,
    PreconditionError,
    SabbaticalError,
    ValidationError,
)


async def core_error_handler(request: Request, exc: SabbaticalError) -> JSONResponse:
    if isinstance(exc, NotFoundError):
        return JSONResponse(status_code=404, content={"message": str(exc)})
    if isinstance(exc, ConflictError):
        return JSONResponse(status_code=409, content={"message": str(exc)})
    if isinstance(exc, ValidationError):
        return JSONResponse(status_code=422, content={"message": str(exc)})
    if isinstance(exc, PreconditionError):
        return JSONResponse(status_code=412, content={"message": str(exc)})
    # Unexpected SabbaticalError subclass — let FastAPI's 500 handler take it
    raise exc

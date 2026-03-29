"""Global FastAPI exception handlers — normalizes all error responses."""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("tinysignage.errors")


def register_error_handlers(app: FastAPI) -> None:
    """Attach exception handlers to the FastAPI app."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "status_code": exc.status_code},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        log.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "detail": str(exc.errors()),
                "status_code": 422,
                "user_message": "Some fields are invalid. Please check your input.",
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Attach request context so JsonErrorHandler can include it
        extra = {
            "request_method": request.method,
            "request_path": request.url.path,
            "client_ip": request.client.host if request.client else "unknown",
        }
        log.error(
            "Unhandled exception on %s %s: %s",
            request.method,
            request.url.path,
            str(exc),
            exc_info=exc,
            extra=extra,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Something went wrong on the server. The error has been logged.",
                "status_code": 500,
            },
        )

"""Stable API error responses."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: object | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_response(error: ApiError) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=error.code,
            message=error.message,
            details=error.details,
        )
    )
    return JSONResponse(status_code=error.status_code, content=body.model_dump())


def install_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApiError)
    async def api_error_handler(_: Request, error: ApiError) -> JSONResponse:
        return error_response(error)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, error: RequestValidationError
    ) -> JSONResponse:
        details = []
        for item in error.errors():
            safe: Mapping[str, object] = {
                key: value
                for key, value in item.items()
                if key not in {"input", "ctx"}
            }
            details.append(dict(safe))
        return error_response(
            ApiError(
                status_code=422,
                code="validation_error",
                message="The request is invalid.",
                details=details,
            )
        )

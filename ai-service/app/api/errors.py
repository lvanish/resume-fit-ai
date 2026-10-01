import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.laya_service import (
    LayaInferenceError,
    LayaInitializationError,
    LayaInputError,
    LayaInvalidResponseError,
)
from app.services.llm_service import ExtractionError

logger = logging.getLogger(__name__)


def _log_analyze_failure(stage: str, exc: Exception) -> None:
    logger.exception(
        "requirement_matching_failed stage=%s exception_type=%s message=%s",
        stage,
        type(exc).__name__,
        exc,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(LayaInputError)
    async def input_error(_request: Request, exc: LayaInputError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"code": "VALIDATION_ERROR", "message": str(exc)},
        )

    @app.exception_handler(LayaInitializationError)
    async def init_error(_request: Request, exc: LayaInitializationError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"code": "LAYA_UNAVAILABLE", "message": str(exc)},
        )

    @app.exception_handler(LayaInferenceError)
    async def inference_error(_request: Request, exc: LayaInferenceError) -> JSONResponse:
        _log_analyze_failure("laya_inference", exc)
        return JSONResponse(
            status_code=502,
            content={"code": "LAYA_INFERENCE_FAILED", "message": str(exc)},
        )

    @app.exception_handler(ExtractionError)
    async def extraction_error(_request: Request, exc: ExtractionError) -> JSONResponse:
        _log_analyze_failure("extraction", exc)
        return JSONResponse(
            status_code=502,
            content={"code": "EXTRACTION_FAILED", "message": str(exc)},
        )

    @app.exception_handler(LayaInvalidResponseError)
    async def invalid_response(_request: Request, exc: LayaInvalidResponseError) -> JSONResponse:
        _log_analyze_failure("laya_result_parsing", exc)
        return JSONResponse(
            status_code=502,
            content={"code": "LAYA_INVALID_RESPONSE", "message": str(exc)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        parts: list[str] = []
        for error in exc.errors():
            location = ".".join(str(item) for item in error.get("loc", []) if item != "body")
            parts.append(f"{location}: {error.get('msg', 'invalid value')}")
        message = "; ".join(parts) if parts else "Request validation failed."
        return JSONResponse(
            status_code=400,
            content={"code": "VALIDATION_ERROR", "message": message},
        )

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected AI service error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "The AI service encountered an unexpected error.",
            },
        )

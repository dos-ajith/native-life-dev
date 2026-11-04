import asyncio
import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.api.websocket_docs import router as websocket_docs_router
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.exceptions import AppError
from app.core.logging import RequestLoggingMiddleware, setup_logging
from app.core.messages import HttpMessages, RealtimeMessages, ValidationMessages
from app.core.openapi_tags import OPENAPI_TAGS
from app.plugins.bootstrap import load_plugin_registry
from app.plugins.mounting import mount_plugins
from app.realtime.connection_manager import CloseCode, get_connection_manager
from app.realtime.publisher import get_realtime_publisher
from app.services.app_formatting_service import refresh_datetime_formats
from app.services.app_timezone_service import refresh_app_timezone
from app.services.push_publisher import get_push_publisher

settings = get_settings()
setup_logging(settings)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up: %s (%s)", settings.app_name, settings.app_env)
    with SessionLocal() as db:
        refresh_app_timezone(db)
        refresh_datetime_formats(db)
        plugin_registry = load_plugin_registry(db, settings)
    mount_plugins(application, plugin_registry, settings.api_v1_prefix)
    publisher = get_realtime_publisher()
    publisher.bind_loop(asyncio.get_running_loop())
    yield
    publisher.unbind_loop()
    get_push_publisher().shutdown()
    await get_connection_manager().close_all(CloseCode.GOING_AWAY, RealtimeMessages.SERVER_SHUTDOWN)
    engine.dispose()
    logger.info("Shutting down")


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.upload_dir), name="media")

Path(settings.private_upload_dir).mkdir(parents=True, exist_ok=True)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "errors": exc.errors},
    )


_HTTP_ERROR_MESSAGES = {
    404: HttpMessages.ENDPOINT_NOT_FOUND,
    405: HttpMessages.METHOD_NOT_ALLOWED,
}


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": _HTTP_ERROR_MESSAGES.get(exc.status_code, HttpMessages.REQUEST_FAILED),
            "errors": [],
        },
        headers=exc.headers,
    )


_VALIDATION_LOC_PREFIXES = {"body", "query", "path", "header", "cookie"}
_VALUE_ERROR_PREFIX = "Value error, "
_JSON_DECODE_ERROR_TYPES = {"json_invalid", "json_type"}


def _validation_field_name(loc: Sequence[int | str]) -> str | None:
    parts = [str(segment) for segment in loc if str(segment) not in _VALIDATION_LOC_PREFIXES]
    return ".".join(parts) if parts else None


def _validation_message(msg: str) -> str:
    return msg.removeprefix(_VALUE_ERROR_PREFIX)


def _combine_field_and_message(field: str | None, message: str) -> str:
    return f"{field}: {message}" if field else message


def _format_validation_error(error: Mapping[str, Any]) -> dict[str, str | None]:
    if error.get("type") in _JSON_DECODE_ERROR_TYPES:
        return {"field": None, "message": ValidationMessages.INVALID_JSON_BODY}
    field = _validation_field_name(error["loc"])
    message = (
        ValidationMessages.FIELD_REQUIRED
        if error.get("type") == "missing"
        else _validation_message(error["msg"])
    )
    return {
        "field": field,
        "message": _combine_field_and_message(field, message),
    }


def _validation_error_response(errors: Sequence[Mapping[str, Any]]) -> JSONResponse:
    formatted_errors = [_format_validation_error(error) for error in errors]
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation failed",
            "errors": formatted_errors,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return _validation_error_response(exc.errors())


@app.exception_handler(ValidationError)
async def pydantic_validation_error_handler(
    _request: Request, exc: ValidationError
) -> JSONResponse:
    return _validation_error_response(exc.errors())


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    message = str(exc) if settings.debug else "Internal server error"
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": message, "errors": []},
    )


app.include_router(api_router, prefix=settings.api_v1_prefix)

if not settings.is_production:
    app.include_router(websocket_docs_router)

import logging

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.routes import router


def _configure_logging() -> None:
    """Show match metadata on the server. Document text is never logged."""
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    if not any(isinstance(handler, logging.StreamHandler) for handler in app_logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        app_logger.addHandler(handler)


def create_app() -> FastAPI:
    _configure_logging()
    application = FastAPI(title="ResumeFit AI Service", version="0.1.0")
    register_exception_handlers(application)
    application.include_router(router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()

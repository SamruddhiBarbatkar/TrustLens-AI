from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.analyses import router as analyses_router
from app.core.config import Settings
from app.core.errors import (
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from app.db.mongodb import MongoDB
from app.db.users import UserRepository
from app.db.analyses import AnalysisRepository
from app.services.tampering_detector import TamperingDetector
from app.services.ai_detector import AIGenerationDetector
from app.services.ocr import OCRService
from app.services.ela import ELAService
from app.services.analysis import ImageAnalysisService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    mongodb = MongoDB(app.state.settings)
    app.state.mongodb = mongodb
    app.state.user_repository = None
    app.state.analysis_repository = None
    if await mongodb.connect():
        try:
            user_repository = UserRepository(mongodb.database())
            analysis_repository = AnalysisRepository(mongodb.database())
            await user_repository.ensure_indexes()
            await analysis_repository.ensure_indexes()
        except PyMongoError:
            await mongodb.close()
        else:
            app.state.user_repository = user_repository
            app.state.analysis_repository = analysis_repository
    try:
        yield
    finally:
        await mongodb.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings.from_environment()
    app = FastAPI(
        title="TrustLens API",
        version="0.1.0",
        description="Backend API for TrustLens image verification workflows.",
        debug=runtime_settings.debug,
        docs_url="/docs" if runtime_settings.debug else None,
        redoc_url="/redoc" if runtime_settings.debug else None,
        openapi_url="/openapi.json" if runtime_settings.debug else None,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.tampering_detector = TamperingDetector(runtime_settings.tampering_model_path)
    app.state.ai_generation_detector = AIGenerationDetector(runtime_settings.ai_detector_model_path)
    app.state.ocr_service = OCRService(
        runtime_settings.easyocr_model_storage_path,
        runtime_settings.easyocr_download_enabled,
    )
    app.state.ela_service = ELAService()
    app.state.analysis_service = ImageAnalysisService(
        app.state.tampering_detector,
        app.state.ai_generation_detector,
        app.state.ocr_service,
        app.state.ela_service,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(analyses_router, prefix="/api/v1")
    return app


app = create_app()

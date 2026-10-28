from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.version import API_VERSION, PIPELINE_VERSION
from app.analysis.reliability_calibrated_fusion import FUSION_POLICY
from app.api.claims import router as claims_router
from app.api.uploads import router as uploads_router
from app.api.verification import router as verification_router
from app.api.auth import ensure_bootstrap_admin, router as auth_router
from app.api.admin import router as admin_router


@asynccontextmanager
async def lifespan(app):
    if settings.database_backend == "mongodb":
        from app.db.mongo_database import initialize_mongodb

        initialize_mongodb()
    ensure_bootstrap_admin()
    yield

app = FastAPI(
    title="TrustLens API",
    description="Multimodal Claim Evidence Verification System",
    version=API_VERSION,
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,

    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(claims_router)
app.include_router(uploads_router)
app.include_router(verification_router)
app.include_router(auth_router)
app.include_router(admin_router)

@app.get("/")
def root():
    return {
        "message": "TrustLens API is running",
        "api_version": API_VERSION,
        "pipeline_version": PIPELINE_VERSION
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "api_version": API_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "detector_policy_mode": settings.detector_policy_mode,
        "fusion_policy_version": FUSION_POLICY["policy_version"],
        "fusion_policy_validated": FUSION_POLICY["validated"]
    }

import asyncio
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from PIL import Image, UnidentifiedImageError

from app.api.dependencies import (
    get_analysis_repository,
    get_analysis_service,
    get_current_user,
)
from app.db.analyses import AnalysisRepository
from app.models.user import User
from app.schemas.analysis import AnalysisHistoryResponse, AnalysisResponse, ReportTitleUpdate
from app.services.analysis import ImageAnalysisService
from app.services.image_artifacts import ImageArtifactStore
from app.services.reports import build_analysis_report
from app.services.report_narrative import GrokReportNarrativeService


router = APIRouter(prefix="/analyses", tags=["analyses"])
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024


def _analysis_response(record: object) -> AnalysisResponse:
    return AnalysisResponse(
        id=record.id,
        created_at=record.created_at,
        signals=record.signals,
        trust_score=record.trust_score,
        explanation=record.explanation,
        report_title=record.report_title,
        source_image_available=record.image_artifact_filename is not None,
    )


@router.get("/{analysis_id}/report")
async def download_report(analysis_id: str, request: Request, current_user: Annotated[User, Depends(get_current_user)], repository: Annotated[AnalysisRepository, Depends(get_analysis_repository)]) -> Response:
    analysis = await repository.find_for_owner(analysis_id, current_user.id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report is not available.")
    narrative = await asyncio.to_thread(
        GrokReportNarrativeService(request.app.state.settings.xai_api_key, request.app.state.settings.xai_model).generate,
        analysis,
    )
    return Response(build_analysis_report(analysis, narrative), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="trustlens-{analysis.id}.pdf"'})


@router.get("/{analysis_id}/source-image")
async def download_source_image(
    analysis_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[AnalysisRepository, Depends(get_analysis_repository)],
) -> FileResponse:
    """Return a normalized uploaded image only to its authenticated owner."""
    analysis = await repository.find_for_owner(analysis_id, current_user.id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image is not available.")
    artifact_path = ImageArtifactStore(request.app.state.settings.uploads_path).path_for(
        analysis.image_artifact_filename
    )
    if artifact_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image is not available.")
    return FileResponse(
        artifact_path,
        media_type="image/png",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("", response_model=AnalysisHistoryResponse)
async def list_analyses(
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[AnalysisRepository, Depends(get_analysis_repository)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnalysisHistoryResponse:
    records = await repository.list_for_owner(current_user.id, limit, offset)
    return AnalysisHistoryResponse(
        items=[_analysis_response(record) for record in records],
        limit=limit,
        offset=offset,
    )


async def _decode_image(upload: UploadFile) -> Image.Image:
    if upload.content_type is None or not upload.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Image file is invalid.")
    data = await upload.read(MAX_IMAGE_UPLOAD_BYTES + 1)
    if len(data) > MAX_IMAGE_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Image file is too large.")
    try:
        with Image.open(BytesIO(data)) as source:
            source.verify()
        with Image.open(BytesIO(data)) as source:
            return source.convert("RGB").copy()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Image file is invalid.") from None


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    image: Annotated[UploadFile, File(...)],
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[AnalysisRepository, Depends(get_analysis_repository)],
    service: Annotated[ImageAnalysisService, Depends(get_analysis_service)],
) -> AnalysisResponse:
    """Analyze one decoded image and persist it under the authenticated user only."""
    decoded_image = await _decode_image(image)
    signals, trust_score = await asyncio.to_thread(service.analyze, decoded_image)
    explanation = service.explain_evidence(signals, trust_score)
    artifact_store = ImageArtifactStore(request.app.state.settings.uploads_path)
    try:
        image_artifact_filename = await asyncio.to_thread(artifact_store.save, decoded_image)
    except OSError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image storage is unavailable. Please try again.",
        ) from None
    try:
        analysis = await repository.create(
            current_user.id,
            signals,
            trust_score,
            explanation,
            image_artifact_filename,
        )
    except Exception:
        await asyncio.to_thread(artifact_store.remove, image_artifact_filename)
        raise
    return _analysis_response(analysis)


@router.patch("/{analysis_id}/report-title", response_model=AnalysisResponse)
async def update_report_title(
    analysis_id: str,
    payload: ReportTitleUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[AnalysisRepository, Depends(get_analysis_repository)],
) -> AnalysisResponse:
    analysis = await repository.update_report_title(analysis_id, current_user.id, payload.report_title)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report is not available.")
    return _analysis_response(analysis)

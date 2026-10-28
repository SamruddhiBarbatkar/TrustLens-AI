from pathlib import Path
from uuid import uuid4
import warnings
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile
)
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user, require_claim_access
from app.db.database import get_db
from app.db.models import Claim, Evidence, User


router = APIRouter(
    prefix="/claims",
    tags=["Evidence Upload"]
)


ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

EXPECTED_IMAGE_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP"
}

ALLOWED_CONTENT_TYPES = {
    ".jpg": {"image/jpeg", "application/octet-stream"},
    ".jpeg": {"image/jpeg", "application/octet-stream"},
    ".png": {"image/png", "application/octet-stream"},
    ".webp": {"image/webp", "application/octet-stream"}
}

RESPONSE_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp"
}

ALLOWED_SOURCE_TYPES = {
    "ORIGINAL_CAMERA",
    "DEVICE_GALLERY",
    "DOCUMENT_SCAN",
    "RECEIVED_FROM_OTHER",
    "UNSPECIFIED"
}


class UploadValidationError(ValueError):
    pass


def remove_file_if_present(file_path):
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass


def validate_saved_file(file_path, extension):
    expected_format = EXPECTED_IMAGE_FORMATS[extension]

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning
            )

            with Image.open(file_path) as image:
                detected_format = image.format
                dimensions = image.size
                image.verify()

    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning
    ) as error:
        raise UploadValidationError(
            "The image dimensions exceed the safety limit."
        ) from error

    except Exception as error:
        raise UploadValidationError(
            "The uploaded file is not a valid image."
        ) from error

    if detected_format != expected_format:
        raise UploadValidationError(
            "The file content does not match its extension."
        )

    return dimensions


def normalize_evidence_context(
    description,
    source_type,
    captured_at,
    location_label
):
    normalized_description = " ".join((description or "").split())
    normalized_location = " ".join((location_label or "").split())
    normalized_source = (source_type or "UNSPECIFIED").strip().upper()

    if len(normalized_description) > 500:
        raise HTTPException(
            status_code=400,
            detail="Evidence descriptions cannot exceed 500 characters."
        )

    if len(normalized_location) > 160:
        raise HTTPException(
            status_code=400,
            detail="Evidence locations cannot exceed 160 characters."
        )

    if normalized_source not in ALLOWED_SOURCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid evidence source type."
        )

    parsed_capture_time = None
    if captured_at:
        try:
            parsed_capture_time = datetime.fromisoformat(captured_at)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail="Evidence capture time must be a valid ISO date and time."
            ) from error

    return {
        "description": normalized_description or None,
        "source_type": normalized_source,
        "captured_at": parsed_capture_time,
        "location_label": normalized_location or None
    }


def save_upload_with_limit(upload_file, destination):
    total_bytes = 0

    with destination.open("xb") as buffer:
        while True:
            chunk = upload_file.file.read(
                settings.upload_chunk_bytes
            )

            if not chunk:
                break

            total_bytes += len(chunk)

            if total_bytes > settings.max_upload_bytes:
                maximum_megabytes = (
                    settings.max_upload_bytes /
                    (1024 * 1024)
                )
                raise UploadValidationError(
                    "The uploaded file exceeds the "
                    f"{maximum_megabytes:g} MB limit."
                )

            buffer.write(chunk)

    if total_bytes == 0:
        raise UploadValidationError(
            "The uploaded file is empty."
        )

    return total_bytes


@router.get("/{claim_id}/evidence/{evidence_id}/file")
def get_evidence_file(
    claim_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return an evidence image only to its owner or an administrator."""
    claim = db.get(Claim, claim_id)
    require_claim_access(claim, current_user)

    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.claim_id == claim_id
    ).first()

    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found.")

    file_path = Path(evidence.file_path).resolve()
    upload_root = settings.upload_dir.resolve()

    if upload_root not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Evidence file not found.")

    media_type = RESPONSE_MEDIA_TYPES.get(file_path.suffix.lower())
    if media_type is None:
        raise HTTPException(status_code=415, detail="Unsupported evidence file.")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=evidence.original_filename,
        content_disposition_type="inline"
    )


@router.post("/{claim_id}/upload/{evidence_type}")
def upload_evidence(
    claim_id: int,
    evidence_type: str,
    file: UploadFile = File(...),
    description: str = Form(""),
    source_type: str = Form("UNSPECIFIED"),
    captured_at: str = Form(""),
    location_label: str = Form(""),
    replace: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    allowed_types = {
        "invoice",
        "product",
        "damage"
    }

    if evidence_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid evidence type. Use invoice, product, or damage."
            )
        )

    claim = db.query(Claim).filter(
        Claim.id == claim_id
    ).first()

    require_claim_access(claim, current_user)

    if claim.status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail="Evidence cannot be changed after a claim is submitted."
        )

    existing_evidence = db.query(Evidence).filter(
        Evidence.claim_id == claim_id,
        Evidence.evidence_type == evidence_type
    ).first()

    if existing_evidence is not None and not replace:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{evidence_type.capitalize()} evidence has already been "
                "uploaded for this claim."
            )
        )

    original_filename = file.filename or ""
    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type."
        )

    content_type = (
        file.content_type or "application/octet-stream"
    ).lower()

    if content_type not in ALLOWED_CONTENT_TYPES[extension]:
        raise HTTPException(
            status_code=400,
            detail="The declared file type does not match the extension."
        )

    evidence_context = normalize_evidence_context(
        description=description,
        source_type=source_type,
        captured_at=captured_at,
        location_label=location_label
    )

    claim_directory = settings.upload_dir / f"claim_{claim_id}"
    claim_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    stored_filename = (
        f"{evidence_type}_{uuid4().hex}{extension}"
    )
    file_path = claim_directory / stored_filename
    temporary_path = claim_directory / (
        f".{stored_filename}.uploading"
    )
    old_file_path = Path(existing_evidence.file_path) if existing_evidence is not None else None

    try:
        file_size_bytes = save_upload_with_limit(
            upload_file=file,
            destination=temporary_path
        )
        image_width, image_height = validate_saved_file(
            file_path=temporary_path,
            extension=extension
        )

        temporary_path.replace(file_path)

        if existing_evidence is not None:
            evidence = existing_evidence
            evidence.original_filename = original_filename
            evidence.stored_filename = stored_filename
            evidence.file_path = str(file_path)
            evidence.file_size_bytes = file_size_bytes
            evidence.image_width = image_width
            evidence.image_height = image_height
            for field, value in evidence_context.items():
                setattr(evidence, field, value)
        else:
            evidence = Evidence(
                claim_id=claim_id,
                evidence_type=evidence_type,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=str(file_path),
                file_size_bytes=file_size_bytes,
                image_width=image_width,
                image_height=image_height,
                **evidence_context
            )

        db.add(evidence)
        db.commit()
        db.refresh(evidence)
        if old_file_path is not None:
            resolved_old_path = old_file_path.resolve()
            if settings.upload_dir.resolve() in resolved_old_path.parents:
                remove_file_if_present(resolved_old_path)

    except UploadValidationError as error:
        db.rollback()
        remove_file_if_present(temporary_path)
        remove_file_if_present(file_path)

        raise HTTPException(
            status_code=400,
            detail=str(error)
        ) from error

    except Exception as error:
        db.rollback()
        remove_file_if_present(temporary_path)
        remove_file_if_present(file_path)

        raise HTTPException(
            status_code=500,
            detail="Could not store the uploaded evidence."
        ) from error

    return {
        "message": "Evidence uploaded successfully",
        "evidence": {
            "id": evidence.id,
            "claim_id": evidence.claim_id,
            "type": evidence.evidence_type,
            "original_filename": evidence.original_filename,
            "description": evidence.description,
            "source_type": evidence.source_type,
            "captured_at": evidence.captured_at,
            "location_label": evidence.location_label,
            "file_size_bytes": evidence.file_size_bytes,
            "image_width": evidence.image_width,
            "image_height": evidence.image_height
        }
    }

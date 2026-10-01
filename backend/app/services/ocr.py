from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import easyocr
import numpy as np
import torch
from PIL import Image

from app.schemas.ocr import OCRPoint, OCRResult, OCRTextRegion


class OCRUnavailableError(RuntimeError):
    """Raised when the pretrained EasyOCR reader cannot be initialized."""


ReaderFactory = Callable[..., Any]


class OCRService:
    """Backend-only EasyOCR service with normalized engine output."""

    def __init__(
        self,
        model_storage_path: Path,
        download_enabled: bool,
        reader_factory: ReaderFactory = easyocr.Reader,
    ) -> None:
        self._model_storage_path = model_storage_path
        self._download_enabled = download_enabled
        self._reader_factory = reader_factory
        self._reader: Any | None = None

    @property
    def is_loaded(self) -> bool:
        return self._reader is not None

    def load(self) -> None:
        """Load the pretrained English reader without training or client-side execution."""
        if self._reader is not None:
            return
        try:
            self._model_storage_path.mkdir(parents=True, exist_ok=True)
            self._reader = self._reader_factory(
                ["en"],
                gpu=torch.cuda.is_available(),
                model_storage_directory=str(self._model_storage_path),
                download_enabled=self._download_enabled,
                verbose=False,
            )
        except Exception as error:
            self._reader = None
            raise OCRUnavailableError("OCR service is unavailable.") from error

    def extract(self, image: Image.Image) -> OCRResult:
        """Extract and normalize text regions from a decoded RGB image."""
        self.load()
        if self._reader is None:
            raise OCRUnavailableError("OCR service is unavailable.")
        raw_regions = self._reader.readtext(
            np.asarray(image.convert("RGB")),
            detail=1,
            paragraph=False,
        )
        return OCRResult(regions=[self._normalize_region(region) for region in raw_regions])

    @staticmethod
    def _normalize_region(region: Sequence[Any]) -> OCRTextRegion:
        if len(region) != 3:
            raise OCRUnavailableError("OCR service returned an invalid response.")
        raw_box, text, confidence = region
        if len(raw_box) != 4:
            raise OCRUnavailableError("OCR service returned an invalid response.")
        points = tuple(OCRPoint(x=float(point[0]), y=float(point[1])) for point in raw_box)
        return OCRTextRegion(
            text=str(text),
            confidence=float(confidence),
            bounding_box=points,
        )

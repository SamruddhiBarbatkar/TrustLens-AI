from pathlib import Path

import pytest
from PIL import Image

from app.services.ocr import OCRService, OCRUnavailableError


class EmptyReader:
    def readtext(self, _image: object, **_options: object) -> list[object]:
        return []


def test_ocr_normalizes_an_empty_engine_response_without_fabricating_text(tmp_path: Path) -> None:
    service = OCRService(
        tmp_path / "models",
        download_enabled=False,
        reader_factory=lambda *_args, **_kwargs: EmptyReader(),
    )

    result = service.extract(Image.new("RGB", (1, 1)))

    assert service.is_loaded is True
    assert result.regions == []


def test_unavailable_pretrained_reader_returns_controlled_error(tmp_path: Path) -> None:
    def failing_reader(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("pretrained files are unavailable")

    service = OCRService(tmp_path / "models", download_enabled=False, reader_factory=failing_reader)

    with pytest.raises(OCRUnavailableError, match="OCR service is unavailable"):
        service.load()


def test_real_reader_reports_unavailable_when_weights_are_not_provisioned(
    tmp_path: Path,
) -> None:
    service = OCRService(tmp_path / "missing-weights", download_enabled=False)

    with pytest.raises(OCRUnavailableError, match="OCR service is unavailable"):
        service.load()

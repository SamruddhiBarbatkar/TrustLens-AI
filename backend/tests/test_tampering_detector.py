from pathlib import Path

import pytest
import torch

from app.services.tampering_detector import (
    TamperingDetector,
    TamperingModelUnavailableError,
)


def test_verified_checkpoint_loads_strictly_without_mutating_it() -> None:
    checkpoint_path = Path(__file__).resolve().parents[2] / "models" / "best_model.pth"
    detector = TamperingDetector(checkpoint_path, device=torch.device("cpu"))

    detector.load()

    assert detector.is_loaded is True
    assert detector.device.type == "cpu"


def test_missing_checkpoint_returns_controlled_unavailable_error(tmp_path: Path) -> None:
    detector = TamperingDetector(tmp_path / "missing-model.pth", device=torch.device("cpu"))

    with pytest.raises(TamperingModelUnavailableError, match="Tampering model is unavailable"):
        detector.load()

from pathlib import Path

import pytest
import torch

from app.services.ai_detector import AIDetectorModelUnavailableError, AIGenerationDetector


def test_verified_checkpoint_loads_strictly_without_mutating_it() -> None:
    checkpoint_path = Path(__file__).resolve().parents[2] / "models" / "ai_detector_best.pth"
    detector = AIGenerationDetector(checkpoint_path, device=torch.device("cpu"))

    detector.load()

    assert detector.is_loaded is True
    assert detector.device.type == "cpu"
    assert detector.class_labels == ("fake", "real")


def test_missing_checkpoint_returns_controlled_unavailable_error(tmp_path: Path) -> None:
    detector = AIGenerationDetector(tmp_path / "missing-model.pth", device=torch.device("cpu"))

    with pytest.raises(AIDetectorModelUnavailableError, match="AI image detector is unavailable"):
        detector.load()

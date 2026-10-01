from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torchvision import models, transforms

from app.schemas.ai_detection import AIGenerationPrediction
from app.services.gradcam import GradCAMError, image_data_url, render_gradcam


class AIDetectorModelUnavailableError(RuntimeError):
    """Raised when the verified AI-image checkpoint cannot be used."""


class AIGenerationDetector:
    """Backend-only EfficientNet-B0 AI-image inference service.

    Contract verified from ``ai_detector_training.ipynb``: EfficientNet-B0 with
    a two-output ``classifier[1]`` layer, a direct model ``state_dict``, and
    class mapping ``FAKE: 0`` / ``REAL: 1``. The inference transform exactly
    mirrors the notebook's ``eval_transform`` and ``predict_image`` routine.
    """

    class_labels = ("fake", "real")
    transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    def __init__(self, model_path: Path, device: torch.device | None = None) -> None:
        self._model_path = model_path
        self._device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model: nn.Module | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> torch.device:
        return self._device

    def load(self) -> None:
        """Strictly load the supplied state dict without changing checkpoint weights."""
        if self._model is not None:
            return
        if not self._model_path.is_file():
            raise AIDetectorModelUnavailableError("AI image detector is unavailable.")

        model = models.efficientnet_b0(weights=None)
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, 2)
        try:
            state_dict = torch.load(
                self._model_path,
                map_location=self._device,
                weights_only=True,
            )
            model.load_state_dict(state_dict, strict=True)
        except (OSError, RuntimeError, ValueError) as error:
            raise AIDetectorModelUnavailableError("AI image detector is unavailable.") from error

        self._model = model.to(self._device)
        self._model.eval()

    def predict(self, image: Image.Image) -> AIGenerationPrediction:
        """Run deterministic evaluation preprocessing and inference on a decoded RGB image."""
        self.load()
        if self._model is None:
            raise AIDetectorModelUnavailableError("AI image detector is unavailable.")

        tensor = self.transform(image.convert("RGB")).unsqueeze(0).to(self._device)
        try:
            logits, heatmap = render_gradcam(self._model, self._model.features[-1], tensor, image)
            gradcam_data_url = image_data_url(heatmap)
        except GradCAMError:
            with torch.inference_mode():
                logits = self._model(tensor)
            gradcam_data_url = None
        probabilities = torch.softmax(logits, dim=1)[0]
        class_index = int(torch.argmax(probabilities).item())

        return AIGenerationPrediction(
            class_index=class_index,
            label=self.class_labels[class_index],
            top_class_softmax_score=float(probabilities[class_index].item()),
            preprocessing_note=(
                "Uses the training notebook's evaluation transform: resize to 224x224, "
                "tensor conversion, and ImageNet mean/std normalization."
            ),
            gradcam_data_url=gradcam_data_url,
        )

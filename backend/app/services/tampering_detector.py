from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torchvision import models, transforms

from app.schemas.tampering import TamperingPrediction
from app.services.gradcam import GradCAMError, image_data_url, render_gradcam


class TamperingModelUnavailableError(RuntimeError):
    """Raised when the verified tampering checkpoint cannot be used."""


class TamperingDetector:
    """Backend-only ResNet18 visual-tampering inference service.

    Contract verified from ``tampering_training.ipynb``:
    ResNet18 with a two-output ``fc`` layer; class index 0 is ``Authentic`` and
    index 1 is ``Tampered``. The saved file is a direct model ``state_dict``.
    The notebook's only documented transform is intentionally preserved here,
    including random flip/rotation; no unverified normalization or deterministic
    inference transform is substituted.
    """

    class_labels = ("authentic", "tampered")
    transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(10),
            transforms.ToTensor(),
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
        """Strictly load the supplied state dict without altering checkpoint weights."""
        if self._model is not None:
            return
        if not self._model_path.is_file():
            raise TamperingModelUnavailableError("Tampering model is unavailable.")

        model = models.resnet18(weights=None)
        model.fc = nn.Linear(model.fc.in_features, 2)
        try:
            state_dict = torch.load(
                self._model_path,
                map_location=self._device,
                weights_only=True,
            )
            model.load_state_dict(state_dict, strict=True)
        except (OSError, RuntimeError, ValueError) as error:
            raise TamperingModelUnavailableError("Tampering model is unavailable.") from error

        self._model = model.to(self._device)
        self._model.eval()

    def predict(self, image: Image.Image) -> TamperingPrediction:
        """Run the verified model in inference mode on a decoded RGB image."""
        self.load()
        if self._model is None:
            raise TamperingModelUnavailableError("Tampering model is unavailable.")

        tensor = self.transform(image.convert("RGB")).unsqueeze(0).to(self._device)
        try:
            logits, heatmap = render_gradcam(self._model, self._model.layer4[-1], tensor, image)
            gradcam_data_url = image_data_url(heatmap)
        except GradCAMError:
            with torch.inference_mode():
                logits = self._model(tensor)
            gradcam_data_url = None
        probabilities = torch.softmax(logits, dim=1)[0]
        class_index = int(torch.argmax(probabilities).item())

        return TamperingPrediction(
            class_index=class_index,
            label=self.class_labels[class_index],
            top_class_softmax_score=float(probabilities[class_index].item()),
            preprocessing_note=(
                "Uses the training notebook's documented resize, random horizontal flip, "
                "random rotation, and tensor conversion transform. The notebook did not "
                "provide a separate deterministic inference transform."
            ),
            gradcam_data_url=gradcam_data_url,
        )

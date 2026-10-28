"""Three-class image authenticity candidate for TrustLens.

This model distinguishes natural authentic images, locally tampered images,
and fully synthetic images. Its two suspicious-class probabilities can still
be calibrated and fused as separate detector signals under the existing
TrustLens methodology.
"""

from pathlib import Path
import hashlib

import torch
from PIL import Image
from torchvision import models, transforms

from app.ml.image_views import (
    DEFAULT_PATCH_FRACTION,
    build_global_and_patch_views,
    mean_probabilities,
    summarize_regional_signals,
)


IMAGE_SIZE = 224
CLASS_NAMES = {
    0: "AUTHENTIC",
    1: "TAMPERED",
    2: "SYNTHETIC",
}


class EvidenceAuthenticityModel:
    def __init__(self, model_path):
        self.model_path = Path(model_path)
        self.model_version = (
            "evidence-authenticity-v2-forensic-candidate"
            if "forensic_multiview" in self.model_path.stem
            else "evidence-authenticity-v1-three-class-candidate"
        )
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.model = models.efficientnet_b0(weights=None)
        self.model.classifier[1] = torch.nn.Linear(
            self.model.classifier[1].in_features,
            len(CLASS_NAMES),
        )

        if not self.model_path.exists():
            raise FileNotFoundError(
                "Three-class authenticity checkpoint not found: "
                f"{self.model_path}"
            )
        if not self.model_path.is_file():
            raise RuntimeError(
                "Three-class authenticity checkpoint path is not a file: "
                f"{self.model_path}"
            )

        self.checkpoint_sha256 = hashlib.sha256(
            self.model_path.read_bytes()
        ).hexdigest()

        checkpoint = torch.load(
            self.model_path,
            map_location=self.device,
            weights_only=True,
        )
        self.model.load_state_dict(checkpoint)
        self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.Resize(
                (IMAGE_SIZE, IMAGE_SIZE),
                interpolation=transforms.InterpolationMode.BICUBIC,
            ),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

    def _predict_images(self, images):
        tensors = torch.stack([self.transform(image) for image in images]).to(
            self.device
        )
        with torch.no_grad():
            logits = self.model(tensors)
            probabilities = torch.softmax(logits, dim=1)
        return probabilities.cpu().tolist()

    def _format_prediction(self, probabilities, *, model_version=None, **extra):
        predicted_index = max(
            range(len(probabilities)),
            key=probabilities.__getitem__,
        )

        return {
            "prediction": CLASS_NAMES[predicted_index],
            "predicted_class_index": predicted_index,
            "authentic_probability": round(float(probabilities[0]), 6),
            "tampered_probability": round(float(probabilities[1]), 6),
            "ai_generated_probability": round(float(probabilities[2]), 6),
            "confidence": round(float(probabilities[predicted_index]), 6),
            "model_name": "EfficientNet-B0",
            "model_version": model_version or self.model_version,
            "checkpoint": self.model_path.name,
            "model_sha256": self.checkpoint_sha256,
            "classes": CLASS_NAMES,
            "model_available": True,
            "device": str(self.device),
            **extra,
        }

    def predict(self, image_path):
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        probabilities = self._predict_images([image])[0]
        return self._format_prediction(
            probabilities,
            inference_strategy="GLOBAL_RESIZE",
            view_count=1,
        )

    def predict_multiview(
        self,
        image_path,
        patch_fraction=DEFAULT_PATCH_FRACTION,
    ):
        """Evaluate deterministic global and local views as a new candidate.

        The distinct model version is important: inference preprocessing is
        part of a calibrated detector, even when checkpoint weights are the
        same.  This candidate therefore cannot accidentally match the active
        single-view calibration artifact.
        """

        with Image.open(image_path) as source:
            views = build_global_and_patch_views(
                source,
                patch_fraction=patch_fraction,
            )
        rows = self._predict_images([view.image for view in views])
        probabilities = mean_probabilities(rows)
        view_predictions = []
        for view, row in zip(views, rows):
            predicted_index = max(range(len(row)), key=row.__getitem__)
            view_predictions.append({
                "view": view.name,
                "prediction": CLASS_NAMES[predicted_index],
                "authentic_probability": round(float(row[0]), 6),
                "tampered_probability": round(float(row[1]), 6),
                "ai_generated_probability": round(float(row[2]), 6),
            })
        return self._format_prediction(
            probabilities,
            model_version=f"{self.model_version}-multiview-v1",
            inference_strategy="GLOBAL_PLUS_FIVE_PATCHES_MEAN_V1",
            aggregation="ARITHMETIC_MEAN",
            patch_fraction=patch_fraction,
            view_count=len(views),
            view_predictions=view_predictions,
            regional_explanation=summarize_regional_signals(
                [view.name for view in views],
                rows,
            ),
        )

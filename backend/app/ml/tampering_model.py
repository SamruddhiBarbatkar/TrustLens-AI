from pathlib import Path
import hashlib

import torch
from PIL import Image
from torchvision import models, transforms


MODEL_PATH = (
    Path(__file__).resolve().parent
    / "tampering_model.pth"
)

IMAGE_SIZE = 224

CLASS_NAMES = {
    0: "AUTHENTIC",
    1: "TAMPERED",
}


class TamperingDetectionModel:

    def __init__(self, model_path=MODEL_PATH):

        self.model_path = Path(model_path)
        self.model_version = (
            "tampering-v1-casia2"
            if self.model_path.resolve() == MODEL_PATH.resolve()
            else "tampering-v2-multisource-hardnegative-candidate"
        )

        self.device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        self.model = models.resnet18(
            weights=None
        )

        self.model.fc = torch.nn.Linear(
            self.model.fc.in_features,
            2
        )

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Tampering model checkpoint not found: "
                f"{self.model_path}"
            )

        if not self.model_path.is_file():
            raise RuntimeError(
                f"Tampering model path is not a file: "
                f"{self.model_path}"
            )

        self.checkpoint_sha256 = hashlib.sha256(
            self.model_path.read_bytes()
        ).hexdigest()

        checkpoint = torch.load(
            self.model_path,
            map_location=self.device,
            weights_only=True
        )

        self.model.load_state_dict(checkpoint)

        self.model.to(self.device)
        self.model.eval()

        # The legacy CASIA2 checkpoint was trained without ImageNet
        # normalization. Multi-source candidates use ImageNet initialization
        # and therefore require the matching normalization at inference.
        transform_steps = [
            transforms.Resize(
                (IMAGE_SIZE, IMAGE_SIZE)
            ),
            transforms.ToTensor(),
        ]
        if self.model_version != "tampering-v1-casia2":
            transform_steps.append(transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ))
        self.transform = transforms.Compose(transform_steps)

    def predict(self, image_path):

        image = Image.open(
            image_path
        ).convert("RGB")

        tensor = (
            self.transform(image)
            .unsqueeze(0)
            .to(self.device)
        )

        with torch.no_grad():

            logits = self.model(tensor)

            probabilities = torch.softmax(
                logits,
                dim=1
            )[0]

        predicted_index = int(
            torch.argmax(
                probabilities
            ).item()
        )

        authentic_probability = float(
            probabilities[0].item()
        )

        tampered_probability = float(
            probabilities[1].item()
        )

        prediction = CLASS_NAMES[
            predicted_index
        ]

        confidence = float(
            probabilities[predicted_index].item()
        )

        return {
            "prediction": prediction,
            "predicted_class_index": predicted_index,
            "authentic_probability": round(
                authentic_probability,
                6
            ),
            "tampered_probability": round(
                tampered_probability,
                6
            ),
            "confidence": round(
                confidence,
                6
            ),
            "model_name": "ResNet-18",
            "model_version": self.model_version,
            "checkpoint": self.model_path.name,
            "model_sha256": self.checkpoint_sha256,
            "dataset": (
                "CASIA2"
                if self.model_version == "tampering-v1-casia2"
                else "Tampered-Images-Combined-Dataset"
            ),
            "model_available": True,
            "device": str(self.device)
        }


_model = None


def get_tampering_model():

    global _model

    if _model is None:
        _model = TamperingDetectionModel()

    return _model

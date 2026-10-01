import numpy as np
from PIL import Image

from app.schemas.quality import ImageQualityResult


class ImageQualityService:
    """Measure deterministic image properties without inferring authenticity."""

    limitations = (
        "Brightness, contrast, and sharpness are image properties, not proof of authenticity or manipulation.",
        "Compression, resizing, noise reduction, focus, and source-device processing can change these measurements.",
    )

    def analyze(self, image: Image.Image) -> ImageQualityResult:
        grayscale = np.asarray(image.convert("L"), dtype=np.float64)
        height, width = grayscale.shape
        laplacian = (
            -4 * grayscale[1:-1, 1:-1]
            + grayscale[:-2, 1:-1]
            + grayscale[2:, 1:-1]
            + grayscale[1:-1, :-2]
            + grayscale[1:-1, 2:]
        )
        sharpness = float(laplacian.var()) if laplacian.size else 0.0

        return ImageQualityResult(
            width=int(width),
            height=int(height),
            brightness_mean=float(grayscale.mean()),
            contrast_standard_deviation=float(grayscale.std()),
            sharpness_laplacian_variance=sharpness,
            method=(
                "Converted the decoded image to grayscale, then measured mean brightness, "
                "pixel-value standard deviation, and variance of a 4-neighbour discrete Laplacian."
            ),
            limitations=self.limitations,
        )

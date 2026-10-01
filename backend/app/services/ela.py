from io import BytesIO

import numpy as np
from PIL import Image

from app.schemas.ela import ELAResult


class ELAService:
    """Measure Error Level Analysis differences for a decoded image.

    ELA compares an image to a JPEG recompression. It is a compression signal,
    not proof that any content was edited, generated, or authentic.
    """

    recompression_quality = 90
    limitations = (
        "ELA measures JPEG recompression differences, not image authenticity or intent.",
        "Prior compression, resizing, editing history, and source format can change ELA values.",
        "Uniform or low-detail regions can naturally differ from textured regions after JPEG encoding.",
    )

    def analyze(self, image: Image.Image) -> ELAResult:
        """Return deterministic per-pixel differences after a controlled JPEG recompression."""
        original = image.convert("RGB")
        buffer = BytesIO()
        original.save(
            buffer,
            format="JPEG",
            quality=self.recompression_quality,
            subsampling=0,
            optimize=False,
        )
        buffer.seek(0)
        with Image.open(buffer) as recompressed:
            recompressed_rgb = recompressed.convert("RGB")
            original_pixels = np.asarray(original, dtype=np.int16)
            recompressed_pixels = np.asarray(recompressed_rgb, dtype=np.int16)

        difference = np.abs(original_pixels - recompressed_pixels)
        pixel_difference = np.any(difference > 0, axis=2)
        squared_difference = difference.astype(np.float64) ** 2

        return ELAResult(
            recompression_quality=self.recompression_quality,
            mean_absolute_difference=float(difference.mean()),
            root_mean_square_difference=float(np.sqrt(squared_difference.mean())),
            max_channel_difference=int(difference.max()),
            differing_pixel_fraction=float(pixel_difference.mean()),
            method=(
                "Converted the decoded image to RGB, recompressed it as JPEG at quality 90 "
                "with 4:4:4 chroma sampling, then measured absolute per-channel differences."
            ),
            limitations=self.limitations,
        )

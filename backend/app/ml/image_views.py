"""Deterministic image views used by research candidate inference.

The deployed TrustLens detector sees one globally resized image.  Local edits
can become very small after that resize, so the candidate path also evaluates
five overlapping square crops.  View creation is deliberately free of random
state so calibration observations can be reproduced exactly.
"""

from dataclasses import dataclass

from PIL import Image


DEFAULT_PATCH_FRACTION = 0.68
MINIMUM_PATCH_FRACTION = 0.50
MAXIMUM_PATCH_FRACTION = 0.90


@dataclass(frozen=True)
class ImageView:
    name: str
    image: Image.Image


def build_global_and_patch_views(
    image: Image.Image,
    patch_fraction: float = DEFAULT_PATCH_FRACTION,
) -> list[ImageView]:
    """Return the full image plus four corners and a center square crop."""

    if not MINIMUM_PATCH_FRACTION <= patch_fraction <= MAXIMUM_PATCH_FRACTION:
        raise ValueError(
            "patch_fraction must be between "
            f"{MINIMUM_PATCH_FRACTION:.2f} and {MAXIMUM_PATCH_FRACTION:.2f}."
        )

    rgb = image.convert("RGB")
    width, height = rgb.size
    if width < 2 or height < 2:
        raise ValueError("Image is too small for multi-view inference.")

    side = max(1, round(min(width, height) * patch_fraction))
    max_left = width - side
    max_top = height - side
    center_left = max_left // 2
    center_top = max_top // 2
    boxes = [
        ("top_left", 0, 0),
        ("top_right", max_left, 0),
        ("bottom_left", 0, max_top),
        ("bottom_right", max_left, max_top),
        ("center", center_left, center_top),
    ]

    views = [ImageView("global", rgb.copy())]
    for name, left, top in boxes:
        views.append(
            ImageView(
                name,
                rgb.crop((left, top, left + side, top + side)),
            )
        )
    return views


def mean_probabilities(rows: list[list[float]]) -> list[float]:
    """Average equally weighted class-probability rows."""

    if not rows:
        raise ValueError("At least one probability row is required.")
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError("Probability rows must have the same non-zero width.")

    means = [sum(row[index] for row in rows) / len(rows) for index in range(width)]
    total = sum(means)
    if total <= 0:
        raise ValueError("Probability rows must have a positive total.")
    return [value / total for value in means]


def summarize_regional_signals(
    view_names: list[str],
    probability_rows: list[list[float]],
    tampered_class_index: int = 1,
) -> dict:
    """Describe patch variation without claiming pixel-level localization."""

    if len(view_names) != len(probability_rows):
        raise ValueError("Every probability row must have a matching view name.")
    patches = [
        (name, float(row[tampered_class_index]))
        for name, row in zip(view_names, probability_rows)
        if name != "global"
    ]
    if not patches:
        raise ValueError("At least one regional patch view is required.")

    highest_name, highest_probability = max(patches, key=lambda item: item[1])
    lowest_probability = min(probability for _, probability in patches)
    return {
        "highest_signal_view": highest_name,
        "highest_tampering_probability": round(highest_probability, 6),
        "regional_signal_spread": round(
            highest_probability - lowest_probability,
            6,
        ),
        "patch_count": len(patches),
        "signal_type": "RAW_UNCALIBRATED_VIEW_PROBABILITY",
        "localization_scope": "COARSE_REGIONAL_VIEW",
        "limitation": (
            "Regional signals explain which model crop was most suspicious; "
            "they are not a pixel-level tampering mask or independent verdict."
        ),
    }

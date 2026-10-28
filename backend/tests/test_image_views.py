import sys
import unittest
from pathlib import Path

from PIL import Image


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ml.image_views import (
    build_global_and_patch_views,
    mean_probabilities,
    summarize_regional_signals,
)


class ImageViewTests(unittest.TestCase):
    def test_global_and_patch_views_are_deterministic(self):
        image = Image.new("RGB", (1000, 600), color=(12, 34, 56))

        views = build_global_and_patch_views(image, patch_fraction=0.5)

        self.assertEqual(
            [view.name for view in views],
            [
                "global",
                "top_left",
                "top_right",
                "bottom_left",
                "bottom_right",
                "center",
            ],
        )
        self.assertEqual(views[0].image.size, (1000, 600))
        self.assertTrue(all(view.image.size == (300, 300) for view in views[1:]))

    def test_patch_fraction_is_bounded(self):
        image = Image.new("RGB", (100, 100))

        with self.assertRaises(ValueError):
            build_global_and_patch_views(image, patch_fraction=0.2)

    def test_probability_rows_are_averaged_and_normalized(self):
        result = mean_probabilities([
            [0.6, 0.3, 0.1],
            [0.3, 0.3, 0.4],
        ])

        self.assertAlmostEqual(sum(result), 1.0)
        self.assertAlmostEqual(result[0], 0.45)
        self.assertAlmostEqual(result[1], 0.30)
        self.assertAlmostEqual(result[2], 0.25)

    def test_regional_summary_ignores_global_view(self):
        result = summarize_regional_signals(
            ["global", "top_left", "top_right", "center"],
            [
                [0.05, 0.90, 0.05],
                [0.50, 0.30, 0.20],
                [0.10, 0.75, 0.15],
                [0.40, 0.45, 0.15],
            ],
        )

        self.assertEqual(result["highest_signal_view"], "top_right")
        self.assertEqual(result["highest_tampering_probability"], 0.75)
        self.assertEqual(result["regional_signal_spread"], 0.45)
        self.assertEqual(result["patch_count"], 3)
        self.assertEqual(
            result["localization_scope"],
            "COARSE_REGIONAL_VIEW",
        )


if __name__ == "__main__":
    unittest.main()

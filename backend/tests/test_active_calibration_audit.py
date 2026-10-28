import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.audit_active_calibration import rate_record, wilson_interval
from scripts.calibrate_fusion import build_validation_scores


class ActiveCalibrationAuditTests(unittest.TestCase):
    def test_wilson_interval_reports_uncertainty_around_a_rate(self):
        interval = wilson_interval(3, 60)
        self.assertAlmostEqual(interval[0], 0.01715, places=5)
        self.assertAlmostEqual(interval[1], 0.137005, places=5)
        self.assertEqual(rate_record(3, 60)["rate"], 0.05)

    def test_heldout_scoring_does_not_reuse_validation_samples(self):
        rows = []
        for split, sample_id, label, probability in (
            ("validation", "validation-only", 0, 0.1),
            ("test", "test-only", 1, 0.9),
        ):
            for detector in ("AI_GENERATION", "TAMPERING_DETECTION"):
                rows.append({
                    "detector": detector,
                    "sample_id": sample_id,
                    "split": split,
                    "claim_label": label,
                    "raw_probability": probability,
                    "quality_status": "GOOD",
                })
        policies = {
            detector: {
                "temperature": 1.0,
                "reliability_by_quality": {"GOOD": 0.7, "OVERALL": 0.7},
            }
            for detector in ("AI_GENERATION", "TAMPERING_DETECTION")
        }

        validation = build_validation_scores(rows, policies)
        heldout = build_validation_scores(rows, policies, split="test")

        self.assertEqual([item["sample_id"] for item in validation], ["validation-only"])
        self.assertEqual([item["sample_id"] for item in heldout], ["test-only"])
        self.assertIn("uncertainty", heldout[0])
        self.assertIn("conflict", heldout[0])


if __name__ == "__main__":
    unittest.main()

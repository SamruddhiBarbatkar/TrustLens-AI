import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.analysis.calibration_training import (
    assess_detector_readiness,
    binary_log_loss,
    calibration_metrics,
    fit_temperature,
    select_operational_thresholds,
    validate_partitions,
)


def row(sample_id, group_id, split, label, probability):
    return {
        "detector": "TAMPERING_DETECTION",
        "sample_id": sample_id,
        "group_id": group_id,
        "split": split,
        "label": label,
        "raw_probability": probability,
        "quality_status": "GOOD",
    }


class CalibrationTrainingTests(unittest.TestCase):
    def test_temperature_fit_does_not_worsen_calibration_log_loss(self):
        observations = [
            row("a", "ga", "calibration", 0, 0.30),
            row("b", "gb", "calibration", 0, 0.40),
            row("c", "gc", "calibration", 1, 0.60),
            row("d", "gd", "calibration", 1, 0.70),
        ]
        temperature = fit_temperature(observations)
        self.assertLessEqual(
            binary_log_loss(observations, temperature),
            binary_log_loss(observations, 1.0) + 1e-8,
        )
        metrics = calibration_metrics(observations, temperature)
        self.assertIn("brier_score", metrics)
        self.assertIn("expected_calibration_error", metrics)
        self.assertIn("auroc", metrics)
        self.assertIn("average_precision", metrics)
        self.assertTrue(metrics["reliability_bins"])

    def test_partition_leakage_is_rejected(self):
        observations = [
            row("same", "group", "calibration", 0, 0.2),
            row("same", "group", "validation", 0, 0.3),
        ]
        with self.assertRaisesRegex(ValueError, "Partition leakage"):
            validate_partitions(observations)

    def test_thresholds_obey_operational_constraints(self):
        scored = [
            {"label": 0, "trust_score": 95.0},
            {"label": 0, "trust_score": 90.0},
            {"label": 1, "trust_score": 25.0},
            {"label": 1, "trust_score": 10.0},
        ]
        thresholds = select_operational_thresholds(
            scored,
            maximum_false_acceptance_rate=0.0,
            maximum_false_rejection_rate=0.0,
        )
        self.assertEqual(thresholds["observed_false_acceptance_rate"], 0.0)
        self.assertEqual(thresholds["observed_false_rejection_rate"], 0.0)
        self.assertLess(thresholds["reject"], thresholds["approve"])

    def test_detector_readiness_rejects_weak_test_metrics(self):
        policies = {
            "AI_GENERATION": {
                "metrics": {
                    "test": {
                        "calibrated": {
                            "auroc": 0.40,
                            "expected_calibration_error": 0.30,
                        }
                    }
                },
                "reliability_by_quality": {"OVERALL": 0.10},
            },
            "TAMPERING_DETECTION": {
                "metrics": {
                    "test": {
                        "calibrated": {
                            "auroc": 0.85,
                            "expected_calibration_error": 0.08,
                        }
                    }
                },
                "reliability_by_quality": {"OVERALL": 0.70},
            },
        }
        assessment = assess_detector_readiness(policies)
        self.assertFalse(assessment["ready"])
        self.assertFalse(assessment["detectors"]["AI_GENERATION"]["passed"])
        self.assertTrue(
            assessment["detectors"]["TAMPERING_DETECTION"]["passed"]
        )


if __name__ == "__main__":
    unittest.main()

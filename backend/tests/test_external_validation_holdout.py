import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.compare_external_candidates import compare
from scripts.evaluate_external_validation import evaluate


class ExternalValidationHoldoutTests(unittest.TestCase):
    def test_test_predictions_are_rejected_from_validation_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "active.json"
            manifest = root / "manifest.csv"
            metadata = root / "metadata.json"
            observations = root / "observations.csv"
            artifact.write_text(json.dumps({
                "validation_assessment": {"requirements": {
                    "minimum_test_auroc": 0.7,
                    "maximum_test_ece": 0.15,
                    "minimum_reliability": 0.2,
                }},
            }), encoding="utf-8")
            metadata.write_text("{}", encoding="utf-8")
            with manifest.open("w", encoding="utf-8", newline="") as destination:
                writer = csv.DictWriter(destination, fieldnames=["sample_id", "split"])
                writer.writeheader()
                writer.writerows([
                    {"sample_id": "v1", "split": "validation"},
                    {"sample_id": "t1", "split": "test"},
                ])
            with observations.open("w", encoding="utf-8", newline="") as destination:
                writer = csv.DictWriter(destination, fieldnames=[
                    "detector", "sample_id", "group_id", "split", "detector_label",
                    "claim_label", "raw_probability", "quality_status",
                ])
                writer.writeheader()
                for split, sample_id in (("validation", "v1"), ("test", "t1")):
                    for detector in ("AI_GENERATION", "TAMPERING_DETECTION"):
                        writer.writerow({
                            "detector": detector, "sample_id": sample_id,
                            "group_id": sample_id, "split": split,
                            "detector_label": 0, "claim_label": 0,
                            "raw_probability": 0.1, "quality_status": "GOOD",
                        })
            with self.assertRaisesRegex(ValueError, "Only validation observations"):
                evaluate(artifact, observations, manifest, metadata)
            with self.assertRaisesRegex(ValueError, "non-validation predictions"):
                compare({"candidate": observations})


if __name__ == "__main__":
    unittest.main()

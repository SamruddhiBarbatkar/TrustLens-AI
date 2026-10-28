import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.analysis.tampering_multiview import analyze_tampering_multiview


class MultiviewCandidateTests(unittest.TestCase):
    def test_disabled_candidate_is_explicitly_excluded(self):
        evidence = SimpleNamespace(id=11, file_path="unused.jpg")
        with patch(
            "app.analysis.tampering_multiview.multiview_candidate_enabled",
            return_value=False,
        ):
            output = analyze_tampering_multiview(evidence)

        self.assertEqual(output["status"], "SKIPPED")
        self.assertTrue(output["result"]["excluded_from_trust_score"])

    def test_completed_candidate_is_explicitly_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "evidence.jpg"
            image.write_bytes(b"test")
            model = Mock()
            model.predict_multiview.return_value = {
                "prediction": "TAMPERED",
                "tampered_probability": 0.8,
                "authentic_probability": 0.1,
                "ai_generated_probability": 0.1,
                "model_available": True,
                "model_version": "multiview-test",
            }
            evidence = SimpleNamespace(id=12, file_path=str(image))
            with (
                patch(
                    "app.analysis.tampering_multiview.multiview_candidate_enabled",
                    return_value=True,
                ),
                patch(
                    "app.analysis.tampering_multiview.get_multiview_candidate_model",
                    return_value=model,
                ),
            ):
                output = analyze_tampering_multiview(evidence)

        self.assertEqual(output["status"], "COMPLETED")
        self.assertEqual(
            output["analysis_type"],
            "TAMPERING_MULTIVIEW_CANDIDATE",
        )
        self.assertEqual(
            output["result"]["decision_role"],
            "RESEARCH_CANDIDATE_ONLY",
        )
        self.assertTrue(output["result"]["excluded_from_trust_score"])


if __name__ == "__main__":
    unittest.main()

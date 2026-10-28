import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.analysis.tampering_shadow import analyze_tampering_resnet_shadow
from app.analysis.tampering import analyze_tampering
from app.core.config import settings
from app.ml import model_registry


class ModelRegistryTests(unittest.TestCase):
    def setUp(self):
        self.original_mode = settings.detector_policy_mode
        self.original_shadow = settings.enable_resnet_shadow
        self.original_multiview_enabled = settings.enable_multiview_candidate
        self.original_ai_path = settings.ai_generation_candidate_path
        self.original_authenticity_path = (
            settings.evidence_authenticity_candidate_path
        )
        self.original_multiview_path = settings.multiview_candidate_path
        model_registry.clear_model_cache()

    def tearDown(self):
        settings.detector_policy_mode = self.original_mode
        settings.enable_resnet_shadow = self.original_shadow
        settings.enable_multiview_candidate = self.original_multiview_enabled
        settings.ai_generation_candidate_path = self.original_ai_path
        settings.evidence_authenticity_candidate_path = (
            self.original_authenticity_path
        )
        settings.multiview_candidate_path = self.original_multiview_path
        model_registry.clear_model_cache()

    def test_hybrid_routes_primary_branches_to_expected_architectures(self):
        settings.detector_policy_mode = model_registry.HYBRID_V1_MODE
        settings.ai_generation_candidate_path = Path("training_outputs/ai.pth")
        settings.evidence_authenticity_candidate_path = Path(
            "training_outputs/authenticity.pth"
        )
        ai = object()
        authenticity = object()

        with (
            patch.object(model_registry, "_ai_model", return_value=ai) as ai_factory,
            patch.object(
                model_registry,
                "_authenticity_model",
                return_value=authenticity,
            ) as authenticity_factory,
        ):
            self.assertIs(model_registry.get_primary_ai_generation_model(), ai)
            self.assertIs(model_registry.get_primary_tampering_model(), authenticity)

        ai_factory.assert_called_once_with(
            (BACKEND_DIR / "training_outputs/ai.pth").resolve()
        )
        authenticity_factory.assert_called_once_with(
            (BACKEND_DIR / "training_outputs/authenticity.pth").resolve()
        )

    def test_resnet_shadow_is_disabled_outside_hybrid_mode(self):
        settings.detector_policy_mode = model_registry.LEGACY_MODE
        settings.enable_resnet_shadow = True

        self.assertFalse(model_registry.resnet_shadow_enabled())
        self.assertIsNone(model_registry.get_resnet_shadow_model())

    def test_hybrid_v2_promotes_multiview_checkpoint_to_primary(self):
        settings.detector_policy_mode = model_registry.HYBRID_V2_MODE
        settings.multiview_candidate_path = Path(
            "training_outputs/forensic-multiview.pth"
        )
        candidate = object()

        with patch.object(
            model_registry,
            "_authenticity_model",
            return_value=candidate,
        ) as factory:
            self.assertIs(model_registry.get_primary_tampering_model(), candidate)

        factory.assert_called_once_with(
            (BACKEND_DIR / "training_outputs/forensic-multiview.pth").resolve()
        )
        self.assertTrue(model_registry.primary_tampering_uses_multiview())
        self.assertFalse(model_registry.multiview_candidate_enabled())

    def test_multiview_candidate_uses_its_separate_checkpoint(self):
        settings.detector_policy_mode = model_registry.HYBRID_V1_MODE
        settings.enable_multiview_candidate = True
        settings.multiview_candidate_path = Path(
            "training_outputs/forensic-multiview.pth"
        )
        candidate = object()

        with patch.object(
            model_registry,
            "_authenticity_model",
            return_value=candidate,
        ) as factory:
            self.assertIs(
                model_registry.get_multiview_candidate_model(),
                candidate,
            )

        factory.assert_called_once_with(
            (BACKEND_DIR / "training_outputs/forensic-multiview.pth").resolve()
        )

    def test_shadow_result_is_explicitly_excluded_from_trust_score(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "evidence.jpg"
            image.write_bytes(b"test")
            model = Mock()
            model.predict.return_value = {
                "prediction": "TAMPERED",
                "tampered_probability": 0.7,
                "authentic_probability": 0.3,
                "confidence": 0.7,
                "model_available": True,
                "model_version": "resnet-shadow-test",
            }
            evidence = SimpleNamespace(id=7, file_path=str(image))

            with (
                patch(
                    "app.analysis.tampering_shadow.resnet_shadow_enabled",
                    return_value=True,
                ),
                patch(
                    "app.analysis.tampering_shadow.get_resnet_shadow_model",
                    return_value=model,
                ),
            ):
                output = analyze_tampering_resnet_shadow(evidence)

        self.assertEqual(output["status"], "COMPLETED")
        self.assertEqual(output["analysis_type"], "TAMPERING_RESNET_SHADOW")
        self.assertEqual(output["result"]["decision_role"], "SHADOW_ONLY")
        self.assertTrue(output["result"]["excluded_from_trust_score"])

    def test_v2_primary_analysis_uses_multiview_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "evidence.jpg"
            image.write_bytes(b"test")
            model = Mock()
            model.predict_multiview.return_value = {
                "prediction": "TAMPERED",
                "tampered_probability": 0.8,
                "authentic_probability": 0.1,
                "ai_generated_probability": 0.1,
                "confidence": 0.8,
                "model_name": "EfficientNet-B0",
                "model_version": "forensic-v2-multiview-v1",
            }
            evidence = SimpleNamespace(id=8, file_path=str(image))

            with (
                patch(
                    "app.analysis.tampering.get_primary_tampering_model",
                    return_value=model,
                ),
                patch(
                    "app.analysis.tampering.primary_tampering_uses_multiview",
                    return_value=True,
                ),
            ):
                output = analyze_tampering(evidence)

        self.assertEqual(output["status"], "COMPLETED")
        model.predict_multiview.assert_called_once_with(image)
        model.predict.assert_not_called()
        self.assertFalse(output["result"]["excluded_from_trust_score"])


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.analysis.reliability_calibrated_fusion import (
    _matches_calibrated_checkpoint,
    analyze_reliability_calibrated_fusion,
    combine_belief_masses,
    make_belief_mass,
)


def analysis(analysis_type, result, evidence_id=1, status="COMPLETED"):
    return SimpleNamespace(
        analysis_type=analysis_type,
        evidence_id=evidence_id,
        status=status,
        result=result,
    )


class ReliabilityCalibratedFusionTests(unittest.TestCase):
    def test_calibrated_policy_rejects_wrong_checkpoint_identity(self):
        from app.analysis import reliability_calibrated_fusion as fusion_module

        original = fusion_module.FUSION_POLICY
        fusion_module.FUSION_POLICY = {
            **original,
            "data_summary": {
                "model_checkpoints": {
                    "AI_GENERATION": {
                        "model_version": "expected-version",
                        "model_sha256": "expected-hash",
                    }
                }
            },
        }
        try:
            self.assertTrue(_matches_calibrated_checkpoint({
                "model_version": "expected-version",
                "model_sha256": "expected-hash",
            }, "AI_GENERATION"))
            self.assertFalse(_matches_calibrated_checkpoint({
                "model_version": "different-version",
                "model_sha256": "expected-hash",
            }, "AI_GENERATION"))
        finally:
            fusion_module.FUSION_POLICY = original

    def test_basic_belief_assignment_preserves_uncertainty(self):
        mass = make_belief_mass(0.8, 0.9)
        self.assertAlmostEqual(mass["fraud"], 0.72)
        self.assertAlmostEqual(mass["authentic"], 0.18)
        self.assertAlmostEqual(mass["uncertainty"], 0.10)
        self.assertAlmostEqual(sum(mass.values()), 1.0)

    def test_dempster_combination_reports_conflict(self):
        authentic = make_belief_mass(0.1, 1.0)
        suspicious = make_belief_mass(0.9, 1.0)
        combined, conflict = combine_belief_masses(authentic, suspicious)
        self.assertAlmostEqual(conflict, 0.82)
        self.assertAlmostEqual(combined["authentic"], 0.5)
        self.assertAlmostEqual(combined["fraud"], 0.5)
        self.assertAlmostEqual(sum(combined.values()), 1.0)

    def test_fusion_produces_companion_outputs_and_provisional_label(self):
        from app.analysis import reliability_calibrated_fusion as fusion_module

        evidence = SimpleNamespace(id=1, evidence_type="damage")
        claim = SimpleNamespace(evidence=[evidence])
        run = SimpleNamespace(analysis_results=[
            analysis("QUALITY_GATE", {"quality_status": "GOOD"}),
            analysis("TAMPERING_DETECTION", {
                "tampered_probability": 0.10,
                "model_available": True,
                "model_version": "tampering-test",
            }),
            analysis("AI_GENERATION", {
                "ai_generated_probability": 0.20,
                "model_available": True,
                "model_version": "ai-test",
            }),
        ])

        original = fusion_module.FUSION_POLICY
        fusion_module.FUSION_POLICY = {
            **original,
            "validated": False,
            "data_summary": {},
            "thresholds": {
                **original["thresholds"],
                "validated": False,
            },
        }
        try:
            output = analyze_reliability_calibrated_fusion(claim, run)
        finally:
            fusion_module.FUSION_POLICY = original
        result = output["result"]

        self.assertEqual(output["status"], "COMPLETED")
        self.assertEqual(result["score_status"], "PROVISIONAL_UNVALIDATED")
        self.assertEqual(result["source_count"], 2)
        self.assertGreater(result["trust_score"], 50)
        self.assertIsInstance(result["fraud_evidence"], float)
        self.assertIsInstance(result["uncertainty"], float)
        self.assertIsInstance(result["conflict"], float)
        self.assertFalse(result["policy"]["validated"])

    def test_missing_models_do_not_generate_a_fake_score(self):
        evidence = SimpleNamespace(id=1, evidence_type="damage")
        claim = SimpleNamespace(evidence=[evidence])
        run = SimpleNamespace(analysis_results=[])

        result = analyze_reliability_calibrated_fusion(claim, run)["result"]

        self.assertEqual(result["score_status"], "UNAVAILABLE")
        self.assertIsNone(result["trust_score"])
        self.assertEqual(result["decision"], "REVIEW_NEEDED")

    def test_validated_ela_support_and_applicable_ocr_join_fusion(self):
        from app.analysis import reliability_calibrated_fusion as fusion_module

        evidence = SimpleNamespace(id=1, evidence_type="invoice")
        claim = SimpleNamespace(evidence=[evidence])
        run = SimpleNamespace(analysis_results=[
            analysis("QUALITY_GATE", {"quality_status": "GOOD"}),
            analysis("FORENSICS", {
                "analysis_version": "ela-recompression-v1",
                "ela_applicable": True,
                "ela_enhanced_mean": 18.0,
            }),
            analysis("TAMPERING_DETECTION", {
                "tampered_probability": 0.20,
                "model_available": True,
                "model_version": "tampering-test",
            }),
            analysis("AI_GENERATION", {
                "ai_generated_probability": 0.10,
                "model_available": True,
                "model_version": "ai-test",
            }),
            analysis("CROSS_EVIDENCE", {
                "analysis_version": "ocr-cross-evidence-v1",
                "comparison_summary": {
                    "match_count": 1,
                    "conflict_count": 2,
                    "not_comparable_count": 0,
                },
            }, evidence_id=None),
        ])

        original = fusion_module.FUSION_POLICY
        fusion_module.FUSION_POLICY = {
            **original,
            "validated": True,
            "data_summary": {},
            "thresholds": {
                **original["thresholds"],
                "calibrated_branches": [
                    "ELA_SUPPORT",
                    "OCR_CONSISTENCY",
                ],
            },
            "conditional_branches": {
                "ELA_SUPPORT": {
                    "enabled": True,
                    "validated": True,
                    "analysis_version": "ela-recompression-v1",
                    "feature": "ela_enhanced_mean",
                    "transform": {
                        "method": "LOGISTIC",
                        "center": 10.0,
                        "scale": 4.0,
                    },
                    "temperature": 1.0,
                    "reliability_by_quality": {"GOOD": 0.40},
                    "visual_support_weight": 0.25,
                },
                "OCR_CONSISTENCY": {
                    "enabled": True,
                    "validated": True,
                    "analysis_version": "ocr-cross-evidence-v1",
                    "temperature": 1.0,
                    "reliability_by_quality": {"OVERALL": 0.50},
                    "minimum_comparisons": 1,
                },
            },
        }
        try:
            result = analyze_reliability_calibrated_fusion(claim, run)["result"]
        finally:
            fusion_module.FUSION_POLICY = original

        self.assertEqual(result["source_count"], 3)
        visual = next(
            source for source in result["sources"]
            if source["source"] == "VISUAL_MANIPULATION_BRANCH"
        )
        self.assertEqual(
            visual["supporting_sources"],
            ["TAMPERING_DETECTION", "ELA_SUPPORT"],
        )
        document = next(
            source for source in result["sources"]
            if source["source"] == "DOCUMENT_CONSISTENCY_BRANCH"
        )
        self.assertEqual(document["observations"][0]["conflict_count"], 2)
        statuses = {
            item["branch"]: item["status"]
            for item in result["conditional_branch_status"]
        }
        self.assertEqual(statuses["ELA_SUPPORT"], "INCLUDED_AS_VISUAL_SUPPORT")
        self.assertEqual(statuses["OCR_CONSISTENCY"], "INCLUDED")

    def test_ocr_without_comparable_text_is_not_applicable(self):
        from app.analysis import reliability_calibrated_fusion as fusion_module

        evidence = SimpleNamespace(id=1, evidence_type="product")
        claim = SimpleNamespace(evidence=[evidence])
        run = SimpleNamespace(analysis_results=[
            analysis("QUALITY_GATE", {"quality_status": "GOOD"}),
            analysis("TAMPERING_DETECTION", {
                "tampered_probability": 0.20,
                "model_available": True,
                "model_version": "tampering-test",
            }),
            analysis("AI_GENERATION", {
                "ai_generated_probability": 0.10,
                "model_available": True,
                "model_version": "ai-test",
            }),
            analysis("CROSS_EVIDENCE", {
                "analysis_version": "ocr-cross-evidence-v1",
                "comparison_summary": {
                    "match_count": 0,
                    "conflict_count": 0,
                    "not_comparable_count": 3,
                },
            }, evidence_id=None),
        ])

        original = fusion_module.FUSION_POLICY
        fusion_module.FUSION_POLICY = {
            **original,
            "data_summary": {},
            "thresholds": {
                **original["thresholds"],
                "calibrated_branches": ["OCR_CONSISTENCY"],
            },
            "conditional_branches": {
                **original.get("conditional_branches", {}),
                "OCR_CONSISTENCY": {
                    "enabled": True,
                    "validated": True,
                    "analysis_version": "ocr-cross-evidence-v1",
                    "temperature": 1.0,
                    "reliability_by_quality": {"OVERALL": 0.50},
                    "minimum_comparisons": 1,
                },
            },
        }
        try:
            result = analyze_reliability_calibrated_fusion(claim, run)["result"]
        finally:
            fusion_module.FUSION_POLICY = original

        self.assertEqual(result["source_count"], 2)
        ocr_status = next(
            item for item in result["conditional_branch_status"]
            if item["branch"] == "OCR_CONSISTENCY"
        )
        self.assertEqual(ocr_status["status"], "NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()

import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.core.config import settings
from app.core.security import hash_password
from app.core.version import PIPELINE_VERSION
from app.db.database import Base, get_db
from app.db.models import AnalysisResult, Claim, User, VerificationRun
from app.main import app


def create_png_bytes():
    output = BytesIO()
    Image.new("RGB", (32, 32), "white").save(output, format="PNG")
    return output.getvalue()


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.upload_directory = tempfile.TemporaryDirectory()
        self.original_upload_dir = settings.upload_dir
        settings.upload_dir = Path(self.upload_directory.name)

        def override_get_db():
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        registration = self.client.post(
            "/auth/register",
            json={
                "email": "claimant@example.com",
                "full_name": "Claimant Test",
                "password": "safe-password-123"
            }
        )
        self.assertEqual(registration.status_code, 201)
        authentication = registration.json()
        self.user = authentication["user"]
        self.headers = {
            "Authorization": f"Bearer {authentication['access_token']}"
        }

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        settings.upload_dir = self.original_upload_dir
        self.upload_directory.cleanup()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def create_claim(self):
        response = self.client.post("/claims/", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def create_admin_headers(self):
        session = self.session_factory()
        administrator = User(
            email="verification-admin@example.com",
            full_name="Verification Administrator",
            password_hash=hash_password("admin-password-123"),
            role="ADMIN"
        )
        session.add(administrator)
        session.commit()
        session.close()
        login = self.client.post(
            "/auth/login",
            json={
                "email": "verification-admin@example.com",
                "password": "admin-password-123"
            }
        )
        return {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }

    def test_health_exposes_versioned_runtime_status(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["api_version"], "0.4.0")
        self.assertEqual(
            payload["pipeline_version"],
            PIPELINE_VERSION,
        )
        self.assertIn(payload["detector_policy_mode"], {
            "LEGACY", "HYBRID_CANDIDATE", "HYBRID_V1", "HYBRID_V2"
        })
        self.assertIsInstance(payload["fusion_policy_validated"], bool)

    def test_claim_create_and_get_round_trip(self):
        created = self.create_claim()

        response = self.client.get(
            f"/claims/{created['id']}",
            headers=self.headers
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["claim_number"], created["claim_number"])
        self.assertEqual(
            response.json()["claimant"]["email"],
            "claimant@example.com"
        )
        self.assertEqual(response.json()["evidence"], [])

    def test_structured_draft_can_be_resumed_edited_and_photo_replaced(self):
        details = {
            "claim_type": "WARRANTY",
            "item_name": "Laptop display",
            "reference_number": "ORDER-8421",
            "incident_date": "2026-10-20",
            "incident_summary": "The display developed a dark band across its right edge."
        }
        created_response = self.client.post(
            "/claims/", headers=self.headers, json=details
        )
        self.assertEqual(created_response.status_code, 200)
        created = created_response.json()
        self.assertEqual(created["intake_version"], 2)
        self.assertEqual(created["item_name"], "Laptop display")

        claim_url = f"/claims/{created['id']}"
        updated_details = {**details, "item_name": "Laptop screen assembly"}
        updated_response = self.client.put(
            f"{claim_url}/details", headers=self.headers, json=updated_details
        )
        self.assertEqual(updated_response.status_code, 200)
        self.assertEqual(updated_response.json()["item_name"], "Laptop screen assembly")

        upload_url = f"{claim_url}/upload/damage"
        first_upload = self.client.post(
            upload_url,
            headers=self.headers,
            files={"file": ("before.png", create_png_bytes(), "image/png")},
            data={"description": "A dark band covers the right edge of the display.", "source_type": "ORIGINAL_CAMERA"}
        )
        self.assertEqual(first_upload.status_code, 200)
        original_id = first_upload.json()["evidence"]["id"]
        replacement = self.client.post(
            upload_url,
            headers=self.headers,
            files={"file": ("after.png", create_png_bytes(), "image/png")},
            data={"description": "A clearer view of the dark band on the display.", "source_type": "ORIGINAL_CAMERA", "replace": "true"}
        )
        self.assertEqual(replacement.status_code, 200)
        self.assertEqual(replacement.json()["evidence"]["id"], original_id)
        resumed = self.client.get(claim_url, headers=self.headers).json()
        self.assertEqual(resumed["item_name"], "Laptop screen assembly")
        self.assertEqual(len(resumed["evidence"]), 1)
        self.assertEqual(resumed["evidence"][0]["original_filename"], "after.png")

        submitted = self.client.post(f"{claim_url}/submit", headers=self.headers)
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.json()["status"], "SUBMITTED")
        self.assertEqual(
            self.client.put(f"{claim_url}/details", headers=self.headers, json=details).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(
                upload_url,
                headers=self.headers,
                files={"file": ("late.png", create_png_bytes(), "image/png")},
                data={"replace": "true"},
            ).status_code,
            409,
        )

    def test_image_upload_duplicate_and_pdf_rejection(self):
        claim = self.create_claim()
        endpoint = f"/claims/{claim['id']}/upload/invoice"

        pdf_response = self.client.post(
            endpoint,
            headers=self.headers,
            files={"file": ("invoice.pdf", b"%PDF-1.7", "application/pdf")}
        )
        upload_response = self.client.post(
            endpoint,
            headers=self.headers,
            files={"file": ("invoice.png", create_png_bytes(), "image/png")},
            data={
                "description": "Retail invoice showing the purchase details.",
                "source_type": "DOCUMENT_SCAN",
                "captured_at": "2026-10-20T11:30",
                "location_label": "Pune retailer"
            }
        )
        duplicate_response = self.client.post(
            endpoint,
            headers=self.headers,
            files={"file": ("second.png", create_png_bytes(), "image/png")}
        )
        claim_response = self.client.get(
            f"/claims/{claim['id']}",
            headers=self.headers
        )

        self.assertEqual(pdf_response.status_code, 400)
        self.assertEqual(pdf_response.json()["detail"], "Unsupported file type.")
        self.assertEqual(upload_response.status_code, 200)
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertNotIn("file_path", claim_response.json()["evidence"][0])
        evidence_payload = claim_response.json()["evidence"][0]
        self.assertEqual(
            evidence_payload["description"],
            "Retail invoice showing the purchase details."
        )
        self.assertEqual(evidence_payload["source_type"], "DOCUMENT_SCAN")
        self.assertEqual(evidence_payload["location_label"], "Pune retailer")
        self.assertEqual(evidence_payload["image_width"], 32)
        self.assertEqual(evidence_payload["image_height"], 32)
        self.assertGreater(evidence_payload["file_size_bytes"], 0)

        evidence_id = claim_response.json()["evidence"][0]["id"]
        image_response = self.client.get(
            f"/claims/{claim['id']}/evidence/{evidence_id}/file",
            headers=self.headers
        )
        unauthenticated_image = self.client.get(
            f"/claims/{claim['id']}/evidence/{evidence_id}/file"
        )
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response.headers["content-type"], "image/png")
        self.assertEqual(unauthenticated_image.status_code, 401)

    def test_verification_requires_evidence(self):
        claim = self.create_claim()
        admin_headers = self.create_admin_headers()

        response = self.client.post(
            f"/claims/{claim['id']}/verify",
            headers=admin_headers
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "No evidence uploaded for this claim."
        )

    def test_verification_success_and_failure_contracts(self):
        claim = self.create_claim()
        self.client.post(
            f"/claims/{claim['id']}/upload/product",
            headers=self.headers,
            files={"file": ("product.png", create_png_bytes(), "image/png")}
        )
        submission = self.client.post(
            f"/claims/{claim['id']}/submit",
            headers=self.headers
        )
        claimant_attempt = self.client.post(
            f"/claims/{claim['id']}/verify",
            headers=self.headers
        )
        admin_headers = self.create_admin_headers()

        with patch(
            "app.api.verification.create_verification_run",
            return_value=SimpleNamespace(id=42, status="COMPLETED")
        ):
            success = self.client.post(
                f"/claims/{claim['id']}/verify",
                headers=admin_headers
            )

        with patch(
            "app.api.verification.create_verification_run",
            side_effect=RuntimeError("private failure detail")
        ):
            failure = self.client.post(
                f"/claims/{claim['id']}/verify",
                headers=admin_headers
            )

        self.assertEqual(submission.status_code, 200)
        self.assertEqual(submission.json()["status"], "SUBMITTED")
        self.assertEqual(claimant_attempt.status_code, 403)
        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.json()["verification_run_id"], 42)
        self.assertEqual(success.json()["status"], "COMPLETED")
        self.assertEqual(failure.status_code, 500)
        self.assertNotIn("private failure detail", failure.text)

    def test_submission_locks_evidence_until_administrator_verification(self):
        claim = self.create_claim()
        endpoint = f"/claims/{claim['id']}/upload/invoice"
        self.client.post(
            endpoint,
            headers=self.headers,
            files={"file": ("invoice.png", create_png_bytes(), "image/png")}
        )

        submission = self.client.post(
            f"/claims/{claim['id']}/submit",
            headers=self.headers
        )
        late_upload = self.client.post(
            f"/claims/{claim['id']}/upload/damage",
            headers=self.headers,
            files={"file": ("damage.png", create_png_bytes(), "image/png")}
        )

        self.assertEqual(submission.status_code, 200)
        self.assertEqual(submission.json()["status"], "SUBMITTED")
        self.assertEqual(late_upload.status_code, 409)

    def test_claim_list_exposes_latest_trust_assessment(self):
        session = self.session_factory()
        claim = Claim(
            claim_number="TL-INTEGRATION",
            status="APPROVED",
            owner_id=self.user["id"]
        )
        session.add(claim)
        session.commit()
        run = VerificationRun(claim_id=claim.id, status="COMPLETED")
        session.add(run)
        session.commit()
        session.add(
            AnalysisResult(
                verification_run_id=run.id,
                analysis_type="TRUST_ASSESSMENT",
                status="COMPLETED",
                result={"assessment": "REVIEW_NEEDED"},
                message="Review required."
            )
        )
        session.commit()
        session.close()

        response = self.client.get("/claims/", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        summary = response.json()["claims"][0]["verification_runs"][0]
        self.assertEqual(
            summary["trust_assessment"]["assessment"],
            "REVIEW_NEEDED"
        )

    def test_verification_results_wait_for_administrator_decision(self):
        session = self.session_factory()
        claim = Claim(
            claim_number="TL-RESTRICTED",
            status="AWAITING_DECISION",
            owner_id=self.user["id"]
        )
        session.add(claim)
        session.commit()
        run = VerificationRun(claim_id=claim.id, status="COMPLETED")
        session.add(run)
        session.commit()
        session.add(
            AnalysisResult(
                verification_run_id=run.id,
                analysis_type="TRUST_ASSESSMENT",
                status="COMPLETED",
                result={"assessment": "REVIEW_NEEDED"},
                message="Administrator review required."
            )
        )
        session.commit()
        run_id = run.id
        session.close()

        claimant_view = self.client.get(
            f"/claims/verification/{run_id}",
            headers=self.headers
        )
        admin_view = self.client.get(
            f"/claims/verification/{run_id}",
            headers=self.create_admin_headers()
        )

        self.assertTrue(claimant_view.json()["results_restricted"])
        self.assertEqual(claimant_view.json()["analysis_results"], [])
        self.assertFalse(admin_view.json()["results_restricted"])
        self.assertEqual(len(admin_view.json()["analysis_results"]), 1)

    def test_authentication_and_claim_ownership_are_enforced(self):
        claim = self.create_claim()

        unauthenticated = self.client.get(f"/claims/{claim['id']}")
        other_registration = self.client.post(
            "/auth/register",
            json={
                "email": "other@example.com",
                "full_name": "Other Claimant",
                "password": "other-password-123"
            }
        ).json()
        other_headers = {
            "Authorization": f"Bearer {other_registration['access_token']}"
        }
        inaccessible = self.client.get(
            f"/claims/{claim['id']}",
            headers=other_headers
        )

        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(inaccessible.status_code, 404)

    def test_login_and_current_user_contract(self):
        login = self.client.post(
            "/auth/login",
            json={
                "email": "CLAIMANT@example.com",
                "password": "safe-password-123"
            }
        )
        self.assertEqual(login.status_code, 200)

        token = login.json()["access_token"]
        profile = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["role"], "CLAIMANT")

    def test_administrator_can_access_legacy_and_claimant_claims(self):
        claimant_claim = self.create_claim()
        session = self.session_factory()
        legacy_claim = Claim(
            claim_number="TL-LEGACY",
            status="PENDING",
            owner_id=None
        )
        administrator = User(
            email="admin@example.com",
            full_name="Test Administrator",
            password_hash=hash_password("admin-password-123"),
            role="ADMIN"
        )
        session.add_all([legacy_claim, administrator])
        session.commit()
        session.close()

        login = self.client.post(
            "/auth/login",
            json={
                "email": "admin@example.com",
                "password": "admin-password-123"
            }
        )
        admin_headers = {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }
        response = self.client.get("/claims/", headers=admin_headers)

        self.assertEqual(response.status_code, 200)
        claim_numbers = {
            claim["claim_number"]
            for claim in response.json()["claims"]
        }
        self.assertIn(claimant_claim["claim_number"], claim_numbers)
        self.assertIn("TL-LEGACY", claim_numbers)
        claimant_row = next(
            item for item in response.json()["claims"]
            if item["claim_number"] == claimant_claim["claim_number"]
        )
        self.assertEqual(
            claimant_row["claimant"]["email"],
            "claimant@example.com"
        )

    def test_tampered_token_is_rejected(self):
        token = self.headers["Authorization"].removeprefix("Bearer ")
        header, payload, signature = token.split(".")
        position = len(payload) // 2
        replacement = "a" if payload[position] != "a" else "b"
        tampered_payload = payload[:position] + replacement + payload[position + 1:]
        tampered_token = f"{header}.{tampered_payload}.{signature}"

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )

        self.assertEqual(response.status_code, 401)

    def test_profile_and_password_settings(self):
        profile = self.client.put(
            "/auth/profile",
            headers=self.headers,
            json={"full_name": "Updated Claimant"}
        )
        wrong_password = self.client.post(
            "/auth/change-password",
            headers=self.headers,
            json={
                "current_password": "incorrect-password",
                "new_password": "new-safe-password-123"
            }
        )
        changed_password = self.client.post(
            "/auth/change-password",
            headers=self.headers,
            json={
                "current_password": "safe-password-123",
                "new_password": "new-safe-password-123"
            }
        )
        old_login = self.client.post(
            "/auth/login",
            json={
                "email": "claimant@example.com",
                "password": "safe-password-123"
            }
        )
        new_login = self.client.post(
            "/auth/login",
            json={
                "email": "claimant@example.com",
                "password": "new-safe-password-123"
            }
        )

        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["full_name"], "Updated Claimant")
        self.assertEqual(wrong_password.status_code, 400)
        self.assertEqual(changed_password.status_code, 200)
        self.assertEqual(old_login.status_code, 401)
        self.assertEqual(new_login.status_code, 200)

    def test_reports_are_administrator_only_and_export_csv(self):
        claim = self.create_claim()
        claimant_report = self.client.get(
            "/admin/reports/summary",
            headers=self.headers
        )

        session = self.session_factory()
        administrator = User(
            email="report-admin@example.com",
            full_name="Report Administrator",
            password_hash=hash_password("report-password-123"),
            role="ADMIN"
        )
        session.add(administrator)
        session.commit()
        session.close()
        login = self.client.post(
            "/auth/login",
            json={
                "email": "report-admin@example.com",
                "password": "report-password-123"
            }
        )
        admin_headers = {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }

        report = self.client.get(
            "/admin/reports/summary",
            headers=admin_headers
        )
        export = self.client.get(
            "/admin/reports/claims.csv",
            headers=admin_headers
        )
        system = self.client.get(
            "/admin/system",
            headers=admin_headers
        )

        self.assertEqual(claimant_report.status_code, 403)
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json()["metrics"]["total_claims"], 1)
        self.assertEqual(
            report.json()["recent_claims"][0]["claim_number"],
            claim["claim_number"]
        )
        self.assertEqual(export.status_code, 200)
        self.assertIn("text/csv", export.headers["content-type"])
        self.assertIn(claim["claim_number"], export.text)
        self.assertEqual(system.status_code, 200)
        self.assertEqual(system.json()["database_engine"], "sqlite")
        self.assertEqual(
            system.json()["pipeline_version"],
            PIPELINE_VERSION
        )
        self.assertIn(
            system.json()["detector_policy_mode"],
            {"LEGACY", "HYBRID_CANDIDATE", "HYBRID_V1", "HYBRID_V2"}
        )
        self.assertIsInstance(system.json()["resnet_shadow_enabled"], bool)
        self.assertIn("fusion_policy_version", system.json())
        self.assertIsInstance(
            system.json()["fusion_policy_validated"],
            bool
        )
        self.assertEqual(
            set(system.json()["model_status"]),
            {
                "ai_generation_efficientnet",
                "authenticity_efficientnet",
                "forensic_multiview_efficientnet",
                "tampering_resnet_shadow",
                "primary_models_ready"
            }
        )
        self.assertTrue(all(
            isinstance(value, bool)
            for value in system.json()["model_status"].values()
        ))

    def test_manually_escalated_low_concern_claim_stays_in_review_queue(self):
        claim = self.create_claim()
        session = self.session_factory()
        database_claim = session.get(Claim, claim["id"])
        database_claim.status = "AWAITING_DECISION"
        run = VerificationRun(claim_id=claim["id"], status="COMPLETED")
        session.add(run)
        session.flush()
        session.add(AnalysisResult(
            verification_run_id=run.id,
            analysis_type="TRUST_ASSESSMENT",
            status="COMPLETED",
            result={"assessment": "LOW_CONCERN", "reasons": []},
            message="No major concerns flagged."
        ))
        session.commit()
        session.close()
        admin_headers = self.create_admin_headers()

        before = self.client.get("/admin/reviews/queue", headers=admin_headers)
        escalated = self.client.post(
            f"/admin/claims/{claim['id']}/decisions",
            headers=admin_headers,
            json={"action": "ESCALATE", "note": "Senior reviewer requested."}
        )
        after = self.client.get("/admin/reviews/queue", headers=admin_headers)
        summary = self.client.get("/admin/reports/summary", headers=admin_headers)

        self.assertEqual(before.json()["count"], 0)
        self.assertEqual(escalated.status_code, 201)
        self.assertEqual(after.json()["count"], 1)
        self.assertEqual(after.json()["claims"][0]["claim"]["id"], claim["id"])
        self.assertEqual(summary.json()["metrics"]["review_needed"], 1)

    def test_review_decisions_follow_transitions_and_preserve_history(self):
        claim = self.create_claim()
        session = self.session_factory()
        database_claim = session.get(Claim, claim["id"])
        database_claim.status = "COMPLETED"
        run = VerificationRun(claim_id=claim["id"], status="COMPLETED")
        session.add(run)
        session.commit()
        session.add(
            AnalysisResult(
                verification_run_id=run.id,
                analysis_type="TRUST_ASSESSMENT",
                status="COMPLETED",
                result={
                    "assessment": "REVIEW_NEEDED",
                    "risk_signals": [{"type": "TAMPERING_DETECTED"}],
                    "reasons": ["Manual inspection required."]
                },
                message="Review required."
            )
        )
        session.add(
            AnalysisResult(
                verification_run_id=run.id,
                analysis_type="TAMPERING_DETECTION",
                status="COMPLETED",
                result={
                    "prediction": "TAMPERED",
                    "model_version": (
                        "evidence-authenticity-v2-forensic-candidate-"
                        "multiview-v1"
                    ),
                    "view_predictions": [
                        {
                            "view": "top_right",
                            "tampered_probability": 0.81,
                        }
                    ],
                    "regional_explanation": {
                        "highest_signal_view": "top_right",
                        "localization_scope": "COARSE_REGIONAL_VIEW",
                        "signal_type": "RAW_UNCALIBRATED_VIEW_PROBABILITY",
                    },
                },
                message="Forensic multi-view analysis completed.",
            )
        )
        administrator = User(
            email="review-admin@example.com",
            full_name="Review Administrator",
            password_hash=hash_password("review-password-123"),
            role="ADMIN"
        )
        session.add(administrator)
        session.commit()
        run_id = run.id
        session.close()

        claimant_attempt = self.client.post(
            f"/admin/claims/{claim['id']}/decisions",
            headers=self.headers,
            json={"action": "APPROVE", "note": "Not allowed"}
        )
        login = self.client.post(
            "/auth/login",
            json={
                "email": "review-admin@example.com",
                "password": "review-password-123"
            }
        )
        admin_headers = {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }

        queue_before = self.client.get(
            "/admin/reviews/queue",
            headers=admin_headers
        )
        self.assertEqual(
            queue_before.json()["claims"][0]["claim"]["claimant_email"],
            "claimant@example.com"
        )
        escalated = self.client.post(
            f"/admin/claims/{claim['id']}/decisions",
            headers=admin_headers,
            json={
                "action": "ESCALATE",
                "note": "Escalate for senior forensic review.",
                "verification_run_id": run_id
            }
        )
        repeated_escalation = self.client.post(
            f"/admin/claims/{claim['id']}/decisions",
            headers=admin_headers,
            json={"action": "ESCALATE", "note": "Escalate again."}
        )
        approved = self.client.post(
            f"/admin/claims/{claim['id']}/decisions",
            headers=admin_headers,
            json={"action": "APPROVE", "note": "Senior review cleared the evidence."}
        )
        terminal_change = self.client.post(
            f"/admin/claims/{claim['id']}/decisions",
            headers=admin_headers,
            json={"action": "REJECT", "note": "Attempt to reverse decision."}
        )
        history = self.client.get(
            f"/admin/claims/{claim['id']}/decisions",
            headers=admin_headers
        )
        claimant_detail = self.client.get(
            f"/claims/{claim['id']}",
            headers=self.headers
        )
        claimant_run = self.client.get(
            f"/claims/verification/{run_id}",
            headers=self.headers,
        )

        self.assertEqual(claimant_attempt.status_code, 403)
        self.assertEqual(queue_before.status_code, 200)
        self.assertEqual(queue_before.json()["count"], 1)
        self.assertEqual(escalated.status_code, 201)
        self.assertEqual(escalated.json()["claim_status"], "ESCALATED")
        self.assertEqual(repeated_escalation.status_code, 409)
        self.assertEqual(approved.status_code, 201)
        self.assertEqual(approved.json()["claim_status"], "APPROVED")
        self.assertEqual(terminal_change.status_code, 409)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["current_status"], "APPROVED")
        self.assertEqual(len(history.json()["decisions"]), 2)
        self.assertEqual(history.json()["decisions"][0]["action"], "APPROVE")
        self.assertEqual(
            history.json()["decisions"][1]["assessment_snapshot"]["assessment"],
            "REVIEW_NEEDED"
        )
        claimant_decision = claimant_detail.json()["review_decision"]
        self.assertEqual(claimant_decision["resulting_status"], "APPROVED")
        self.assertEqual(
            claimant_decision["message"],
            "Senior review cleared the evidence."
        )
        self.assertNotIn("note", claimant_decision)
        self.assertNotIn("reviewer", claimant_decision)
        self.assertFalse(claimant_run.json()["results_restricted"])
        tampering_result = next(
            item for item in claimant_run.json()["analysis_results"]
            if item["analysis_type"] == "TAMPERING_DETECTION"
        )
        self.assertEqual(
            tampering_result["result"]["regional_explanation"][
                "highest_signal_view"
            ],
            "top_right",
        )
        self.assertEqual(
            tampering_result["result"]["regional_explanation"][
                "localization_scope"
            ],
            "COARSE_REGIONAL_VIEW",
        )
        claimant_trust = (
            claimant_detail.json()["verification_runs"][0]["trust_assessment"]
        )
        self.assertEqual(claimant_trust["assessment"], "REVIEW_NEEDED")
        self.assertEqual(
            claimant_trust["reasons"],
            ["Manual inspection required."]
        )


if __name__ == "__main__":
    unittest.main()

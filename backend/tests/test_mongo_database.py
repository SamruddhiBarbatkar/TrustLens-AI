"""MongoDB storage integration without requiring a running server."""

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

import mongomock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.claims import router as claims_router
from app.api.uploads import router as uploads_router
from app.core.config import settings
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import AnalysisResult, Claim, User, VerificationRun
from app.db.mongo_database import MongoSession


class MongoDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.database = mongomock.MongoClient().trustlens_test
        self.database.users.create_index("email", unique=True)
        self.database.claims.create_index("claim_number", unique=True)
        self.database.evidence.create_index(
            [("claim_id", 1), ("evidence_type", 1)]
        )
        self.upload_directory = tempfile.TemporaryDirectory()
        self.original_upload_dir = settings.upload_dir
        settings.upload_dir = Path(self.upload_directory.name)
        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(admin_router)
        app.include_router(claims_router)
        app.include_router(uploads_router)

        def override_get_db():
            session = MongoSession(self.database)
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        settings.upload_dir = self.original_upload_dir
        self.upload_directory.cleanup()

    def test_claimant_flow_and_relationships(self):
        registration = self.client.post(
            "/auth/register",
            json={"email": "mongo@example.com", "full_name": "Mongo User", "password": "safe-password-123"},
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        token = registration.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.get("/auth/me", headers=headers).status_code, 200)
        claim_response = self.client.post("/claims/", headers=headers)
        self.assertEqual(claim_response.status_code, 200, claim_response.text)
        claim_id = claim_response.json()["id"]
        details = self.client.put(
            f"/claims/{claim_id}/details",
            headers=headers,
            json={
                "claim_type": "WARRANTY",
                "item_name": "Damaged product",
                "reference_number": "W-123",
                "incident_date": "2026-01-10",
                "incident_summary": "The product developed visible damage during normal use.",
            },
        )
        self.assertEqual(details.status_code, 200, details.text)
        image_bytes = BytesIO()
        Image.new("RGB", (32, 32), "white").save(image_bytes, "PNG")
        uploaded = self.client.post(
            f"/claims/{claim_id}/upload/product",
            headers=headers,
            files={"file": ("item.png", image_bytes.getvalue(), "image/png")},
            data={"description": "The damaged product", "source_type": "DEVICE_GALLERY"},
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        self.assertEqual(self.client.post(f"/claims/{claim_id}/submit", headers=headers).status_code, 200)
        detail = self.client.get(f"/claims/{claim_id}", headers=headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["status"], "SUBMITTED")
        self.assertEqual(detail.json()["claimant"]["email"], "mongo@example.com")
        self.assertEqual(detail.json()["incident_date"], "2026-01-10")
        self.assertEqual(detail.json()["evidence"][0]["type"], "product")

        session = MongoSession(self.database)
        claim = session.get(Claim, claim_id)
        run = VerificationRun(claim_id=claim.id, status="COMPLETED")
        session.add(run)
        session.commit()
        session.refresh(run)
        self.assertEqual(run.claim.id, claim_id)
        analysis = AnalysisResult(
            verification_run_id=run.id,
            evidence_id=claim.evidence[0].id,
            analysis_type="TRUST_ASSESSMENT",
            status="COMPLETED",
            result={"assessment": "REVIEW_NEEDED"},
        )
        session.add(analysis)
        self.assertEqual(
            session.query(AnalysisResult).filter(
                AnalysisResult.verification_run_id == run.id,
                AnalysisResult.evidence_id == claim.evidence[0].id,
            ).first().analysis_type,
            "TRUST_ASSESSMENT",
        )
        reviewer = User(
            email="reviewer@example.com",
            full_name="Review Administrator",
            password_hash="unused-test-hash",
            role="ADMIN",
        )
        session.add(reviewer)
        session.commit()
        session.close()
        reviewed = self.client.post(
            f"/admin/claims/{claim_id}/decisions",
            headers={"Authorization": f"Bearer {create_access_token(reviewer)}"},
            json={"action": "APPROVE", "note": "Reviewed evidence and approved."},
        )
        self.assertEqual(reviewed.status_code, 201, reviewed.text)
        self.assertEqual(reviewed.json()["decision"]["reviewer"]["email"], "reviewer@example.com")
        reloaded = MongoSession(self.database).get(Claim, claim_id)
        self.assertEqual(reloaded.verification_runs[0].analysis_results[0].result["assessment"], "REVIEW_NEEDED")
        self.assertEqual(reloaded.review_decisions[0].reviewer.email, "reviewer@example.com")
        self.assertEqual(self.client.get(f"/claims/{claim_id}", headers=headers).json()["status"], "APPROVED")

    def test_rollback_discards_pending_results(self):
        session = MongoSession(self.database)
        user = User(email="rollback@example.com", full_name="Rollback User", password_hash="x")
        session.add(user)
        session.commit()
        claim = Claim(claim_number="TL-ROLLBACK", owner_id=user.id, status="SUBMITTED")
        session.add(claim)
        session.commit()
        claim.status = "VERIFICATION_STARTED"
        session.add(VerificationRun(claim_id=claim.id, status="RUNNING"))
        session.flush()
        session.rollback()
        self.assertEqual(MongoSession(self.database).get(Claim, claim.id).status, "SUBMITTED")
        self.assertEqual(self.database.verification_runs.count_documents({}), 0)


if __name__ == "__main__":
    unittest.main()

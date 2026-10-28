import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.db.database import Base
from app.db.models import AnalysisResult, Claim, Evidence, VerificationRun
from app.services.verification_pipeline import create_verification_run


class VerificationLifecycleTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()

        self.claim = Claim(
            claim_number="TL-TEST-FAILURE",
            status="PENDING"
        )
        self.session.add(self.claim)
        self.session.commit()

        self.evidence = Evidence(
            claim_id=self.claim.id,
            evidence_type="invoice",
            original_filename="invoice.png",
            stored_filename="invoice_test.png",
            file_path="missing-test-file.png"
        )
        self.session.add(self.evidence)
        self.session.commit()
        self.session.refresh(self.claim)

    def tearDown(self):
        self.session.close()

    def test_unexpected_failure_is_persisted(self):
        with patch(
            "app.services.verification_pipeline.run_analysis",
            side_effect=RuntimeError("forced test failure")
        ):
            with self.assertRaises(RuntimeError):
                create_verification_run(
                    db=self.session,
                    claim=self.claim
                )

        run = self.session.query(VerificationRun).one()
        claim = self.session.get(Claim, self.claim.id)
        error_result = self.session.query(AnalysisResult).filter(
            AnalysisResult.verification_run_id == run.id,
            AnalysisResult.analysis_type == "PIPELINE_ERROR"
        ).one()

        self.assertEqual(run.status, "FAILED")
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.completed_at)
        self.assertEqual(claim.status, "VERIFICATION_FAILED")
        self.assertEqual(error_result.status, "ERROR")
        self.assertEqual(
            error_result.result["error_type"],
            "RuntimeError"
        )
        self.assertNotIn(
            "forced test failure",
            error_result.message
        )


if __name__ == "__main__":
    unittest.main()

import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.api.uploads import (
    UploadValidationError,
    save_upload_with_limit,
    upload_evidence,
    validate_saved_file
)
from app.db.database import Base
from app.db.models import Claim, Evidence, User


class UploadValidationTests(unittest.TestCase):
    def test_valid_png_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "image.png"
            Image.new("RGB", (32, 32), "white").save(file_path)

            validate_saved_file(file_path, ".png")

    def test_extension_content_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "image.jpg"
            Image.new("RGB", (32, 32), "white").save(
                file_path,
                format="PNG"
            )

            with self.assertRaises(UploadValidationError):
                validate_saved_file(file_path, ".jpg")

    def test_empty_upload_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "empty.uploading"
            upload = SimpleNamespace(
                file=BytesIO(b"")
            )

            with self.assertRaises(UploadValidationError):
                save_upload_with_limit(upload, destination)

    def test_duplicate_evidence_type_returns_conflict(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        try:
            user = User(
                email="upload-test@example.com",
                full_name="Upload Test",
                password_hash="not-used",
                role="CLAIMANT"
            )
            session.add(user)
            session.commit()

            claim = Claim(
                claim_number="TL-TEST-DUPLICATE",
                status="PENDING",
                owner_id=user.id
            )
            session.add(claim)
            session.commit()

            session.add(
                Evidence(
                    claim_id=claim.id,
                    evidence_type="invoice",
                    original_filename="first.png",
                    stored_filename="invoice_first.png",
                    file_path="uploads/claim_test/invoice_first.png"
                )
            )
            session.commit()

            upload = UploadFile(
                file=BytesIO(b"duplicate"),
                filename="second.png"
            )

            with self.assertRaises(HTTPException) as context:
                upload_evidence(
                    claim_id=claim.id,
                    evidence_type="invoice",
                    file=upload,
                    db=session,
                    current_user=user,
                    replace=False
                )

            self.assertEqual(
                context.exception.status_code,
                409
            )
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()

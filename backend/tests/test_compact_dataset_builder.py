import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from scripts.prepare_compact_calibration_dataset import (
    relative_manifest_path,
    retry_delay,
)


class CompactDatasetBuilderTests(unittest.TestCase):
    def test_retry_delay_honors_rate_limit_header(self):
        headers = Message()
        headers["Retry-After"] = "37"
        error = HTTPError("https://example.test", 429, "limited", headers, None)

        self.assertEqual(retry_delay(error, 0), 37)

    def test_retry_delay_caps_rate_limit_backoff(self):
        error = HTTPError("https://example.test", 429, "limited", Message(), None)

        self.assertEqual(retry_delay(error, 10), 60)

    def test_manifest_path_uses_selected_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            calibration = Path(directory) / "calibration"
            destination = (
                calibration
                / "fresh_audit_data"
                / "images"
                / "tampered"
                / "sample.jpg"
            )
            manifest = calibration / "fresh_audit_manifest.csv"
            self.assertEqual(
                relative_manifest_path(destination, manifest).as_posix(),
                "fresh_audit_data/images/tampered/sample.jpg",
            )


if __name__ == "__main__":
    unittest.main()

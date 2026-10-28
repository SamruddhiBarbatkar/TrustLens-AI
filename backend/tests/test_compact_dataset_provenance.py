import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND_DIR / "scripts" / "prepare_compact_calibration_dataset.py"
SPEC = importlib.util.spec_from_file_location("compact_dataset_builder", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CompactDatasetProvenanceTests(unittest.TestCase):
    def test_prior_provenance_identities_are_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prior.csv"
            with path.open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(
                    output,
                    fieldnames=["dataset", "dataset_row", "group_id", "sha256"],
                )
                writer.writeheader()
                writer.writerow({
                    "dataset": "example/dataset",
                    "dataset_row": "42",
                    "group_id": "source-42",
                    "sha256": "ABC123",
                })

            rows, groups, hashes, files = MODULE.load_excluded_provenance([path])

        self.assertEqual(rows, {("example/dataset", 42)})
        self.assertEqual(groups, {"source-42"})
        self.assertEqual(hashes, {"abc123"})
        self.assertEqual(files, [str(path)])


if __name__ == "__main__":
    unittest.main()

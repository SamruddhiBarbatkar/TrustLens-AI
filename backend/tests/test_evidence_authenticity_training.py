import csv
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from scripts.train_evidence_authenticity_streaming import (
    CLASS_NAMES,
    TAMPER_DATASET,
    group_partition,
    load_excluded_groups,
    source_group,
)


class EvidenceAuthenticityTrainingTests(unittest.TestCase):
    def test_class_contract_is_stable(self):
        self.assertEqual(
            CLASS_NAMES,
            {0: "AUTHENTIC", 1: "TAMPERED", 2: "SYNTHETIC"},
        )

    def test_original_and_manipulation_share_partition(self):
        original = source_group("opensdid_real_000176212.jpg")
        manipulated = source_group("opensdid_Flux.1_000176212.jpg")
        self.assertEqual(original, manipulated)
        self.assertEqual(
            group_partition(original, 2026, 0.18),
            group_partition(manipulated, 2026, 0.18),
        )

    def test_multiple_audit_provenance_files_are_combined(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index, source_id in enumerate(
                ("cocoglide_101762", "cocoglide_202329"),
                start=1,
            ):
                path = Path(directory) / f"audit_{index}.csv"
                with path.open("w", encoding="utf-8", newline="") as output:
                    writer = csv.DictWriter(
                        output,
                        fieldnames=["dataset", "source_id"],
                    )
                    writer.writeheader()
                    writer.writerow({
                        "dataset": TAMPER_DATASET,
                        "source_id": source_id,
                    })
                paths.append(path)
            excluded, files = load_excluded_groups(paths)
            self.assertEqual(
                excluded,
                {"cocoglide-101762", "cocoglide-202329"},
            )
            self.assertEqual(len(files), 2)


if __name__ == "__main__":
    unittest.main()

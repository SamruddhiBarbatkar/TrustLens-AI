import csv
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from scripts.train_tampering_detector_streaming import (
    DATASET_NAME,
    group_partition,
    load_excluded_groups,
    source_group,
)


class TamperingRetrainingTests(unittest.TestCase):
    def test_source_group_keeps_original_and_manipulation_together(self):
        pairs = [
            (
                "sagid_coco_000000000110_brushnet_epicrealism_1_Blended",
                "sagid_real_000000000110",
            ),
            ("cocoglide_101762", "cocoglide_real_101762"),
            (
                "opensdid_Flux.1_000176212.jpg",
                "opensdid_real_000176212.jpg",
            ),
        ]
        for manipulated, authentic in pairs:
            self.assertEqual(source_group(manipulated), source_group(authentic))

    def test_group_partition_is_deterministic(self):
        group = "opensdid-176212"
        self.assertEqual(
            group_partition(group, seed=2026, validation_fraction=0.18),
            group_partition(group, seed=2026, validation_fraction=0.18),
        )
        self.assertIn(
            group_partition(group, seed=2026, validation_fraction=0.18),
            {"train", "validation"},
        )

    def test_exclusion_loader_uses_only_matching_dataset_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            provenance = Path(directory) / "provenance.csv"
            with provenance.open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(
                    output,
                    fieldnames=["dataset", "source_id"],
                )
                writer.writeheader()
                writer.writerow({
                    "dataset": DATASET_NAME,
                    "source_id": "cocoglide_101762",
                })
                writer.writerow({
                    "dataset": "unrelated",
                    "source_id": "cocoglide_999999",
                })
            self.assertEqual(
                load_excluded_groups(provenance),
                {"cocoglide-101762"},
            )


if __name__ == "__main__":
    unittest.main()

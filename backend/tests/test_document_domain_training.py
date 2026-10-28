import csv
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_document_domain_pack import select_rows
from scripts.train_document_domain_head import development_partition, extract, read_manifest


def _row(index, label, tier="C2"):
    return {
        "row_idx": index,
        "row": {
            "id": f"kriyam_{index:04d}",
            "tier": tier,
            "is_authentic": not bool(label),
            "image": {
                "src": "https://huggingface.co/datasets/kriyam-ai/kriyam-tamperflow/resolve/923669c2a7af148da9e1f62ea56ac5f0308af322/images/test.png"
            },
        },
    }


class DocumentDomainTests(unittest.TestCase):
    def test_document_selection_is_balanced_and_source_disjoint(self):
        rows = []
        for index in range(20):
            rows.append(_row(index, index % 2))
            rows.append(_row(index, index % 2, "C4"))
        chosen = select_rows(rows, {"train": 5, "validation": 2, "test": 2}, 17)
        self.assertEqual(len(chosen), 18)
        self.assertEqual(len({item["row"]["id"] for item, _, _ in chosen}), 18)
        self.assertEqual({item["row"]["tier"] for item, _, _ in chosen}, {"C2"})
        for chosen_split, quota in (("train", 5), ("validation", 2), ("test", 2)):
            for chosen_label in (0, 1):
                self.assertEqual(sum(split == chosen_split and label == chosen_label
                                     for _, split, label in chosen), quota)

    def test_training_reader_rejects_source_leakage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.csv"
            provenance = root / "provenance.csv"
            rows = [
                {"sample_id": "a", "group_id": "same", "split": "train", "label": "0", "file_path": "a.jpg"},
                {"sample_id": "b", "group_id": "same", "split": "validation", "label": "1", "file_path": "b.jpg"},
                {"sample_id": "c", "group_id": "other", "split": "test", "label": "0", "file_path": "c.jpg"},
            ]
            for path, columns in ((manifest, rows[0].keys()), (provenance, ("sample_id", "group_id"))):
                with path.open("w", encoding="utf-8", newline="") as output:
                    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "crossed partitions"):
                read_manifest(manifest, provenance)

    def test_development_carve_is_source_disjoint(self):
        rows = [{"sample_id": str(index), "group_id": str(index), "split": "train",
                 "label": str(index % 2)} for index in range(40)]
        training, development = development_partition(rows, 23)
        self.assertEqual(len(training), 32)
        self.assertEqual(len(development), 8)
        self.assertTrue({row["group_id"] for row in training}.isdisjoint(
            {row["group_id"] for row in development}
        ))

    def test_feature_extraction_rejects_sealed_test_before_file_read(self):
        row = {"sample_id": "sealed", "group_id": "g", "split": "test",
               "label": "1", "file_path": "does-not-exist.jpg"}
        with self.assertRaisesRegex(ValueError, "Sealed test images"):
            extract(None, [row], {}, Path("manifest.csv"))

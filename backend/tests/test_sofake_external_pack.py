import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.prepare_sofake_external_pack import (
    assigned_split,
    prepare,
    selected_manifest_row,
    source_group,
)


class SoFakeExternalPackTests(unittest.TestCase):
    def test_grouping_keeps_generated_variant_with_source(self):
        self.assertEqual(source_group("camera_generated.png"), source_group("camera.jpg"))
        self.assertEqual(assigned_split(source_group("camera.jpg"), 42),
                         assigned_split(source_group("camera_generated.png"), 42))

    def test_manifest_assigns_detector_targets_by_kind(self):
        tampered = selected_manifest_row("s1", "g1", "test", "tampered", "image.jpg")
        synthetic = selected_manifest_row("s2", "g2", "test", "synthetic", "image.jpg")
        self.assertEqual((tampered["claim_label"], tampered["tampering_label"], tampered["ai_generation_label"]), (1, 1, 0))
        self.assertEqual((synthetic["claim_label"], synthetic["tampering_label"], synthetic["ai_generation_label"]), (1, 0, 1))

    def test_prepare_builds_balanced_disjoint_manifest_under_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = 42
            rows = []
            images = {}
            index = 0
            for split in ("validation", "test"):
                for label in ("real", "tampered", "full_synthetic"):
                    while True:
                        filename = f"image-{index}.png"
                        if assigned_split(source_group(filename), seed) == split:
                            break
                        index += 1
                    output = io.BytesIO()
                    Image.new("RGB", (256, 256), ((index * 37) % 255, 40, 80)).save(output, format="JPEG")
                    url = f"https://datasets-server.huggingface.co/cached-assets/test/--/revision/--/image-{index}.jpg"
                    images[url] = output.getvalue()
                    rows.append({"row_idx": index, "row": {
                        "label": label, "filename": filename, "generator": "example",
                        "image": {"src": url},
                    }})
                    index += 1
            args = SimpleNamespace(
                output_dir=root / "images", manifest=root / "manifest.csv",
                provenance=root / "provenance.csv", per_class_per_split=1,
                max_storage_mb=1, start_offset=0, max_scan_rows=100, seed=seed,
                exclude_row=[],
            )
            with (
                patch("scripts.prepare_sofake_external_pack.fetch_rows", return_value=rows),
                patch("scripts.prepare_sofake_external_pack.fetch_bytes", side_effect=images.__getitem__),
                patch("scripts.prepare_sofake_external_pack.load_excluded_provenance", return_value=(set(), set(), set(), [])),
            ):
                prepare(args)
            import csv
            with args.manifest.open(newline="", encoding="utf-8") as source:
                manifest = list(csv.DictReader(source))
            self.assertEqual(len(manifest), 6)
            self.assertEqual(len({row["group_id"] for row in manifest}), 6)
            self.assertEqual({row["split"] for row in manifest}, {"validation", "test"})
            self.assertTrue(all((args.manifest.parent / row["file_path"]).is_file() for row in manifest))


if __name__ == "__main__":
    unittest.main()

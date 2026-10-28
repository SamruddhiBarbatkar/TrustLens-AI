"""Build a bounded, disjoint So-Fake-Set image-level evaluation pack.

Only the dataset's validation split is sampled. The Hugging Face viewer serves
JPEG previews, so this pack tests the viewer-transcoded image domain rather
than the original encoded files. Never use this pack for detector training.
"""

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.prepare_compact_calibration_dataset import (
    fetch_bytes,
    fetch_rows,
    load_excluded_provenance,
)


DATASET = "saberzl/So-Fake-Set"
DATASET_CARD = "https://huggingface.co/datasets/saberzl/So-Fake-Set"
DATASET_SPLIT = "validation"
LABELS = {"real": "authentic", "tampered": "tampered", "full_synthetic": "synthetic"}
MANIFEST_COLUMNS = (
    "sample_id", "group_id", "split", "claim_label", "tampering_label",
    "ai_generation_label", "file_path",
)
PROVENANCE_COLUMNS = (
    "sample_id", "group_id", "split", "kind", "dataset", "dataset_split",
    "dataset_row", "source_filename", "generator", "viewer_revision",
    "delivery_format", "width", "height", "sha256", "stored_bytes",
)


def source_group(filename):
    stem = Path(filename).stem.lower()
    for ending in ("_generated", "_fake", "_tampered", "_real", "_original"):
        if stem.endswith(ending):
            stem = stem[: -len(ending)]
            break
    return f"sofake-{stem}"


def assigned_split(group_id, seed):
    digest = hashlib.sha256(f"{seed}:{group_id}".encode("utf-8")).digest()
    return "validation" if digest[0] % 2 == 0 else "test"


def inspect_jpeg(data):
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "JPEG":
            raise ValueError("Dataset viewer did not return a JPEG preview.")
        width, height = image.size
        image.verify()
    if min(width, height) < 128:
        raise ValueError("Dataset viewer image is too small for evaluation.")
    return width, height


def selected_manifest_row(sample_id, group_id, split, kind, file_path):
    tampered = int(kind == "tampered")
    synthetic = int(kind == "synthetic")
    return {
        "sample_id": sample_id,
        "group_id": group_id,
        "split": split,
        "claim_label": int(tampered or synthetic),
        "tampering_label": tampered,
        "ai_generation_label": synthetic,
        "file_path": file_path,
    }


def prepare(args):
    if args.per_class_per_split < 1:
        raise ValueError("per-class-per-split must be positive.")
    output_dir = args.output_dir.resolve()
    calibration_dir = BACKEND_DIR / "calibration"
    metadata_path = args.provenance.with_suffix(".json")
    excluded_inspected_rows = set(args.exclude_row)
    if metadata_path.is_file():
        previous_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        excluded_inspected_rows.update(previous_metadata.get("selection", {}).get("excluded_inspected_rows", []))
    excluded_paths = sorted(calibration_dir.glob("*provenance.csv"))
    excluded_paths = [path for path in excluded_paths if path.resolve() != args.provenance.resolve()]
    excluded_rows, excluded_groups, excluded_hashes, exclusions = load_excluded_provenance(excluded_paths)

    prior_by_row = {}
    if args.provenance.is_file():
        with args.provenance.open("r", encoding="utf-8-sig", newline="") as source:
            prior_by_row = {int(row["dataset_row"]): row for row in csv.DictReader(source)}

    counts = Counter()
    manifest = []
    provenance = []
    seen_groups = set()
    seen_hashes = set()
    stored_bytes = 0
    scanned = 0
    target = args.per_class_per_split
    for offset in range(args.start_offset, args.start_offset + args.max_scan_rows, 100):
        batch = fetch_rows(DATASET, "default", DATASET_SPLIT, offset, 100)
        if not batch:
            break
        for item in batch:
            scanned += 1
            row = item["row"]
            kind = LABELS.get(str(row.get("label", "")).lower())
            filename = str(row.get("filename") or "").strip()
            image = row.get("image") or {}
            image_url = image.get("src") if isinstance(image, dict) else None
            if not kind or not filename or not image_url:
                continue
            row_index = int(item["row_idx"])
            group_id = source_group(filename)
            split = assigned_split(group_id, args.seed)
            if (
                counts[(split, kind)] >= target
                or row_index in excluded_inspected_rows
                or group_id in seen_groups
                or group_id in excluded_groups
                or (DATASET, row_index) in excluded_rows
            ):
                continue
            parsed_url = urlparse(image_url)
            if parsed_url.scheme != "https" or parsed_url.hostname != "datasets-server.huggingface.co":
                raise ValueError("Unexpected dataset image host.")
            revision_parts = parsed_url.path.split("/--/")
            viewer_revision = revision_parts[1].split("/")[0] if len(revision_parts) > 1 else "unknown"
            destination = output_dir / "images" / kind / f"sofake-{row_index:08d}.jpg"
            previous = prior_by_row.get(row_index)
            if destination.is_file() and previous:
                if (
                    previous["source_filename"] != filename
                    or previous["kind"] != kind
                    or previous["viewer_revision"] != viewer_revision
                ):
                    raise ValueError(f"Dataset row changed since previous run: {row_index}")
                data = destination.read_bytes()
                if hashlib.sha256(data).hexdigest() != previous["sha256"]:
                    raise ValueError(f"Cached image hash changed: {destination}")
            else:
                data = fetch_bytes(image_url)
            width, height = inspect_jpeg(data)
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen_hashes or digest in excluded_hashes:
                continue
            if stored_bytes + len(data) > args.max_storage_mb * 1024 * 1024:
                raise RuntimeError("Storage cap reached before all class/split targets were filled.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if previous is None or not destination.is_file():
                destination.write_bytes(data)
            stored_bytes += len(data)
            seen_groups.add(group_id)
            seen_hashes.add(digest)
            counts[(split, kind)] += 1
            sample_id = f"sofake-{row_index:08d}"
            relative_path = destination.relative_to(args.manifest.parent.resolve()).as_posix() if destination.is_relative_to(args.manifest.parent.resolve()) else str(destination)
            manifest.append(selected_manifest_row(sample_id, group_id, split, kind, relative_path))
            provenance.append({
                "sample_id": sample_id,
                "group_id": group_id,
                "split": split,
                "kind": kind,
                "dataset": DATASET,
                "dataset_split": DATASET_SPLIT,
                "dataset_row": row_index,
                "source_filename": filename,
                "generator": row.get("generator") or "",
                "viewer_revision": viewer_revision,
                "delivery_format": "HUGGING_FACE_VIEWER_JPEG",
                "width": width,
                "height": height,
                "sha256": digest,
                "stored_bytes": len(data),
            })
            if all(counts[(s, k)] >= target for s in ("validation", "test") for k in LABELS.values()):
                break
        print(f"Scanned {scanned} rows; selected {len(manifest)} images", flush=True)
        if all(counts[(s, k)] >= target for s in ("validation", "test") for k in LABELS.values()):
            break
    if not all(counts[(s, k)] >= target for s in ("validation", "test") for k in LABELS.values()):
        raise RuntimeError(f"Could not fill balanced class/split targets: {dict(counts)}")

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    for path, columns, rows in (
        (args.manifest, MANIFEST_COLUMNS, manifest),
        (args.provenance, PROVENANCE_COLUMNS, provenance),
    ):
        with path.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": DATASET,
        "dataset_card": DATASET_CARD,
        "dataset_split": DATASET_SPLIT,
        "license": "CC-BY-4.0 per dataset card; verify underlying source rights before redistribution",
        "delivery_format": "HUGGING_FACE_VIEWER_JPEG",
        "delivery_limitation": "Viewer-transcoded JPEG previews may alter forensic compression traces.",
        "selection": {"seed": args.seed, "start_offset": args.start_offset, "scanned_rows": scanned, "per_class_per_split": target, "excluded_inspected_rows": sorted(excluded_inspected_rows)},
        "counts": {f"{split}_{kind}": counts[(split, kind)] for split in ("validation", "test") for kind in LABELS.values()},
        "stored_bytes": stored_bytes,
        "excluded_provenance": exclusions,
        "manifest": str(args.manifest),
        "provenance": str(args.provenance),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(args.manifest), "provenance": str(args.provenance), "metadata": str(metadata_path), "counts": metadata["counts"], "stored_mb": round(stored_bytes / 1024**2, 2)}, indent=2))


def main():
    calibration = BACKEND_DIR / "calibration"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=calibration / "sofake_external_data")
    parser.add_argument("--manifest", type=Path, default=calibration / "sofake_external_manifest.csv")
    parser.add_argument("--provenance", type=Path, default=calibration / "sofake_external_provenance.csv")
    parser.add_argument("--per-class-per-split", type=int, default=20)
    parser.add_argument("--max-storage-mb", type=int, default=100)
    parser.add_argument("--start-offset", type=int, default=0)
    parser.add_argument("--max-scan-rows", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=20261028)
    parser.add_argument("--exclude-row", type=int, action="append", default=[], help="Exclude any row inspected before the test partition was sealed.")
    args = parser.parse_args()
    prepare(args)


if __name__ == "__main__":
    main()

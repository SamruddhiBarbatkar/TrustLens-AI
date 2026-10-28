"""Prepare a small, source-disjoint academic document-tampering experiment.

Kriyam TamperFlow is CC BY-NC 4.0. This script stores resized derivatives
for image-level research only; they cannot measure original-format forensic
traces. No source ID is allowed in more than one partition. The test partition
is reserved and must not be passed to model selection or training.
"""

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageOps

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.prepare_compact_calibration_dataset import fetch_bytes

DATASET = "kriyam-ai/kriyam-tamperflow"
SOURCE_SPLIT = "train"
SOURCE_TIER = "C2"
REVISION = "923669c2a7af148da9e1f62ea56ac5f0308af322"
MANIFEST_COLUMNS = ("sample_id", "group_id", "split", "label", "file_path")
PROVENANCE_COLUMNS = (
    "sample_id", "group_id", "split", "label", "dataset", "source_split",
    "source_row", "source_id", "tier", "tamper_types", "source_sha256",
    "stored_sha256", "source_bytes", "stored_bytes", "width", "height",
)


def select_rows(rows, quotas, seed):
    """Select one fixed tier per source and partition disjoint source IDs."""
    by_id = {}
    for item in rows:
        row = item["row"]
        if row.get("tier") != SOURCE_TIER:
            continue
        source_id = str(row.get("id") or "")
        if not source_id or source_id in by_id or type(row.get("is_authentic")) is not bool:
            continue
        image = row.get("image") or {}
        url = image.get("src") if isinstance(image, dict) else None
        if not url:
            continue
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "huggingface.co":
            raise ValueError("Unexpected image URL host.")
        if f"/resolve/{REVISION}/images/" not in parsed.path:
            raise ValueError("Dataset revision changed; pin and audit the new source.")
        by_id[source_id] = item

    counts = Counter()
    selected = []
    order = sorted(
        by_id.values(),
        key=lambda item: hashlib.sha256(
            f"{seed}:{item['row']['id']}".encode("utf-8")
        ).digest(),
    )
    for item in order:
        label = 0 if item["row"]["is_authentic"] else 1
        for split in ("train", "validation", "test"):
            if counts[(split, label)] < quotas[split]:
                selected.append((item, split, label))
                counts[(split, label)] += 1
                break
        if all(counts[(split, label)] == count
               for split, count in quotas.items() for label in (0, 1)):
            break
    missing = {
        f"{split}_{label}": count - counts[(split, label)]
        for split, count in quotas.items() for label in (0, 1)
        if counts[(split, label)] != count
    }
    if missing:
        raise ValueError(f"Not enough source-disjoint documents: {missing}")
    return selected


def fetch_and_store(item, split, label, output_dir, max_side):
    row = item["row"]
    source_id = row["id"]
    sample_id = f"{source_id}_{SOURCE_TIER}"
    destination = output_dir / "images" / split / f"{sample_id}.jpg"
    raw = fetch_bytes(row["image"]["src"])
    source_digest = hashlib.sha256(raw).hexdigest()
    with Image.open(io.BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        width, height = image.size
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=88, optimize=True)
    data = buffer.getvalue()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return {
        "sample_id": sample_id, "group_id": source_id, "split": split,
        "label": label, "file_path": str(destination), "dataset": DATASET,
        "source_split": SOURCE_SPLIT, "source_row": item["row_idx"],
        "source_id": source_id, "tier": SOURCE_TIER,
        "tamper_types": ",".join(row.get("tamper_types") or []),
        "source_sha256": source_digest,
        "stored_sha256": hashlib.sha256(data).hexdigest(),
        "source_bytes": len(raw), "stored_bytes": len(data),
        "width": width, "height": height,
    }


def prepare(args):
    quotas = {"train": args.train_per_class, "validation": args.validation_per_class,
              "test": args.test_per_class}
    if min(quotas.values()) < 1 or args.max_side < 224:
        raise ValueError("Quotas must be positive and max-side must be at least 224.")
    metadata_url = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/metadata.jsonl"
    if args.index_cache.is_file():
        metadata_bytes = args.index_cache.read_bytes()
    else:
        metadata_bytes = fetch_bytes(metadata_url)
        args.index_cache.parent.mkdir(parents=True, exist_ok=True)
        args.index_cache.write_bytes(metadata_bytes)
    source_rows = [json.loads(line) for line in metadata_bytes.splitlines() if line.strip()]
    if not source_rows or len(source_rows) > args.max_scan_rows:
        raise ValueError("Source metadata is empty or exceeds the explicit scan bound.")
    rows = []
    for index, row in enumerate(source_rows):
        filename = row.get("file_name")
        if not filename or not filename.startswith("images/") or ".." in Path(filename).parts:
            raise ValueError("Unexpected source image path in metadata.")
        row["image"] = {"src": f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{filename}"}
        rows.append({"row_idx": index, "row": row})
    print(f"Indexed {len(rows)} rows from pinned metadata.jsonl", flush=True)
    source_counts = dict(Counter(
        "authentic" if row["row"]["is_authentic"] else "tampered"
        for row in rows if row["row"].get("tier") == SOURCE_TIER
    ))
    selected = select_rows(rows, quotas, args.seed)
    output_dir = args.output_dir.resolve()
    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(fetch_and_store, *entry, output_dir, args.max_side)
                   for entry in selected]
        for future in as_completed(futures):
            records.append(future.result())
            if len(records) % 20 == 0:
                print(f"Stored {len(records)}/{len(selected)} documents", flush=True)
    records.sort(key=lambda row: (row["split"], row["sample_id"]))
    stored_bytes = sum(row["stored_bytes"] for row in records)
    if stored_bytes > args.max_storage_mb * 1024**2:
        raise RuntimeError("Stored derivatives exceed the configured storage cap.")
    if len({row["stored_sha256"] for row in records}) != len(records):
        raise ValueError("Duplicate stored images detected.")
    if len({row["group_id"] for row in records}) != len(records):
        raise ValueError("Source group appears in multiple partitions.")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    for path, columns, data in (
        (args.manifest, MANIFEST_COLUMNS, records),
        (args.provenance, PROVENANCE_COLUMNS, records),
    ):
        with path.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": DATASET, "revision": REVISION, "license": "CC-BY-NC-4.0",
        "use": "academic research only; no deployment or commercial training",
        "source_split": SOURCE_SPLIT, "source_tier": SOURCE_TIER,
        "stored_format": "resized JPEG derivatives",
        "limitation": "Downscaling/recompression destroys some original forensic traces.",
        "seed": args.seed, "quotas": quotas, "counts": dict(Counter(
            f"{row['split']}_{row['label']}" for row in records)),
        "available_c2_source_counts": source_counts,
        "card_count_discrepancy": "Pinned metadata has 69 authentic source IDs, while the dataset card states 350. Treat this as a small pilot, not a benchmark claim.",
        "source_metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
        "stored_bytes": stored_bytes, "max_side": args.max_side,
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "provenance_sha256": hashlib.sha256(args.provenance.read_bytes()).hexdigest(),
        "test_inference_status": "NOT_RUN",
    }
    args.metadata.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": metadata["counts"], "stored_mb": round(stored_bytes / 1024**2, 2)}, indent=2))


def main():
    calibration = BACKEND_DIR / "calibration"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=calibration / "document_domain_data")
    parser.add_argument("--manifest", type=Path, default=calibration / "document_domain_manifest.csv")
    parser.add_argument("--provenance", type=Path, default=calibration / "document_domain_provenance.csv")
    parser.add_argument("--metadata", type=Path, default=calibration / "document_domain_provenance.json")
    parser.add_argument("--index-cache", type=Path, default=calibration / "document_domain_metadata.jsonl")
    parser.add_argument("--train-per-class", type=int, default=40)
    parser.add_argument("--validation-per-class", type=int, default=14)
    parser.add_argument("--test-per-class", type=int, default=15)
    parser.add_argument("--max-side", type=int, default=768)
    parser.add_argument("--max-storage-mb", type=int, default=100)
    parser.add_argument("--max-scan-rows", type=int, default=3000)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261028)
    prepare(parser.parse_args())


if __name__ == "__main__":
    main()

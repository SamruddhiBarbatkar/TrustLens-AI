"""Build a storage-bounded, group-safe TrustLens calibration image pack.

The script downloads individual, labeled images through the Hugging Face
dataset viewer API. It never downloads the multi-gigabyte source archives.
The resulting media are for research evaluation and must not be redistributed.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from collections import Counter
from pathlib import Path

from PIL import Image


AI_DATASET = "TheKernel01/Tiny-GenImage"
AI_CONFIG = "default"
AI_SPLIT = "validation"
TAMPER_DATASET = "KhangTruong/Tampered-Images-Combined-Dataset"
TAMPER_CONFIG = "default"
TAMPER_SPLIT = "cross_test"
DATASET_API = "https://datasets-server.huggingface.co/rows"
SPLITS = ("calibration", "validation", "test")


def load_excluded_provenance(paths):
    """Load identities from prior packs so a fresh audit cannot reuse them."""

    excluded_rows = set()
    excluded_groups = set()
    excluded_hashes = set()
    files = []
    for path in paths or []:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Excluded provenance file not found: {path}")
        files.append(str(path))
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            required = {"dataset", "dataset_row", "group_id", "sha256"}
            missing = required.difference(reader.fieldnames or [])
            if missing:
                raise ValueError(
                    f"{path} is missing provenance columns: "
                    + ", ".join(sorted(missing))
                )
            for row in reader:
                excluded_rows.add((row["dataset"], int(row["dataset_row"])))
                if row["group_id"]:
                    excluded_groups.add(row["group_id"])
                if row["sha256"]:
                    excluded_hashes.add(row["sha256"].lower())
    return excluded_rows, excluded_groups, excluded_hashes, files


def retry_delay(error, attempt):
    """Use the server's backoff for throttling and a short exponential fallback."""
    if isinstance(error, HTTPError) and error.code == 429:
        retry_after = error.headers.get("Retry-After")
        if retry_after:
            try:
                return min(60, max(1, int(retry_after)))
            except ValueError:
                pass
        return min(60, 15 * (attempt + 1))
    return 2 ** attempt


def _rows_url(dataset, config, split, offset, length):
    query = urllib.parse.urlencode({
        "dataset": dataset,
        "config": config,
        "split": split,
        "offset": offset,
        "length": length,
    })
    return f"{DATASET_API}?{query}"


def fetch_rows(dataset, config, split, offset, length=100):
    url = _rows_url(dataset, config, split, offset, length)
    for attempt in range(6):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "TrustLens-Calibration/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)["rows"]
        except Exception as error:
            if attempt == 5:
                raise
            time.sleep(retry_delay(error, attempt))


def fetch_bytes(url):
    for attempt in range(6):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "TrustLens-Calibration/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except Exception as error:
            if attempt == 5:
                raise
            time.sleep(retry_delay(error, attempt))


def tamper_source_key(identifier):
    """Return a shared source key for supported real/tampered row pairs."""
    identifier = identifier.lower()
    patterns = (
        ("sagid", r"^sagid_(?:coco|real)_(\d+)"),
        ("cocoglide", r"^cocoglide_(?:real_)?(\d+)$"),
        ("opensdid", r"^opensdid_(?:real|flux\.1|sd1\.5|sdxl)_(\d+)\.jpg$"),
    )
    for prefix, pattern in patterns:
        match = re.match(pattern, identifier)
        if match:
            return f"{prefix}-{int(match.group(1))}"
    return None


def collect_tampered_images(
    target_count,
    block_shift=0,
    excluded_rows=frozenset(),
    excluded_groups=frozenset(),
):
    selected = []
    seen_groups = set()
    # Curated manipulated-only blocks provide generator diversity without
    # scanning or downloading the full 1.19 GB combined dataset.
    manipulated_offsets = [
        offset + block_shift
        for offset in (0, 2500, 5000, 6500)
    ]
    for offset in manipulated_offsets:
        rows = []
        for page_offset in (offset, offset + 100):
            rows.extend(fetch_rows(
                TAMPER_DATASET,
                TAMPER_CONFIG,
                TAMPER_SPLIT,
                page_offset,
                length=100,
            ))
        if not rows:
            break
        added_from_block = 0
        for item in rows:
            row = item["row"]
            if int(row["label"]) != 1:
                continue
            key = tamper_source_key(row["id"])
            group_id = f"tamper-{key}" if key else None
            row_identity = (TAMPER_DATASET, int(item["row_idx"]))
            if (
                key is None
                or key in seen_groups
                or group_id in excluded_groups
                or row_identity in excluded_rows
            ):
                continue
            seen_groups.add(key)
            selected.append({
                "source_group": key,
                "row_index": int(item["row_idx"]),
                **row,
            })
            added_from_block += 1
            if added_from_block >= 35:
                break
        if len(selected) >= target_count or len(rows) < 100:
            break
    if len(selected) < target_count:
        raise RuntimeError(
            f"Only {len(selected)} unique tampered images were available; "
            f"{target_count} are required."
        )
    return selected


def collect_genimage_images(
    target_count,
    label,
    start_offset=0,
    excluded_rows=frozenset(),
):
    selected = []
    offset = start_offset
    while len(selected) < target_count:
        rows = fetch_rows(AI_DATASET, AI_CONFIG, AI_SPLIT, offset)
        if not rows:
            break
        for item in rows:
            row = item["row"]
            row_identity = (AI_DATASET, int(item["row_idx"]))
            if int(row["label"]) == label and row_identity not in excluded_rows:
                selected.append({
                    "row_index": int(item["row_idx"]),
                    **row,
                })
                if len(selected) == target_count:
                    break
        offset += len(rows)
        if len(rows) < 100:
            break
    if len(selected) < target_count:
        class_name = "synthetic" if label == 1 else "authentic"
        raise RuntimeError(
            f"Only {len(selected)} {class_name} images were available; "
            f"{target_count} are required."
        )
    return selected


def save_image(source_url, destination, max_dimension, preserve_source=False):
    source_bytes = fetch_bytes(source_url)
    with Image.open(io.BytesIO(source_bytes)) as image:
        source_size = image.size
        destination.parent.mkdir(parents=True, exist_ok=True)
        if preserve_source:
            destination.write_bytes(source_bytes)
            normalized_size = source_size
        else:
            image = image.convert("RGB")
            image.thumbnail(
                (max_dimension, max_dimension),
                Image.Resampling.LANCZOS,
            )
            image.save(destination, format="JPEG", quality=90, optimize=True)
            normalized_size = image.size
    return {
        "source_width": source_size[0],
        "source_height": source_size[1],
        "normalized_width": normalized_size[0],
        "normalized_height": normalized_size[1],
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "stored_bytes": destination.stat().st_size,
    }


def manifest_row(sample_id, group_id, split, kind, relative_path):
    labels = {
        "authentic": (0, 0, 0),
        "tampered": (1, 1, 0),
        "synthetic": (1, 0, 1),
    }
    claim_label, tampering_label, ai_generation_label = labels[kind]
    return {
        "sample_id": sample_id,
        "group_id": group_id,
        "split": split,
        "claim_label": claim_label,
        "tampering_label": tampering_label,
        "ai_generation_label": ai_generation_label,
        "file_path": relative_path.as_posix(),
    }


def relative_manifest_path(destination, manifest):
    """Return a portable media path rooted at the manifest directory."""
    try:
        return Path(destination).resolve().relative_to(
            Path(manifest).parent.resolve()
        )
    except ValueError as error:
        raise ValueError(
            "The output directory must be inside the manifest directory "
            "so image paths remain portable."
        ) from error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("calibration/compact_data"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("calibration/compact_image_manifest.csv"),
    )
    parser.add_argument(
        "--provenance",
        type=Path,
        default=Path("calibration/compact_provenance.csv"),
    )
    parser.add_argument("--per-class", type=int, default=90)
    parser.add_argument("--max-dimension", type=int, default=512)
    parser.add_argument("--max-megabytes", type=int, default=250)
    parser.add_argument(
        "--genimage-start-offset",
        type=int,
        default=0,
        help="Start row for an independent Tiny-GenImage selection window.",
    )
    parser.add_argument(
        "--tamper-block-shift",
        type=int,
        default=0,
        help="Shift curated tampering source blocks for an independent pack.",
    )
    parser.add_argument(
        "--exclude-provenance",
        type=Path,
        action="append",
        default=[],
        help=(
            "Repeat for every earlier provenance CSV. Dataset rows, source "
            "groups, and image hashes from those packs are forbidden."
        ),
    )
    args = parser.parse_args()

    if args.per_class < 30 or args.per_class % len(SPLITS):
        parser.error("--per-class must be at least 30 and divisible by 3")
    if args.max_dimension < 224:
        parser.error("--max-dimension must be at least 224")
    if args.genimage_start_offset < 0 or args.tamper_block_shift < 0:
        parser.error("selection offsets cannot be negative")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error(
            f"Output directory is not empty: {args.output_dir}. "
            "Choose a new directory or remove the previous generated pack."
        )

    (
        excluded_rows,
        excluded_groups,
        excluded_hashes,
        exclusion_files,
    ) = load_excluded_provenance(args.exclude_provenance)

    authentic_images = collect_genimage_images(
        args.per_class,
        label=0,
        start_offset=args.genimage_start_offset,
        excluded_rows=excluded_rows,
    )
    tampered_images = collect_tampered_images(
        args.per_class + 10,
        block_shift=args.tamper_block_shift,
        excluded_rows=excluded_rows,
        excluded_groups=excluded_groups,
    )
    ai_images = collect_genimage_images(
        args.per_class,
        label=1,
        start_offset=args.genimage_start_offset,
        excluded_rows=excluded_rows,
    )
    image_dir = args.output_dir / "images"
    manifest_rows = []
    provenance_rows = []
    stored_bytes = 0
    maximum_bytes = args.max_megabytes * 1024 * 1024

    def store(
        row,
        sample_id,
        group_id,
        split,
        kind,
        dataset,
        details,
        preserve_source=False,
    ):
        nonlocal stored_bytes
        destination = image_dir / kind / f"{sample_id}.jpg"
        image_details = save_image(
            row["image"]["src"],
            destination,
            args.max_dimension,
            preserve_source=preserve_source,
        )
        if image_details["sha256"].lower() in excluded_hashes:
            destination.unlink(missing_ok=True)
            raise RuntimeError(
                "Fresh-audit image duplicates an excluded provenance hash: "
                f"{sample_id}. Choose a different selection offset."
            )
        stored_bytes += image_details["stored_bytes"]
        if stored_bytes > maximum_bytes:
            destination.unlink(missing_ok=True)
            raise RuntimeError(
                f"Storage cap of {args.max_megabytes} MB exceeded. "
                "Retry with a smaller --per-class or --max-dimension value."
            )
        relative_path = relative_manifest_path(destination, args.manifest)
        manifest_rows.append(manifest_row(
            sample_id,
            group_id,
            split,
            kind,
            relative_path,
        ))
        provenance_rows.append({
            "sample_id": sample_id,
            "group_id": group_id,
            "split": split,
            "kind": kind,
            "dataset": dataset,
            "dataset_split": details.pop("dataset_split"),
            "dataset_row": row["row_index"],
            "source_id": row.get("id", ""),
            "source_category": details.pop("source_category", ""),
            "source_method": details.pop("source_method", ""),
            **image_details,
        })
        return destination, image_details

    for index, row in enumerate(authentic_images):
        split = SPLITS[index % len(SPLITS)]
        sample_id = f"authentic-{index + 1:03d}"
        store(
            row,
            sample_id,
            f"authentic-tiny-genimage-{row['row_index']}",
            split,
            "authentic",
            AI_DATASET,
            {
                "dataset_split": AI_SPLIT,
                "source_category": row.get("generator", ""),
                "source_method": "natural",
            },
        )

    accepted_tampered = 0
    seen_tampered_hashes = set()
    for row in tampered_images:
        if accepted_tampered >= args.per_class:
            break
        split = SPLITS[accepted_tampered % len(SPLITS)]
        sample_id = f"tampered-{accepted_tampered + 1:03d}"
        path, details = store(
            row,
            sample_id,
            f"tamper-{row['source_group']}",
            split,
            "tampered",
            TAMPER_DATASET,
            {
                "dataset_split": TAMPER_SPLIT,
                "source_category": row.get("dataset", ""),
                "source_method": row.get("method", ""),
            },
            preserve_source=True,
        )
        if details["sha256"] in seen_tampered_hashes:
            path.unlink(missing_ok=True)
            stored_bytes -= details["stored_bytes"]
            manifest_rows.pop()
            provenance_rows.pop()
            continue
        seen_tampered_hashes.add(details["sha256"])
        accepted_tampered += 1

    if accepted_tampered < args.per_class:
        raise RuntimeError(
            f"Only {accepted_tampered} unique tampered images "
            f"were available; {args.per_class} are required."
        )

    for index, row in enumerate(ai_images):
        split = SPLITS[index % len(SPLITS)]
        sample_id = f"synthetic-{index + 1:03d}"
        store(
            row,
            sample_id,
            f"synthetic-tiny-genimage-{row['row_index']}",
            split,
            "synthetic",
            AI_DATASET,
            {
                "dataset_split": AI_SPLIT,
                "source_category": row.get("generator", ""),
                "source_method": "full_generation",
            },
        )

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=[
            "sample_id",
            "group_id",
            "split",
            "claim_label",
            "tampering_label",
            "ai_generation_label",
            "file_path",
        ])
        writer.writeheader()
        writer.writerows(manifest_rows)

    with args.provenance.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(provenance_rows[0]))
        writer.writeheader()
        writer.writerows(provenance_rows)

    summary = {
        "images": len(manifest_rows),
        "stored_megabytes": round(stored_bytes / 1024 / 1024, 2),
        "classes": dict(Counter(row["kind"] for row in provenance_rows)),
        "splits": dict(Counter(row["split"] for row in manifest_rows)),
        "manifest": str(args.manifest),
        "provenance": str(args.provenance),
        "selection": {
            "genimage_start_offset": args.genimage_start_offset,
            "tamper_block_shift": args.tamper_block_shift,
            "excluded_provenance": exclusion_files,
            "excluded_dataset_rows": len(excluded_rows),
            "excluded_source_groups": len(excluded_groups),
            "excluded_hashes": len(excluded_hashes),
        },
        "license_notice": "Research evaluation only; do not redistribute media.",
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Download interrupted.", file=sys.stderr)
        raise SystemExit(130)

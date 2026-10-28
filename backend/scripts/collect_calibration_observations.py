"""Run TrustLens detectors over a labeled manifest for calibration."""

import argparse
import csv
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.analysis.image_quality import analyze_image_quality
from app.analysis.quality_gate import evaluate_quality_gate
from app.ml.ai_generation_model import AIGenerationModel, get_ai_generation_model
from app.ml.evidence_authenticity_model import EvidenceAuthenticityModel
from app.ml.tampering_model import TamperingDetectionModel, get_tampering_model


MANIFEST_COLUMNS = {
    "sample_id",
    "group_id",
    "split",
    "claim_label",
    "tampering_label",
    "ai_generation_label",
    "file_path",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split",
        choices=("calibration", "validation", "test", "all"),
        default="all",
        help="Collect one partition at a time to keep a future test split unseen during policy tuning.",
    )
    parser.add_argument(
        "--ai-model-path",
        type=Path,
        help="Evaluate a candidate checkpoint without replacing the deployed model.",
    )
    parser.add_argument(
        "--tampering-model-path",
        type=Path,
        help="Evaluate a tampering candidate without replacing the deployed model.",
    )
    parser.add_argument(
        "--multiclass-model-path",
        type=Path,
        help=(
            "Evaluate one three-class checkpoint as both the tampering and "
            "AI-generation detector without replacing deployed models."
        ),
    )
    parser.add_argument(
        "--multiclass-tampering-model-path",
        type=Path,
        help=(
            "Use a three-class checkpoint only for tampering while the "
            "AI-generation branch uses --ai-model-path."
        ),
    )
    parser.add_argument(
        "--tampering-inference",
        choices=("single", "multiview"),
        default="single",
        help=(
            "Use the validated single global view or collect the separately "
            "versioned global-plus-patch tampering candidate."
        ),
    )
    args = parser.parse_args()
    if args.multiclass_model_path and (
        args.ai_model_path
        or args.tampering_model_path
        or args.multiclass_tampering_model_path
    ):
        parser.error(
            "--multiclass-model-path cannot be combined with separate "
            "--ai-model-path or --tampering-model-path values."
        )
    if args.multiclass_tampering_model_path and args.tampering_model_path:
        parser.error(
            "--multiclass-tampering-model-path cannot be combined with "
            "--tampering-model-path."
        )

    with args.manifest_csv.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = MANIFEST_COLUMNS.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "Manifest is missing columns: " + ", ".join(sorted(missing))
            )
        manifest = [
            row for row in reader
            if args.split == "all" or row["split"].strip().lower() == args.split
        ]
    if not manifest:
        raise ValueError(f"No manifest rows matched split {args.split!r}.")

    shared_model = (
        EvidenceAuthenticityModel(args.multiclass_model_path)
        if args.multiclass_model_path
        else None
    )
    tampering_model = shared_model
    if tampering_model is None and args.multiclass_tampering_model_path:
        tampering_model = EvidenceAuthenticityModel(
            args.multiclass_tampering_model_path
        )
    if tampering_model is None:
        tampering_model = (
            TamperingDetectionModel(args.tampering_model_path)
            if args.tampering_model_path
            else get_tampering_model()
        )
    ai_model = shared_model or (
        AIGenerationModel(args.ai_model_path)
        if args.ai_model_path
        else get_ai_generation_model()
    )
    if args.tampering_inference == "multiview" and not hasattr(
        tampering_model,
        "predict_multiview",
    ):
        parser.error(
            "--tampering-inference multiview requires a three-class "
            "EfficientNet supplied with --multiclass-model-path or "
            "--multiclass-tampering-model-path."
        )
    tampering_model_version = tampering_model.model_version
    if args.tampering_inference == "multiview":
        tampering_model_version += "-multiview-v1"
    model_metadata = {
        "TAMPERING_DETECTION": {
            "model_version": tampering_model_version,
            "model_sha256": hashlib.sha256(
                tampering_model.model_path.read_bytes()
            ).hexdigest(),
        },
        "AI_GENERATION": {
            "model_version": ai_model.model_version,
            "model_sha256": hashlib.sha256(
                ai_model.model_path.read_bytes()
            ).hexdigest(),
        },
    }
    observations = []

    for index, item in enumerate(manifest, start=1):
        image_path = Path(item["file_path"])
        if not image_path.is_absolute():
            image_path = (args.manifest_csv.parent / image_path).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"Calibration image not found: {image_path}")

        labels = {
            "claim_label": int(item["claim_label"]),
            "tampering_label": int(item["tampering_label"]),
            "ai_generation_label": int(item["ai_generation_label"]),
        }
        if any(label not in {0, 1} for label in labels.values()):
            raise ValueError(f"Labels must be 0 or 1 for {item['sample_id']}.")
        if item["split"].lower() not in {"calibration", "validation", "test"}:
            raise ValueError(f"Invalid split for {item['sample_id']}.")

        evidence = SimpleNamespace(id=index, file_path=str(image_path))
        quality_output = analyze_image_quality(evidence)
        quality_gate = evaluate_quality_gate(
            quality_output.get("result"),
            evidence_id=index,
        )
        quality_status = (quality_gate.get("result") or {}).get(
            "quality_status",
            "UNKNOWN",
        )

        tampering = (
            tampering_model.predict_multiview(image_path)
            if args.tampering_inference == "multiview"
            else tampering_model.predict(image_path)
        )
        synthetic = (
            shared_model.predict(image_path)
            if shared_model is not None
            else ai_model.predict(image_path)
        )
        common = {
            "sample_id": item["sample_id"],
            "group_id": item["group_id"],
            "split": item["split"].lower(),
            "claim_label": labels["claim_label"],
            "quality_status": quality_status,
        }
        observations.extend([
            {
                "detector": "TAMPERING_DETECTION",
                **model_metadata["TAMPERING_DETECTION"],
                **common,
                "detector_label": labels["tampering_label"],
                "raw_probability": tampering["tampered_probability"],
            },
            {
                "detector": "AI_GENERATION",
                **model_metadata["AI_GENERATION"],
                **common,
                "detector_label": labels["ai_generation_label"],
                "raw_probability": synthetic["ai_generated_probability"],
            },
        ])
        if index % 10 == 0 or index == len(manifest):
            print(f"Evaluated {index}/{len(manifest)} images", flush=True)

    fieldnames = [
        "detector",
        "model_version",
        "model_sha256",
        "sample_id",
        "group_id",
        "split",
        "detector_label",
        "claim_label",
        "raw_probability",
        "quality_status",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(observations)
    print(f"Wrote {len(observations)} detector observations: {args.output}")


if __name__ == "__main__":
    main()

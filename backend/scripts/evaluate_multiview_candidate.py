"""Compare single-view and global-plus-patch inference on a held-out manifest."""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ml.evidence_authenticity_model import EvidenceAuthenticityModel
from app.analysis.calibration_training import calibration_metrics


REQUIRED_COLUMNS = {
    "sample_id",
    "group_id",
    "split",
    "claim_label",
    "tampering_label",
    "ai_generation_label",
    "file_path",
}


def binary_metrics(labels, probabilities):
    rows = [
        {"label": int(label), "raw_probability": float(probability)}
        for label, probability in zip(labels, probabilities)
    ]
    return calibration_metrics(rows)


def multiclass_metrics(labels, predictions, class_count=3):
    accuracy = sum(
        label == prediction
        for label, prediction in zip(labels, predictions)
    ) / len(labels)
    f1_scores = []
    confusion = [[0 for _ in range(class_count)] for _ in range(class_count)]
    for label, prediction in zip(labels, predictions):
        confusion[label][prediction] += 1
    for class_index in range(class_count):
        true_positive = confusion[class_index][class_index]
        false_positive = sum(
            confusion[row][class_index]
            for row in range(class_count)
            if row != class_index
        )
        false_negative = sum(
            confusion[class_index][column]
            for column in range(class_count)
            if column != class_index
        )
        denominator = 2 * true_positive + false_positive + false_negative
        f1_scores.append(
            (2 * true_positive / denominator) if denominator else 0.0
        )
    return {
        "accuracy": round(accuracy, 8),
        "macro_f1": round(sum(f1_scores) / class_count, 8),
        "confusion_matrix": confusion,
    }


def strategy_metrics(rows, prefix):
    class_labels = [row["class_label"] for row in rows]
    predictions = [row[f"{prefix}_prediction_index"] for row in rows]
    tampering_labels = [row["tampering_label"] for row in rows]
    tampering_probabilities = [
        row[f"{prefix}_tampered_probability"] for row in rows
    ]
    claim_labels = [row["claim_label"] for row in rows]
    suspicious_probabilities = [
        1.0 - row[f"{prefix}_authentic_probability"] for row in rows
    ]
    return {
        "three_class": multiclass_metrics(class_labels, predictions),
        "tampering_branch": binary_metrics(
            tampering_labels,
            tampering_probabilities,
        ),
        "any_suspicious_content": binary_metrics(
            claim_labels,
            suspicious_probabilities,
        ),
    }


def numeric_delta(candidate, baseline):
    result = {}
    for key, value in candidate.items():
        baseline_value = baseline.get(key)
        if isinstance(value, dict) and isinstance(baseline_value, dict):
            result[key] = numeric_delta(value, baseline_value)
        elif (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and isinstance(baseline_value, (int, float))
            and not isinstance(baseline_value, bool)
        ):
            result[key] = value - baseline_value
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest_csv", type=Path)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--predictions-output", type=Path)
    parser.add_argument(
        "--split",
        choices=("calibration", "validation", "test", "all"),
        default="test",
    )
    args = parser.parse_args()

    with args.manifest_csv.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "Manifest is missing columns: " + ", ".join(sorted(missing))
            )
        manifest = [
            row for row in reader
            if args.split == "all" or row["split"].lower() == args.split
        ]
    if not manifest:
        raise ValueError(f"No manifest rows matched split {args.split!r}.")

    model = EvidenceAuthenticityModel(args.model_path)
    rows = []
    for index, item in enumerate(manifest, start=1):
        image_path = Path(item["file_path"])
        if not image_path.is_absolute():
            image_path = (args.manifest_csv.parent / image_path).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"Evaluation image not found: {image_path}")

        tampering_label = int(item["tampering_label"])
        ai_label = int(item["ai_generation_label"])
        if tampering_label and ai_label:
            raise ValueError(
                f"Sample {item['sample_id']} cannot be both locally tampered "
                "and fully synthetic in the three-class evaluation."
            )
        class_label = 2 if ai_label else (1 if tampering_label else 0)
        single = model.predict(image_path)
        multiview = model.predict_multiview(image_path)
        rows.append({
            "sample_id": item["sample_id"],
            "group_id": item["group_id"],
            "split": item["split"].lower(),
            "claim_label": int(item["claim_label"]),
            "tampering_label": tampering_label,
            "ai_generation_label": ai_label,
            "class_label": class_label,
            "single_prediction_index": single["predicted_class_index"],
            "single_authentic_probability": single["authentic_probability"],
            "single_tampered_probability": single["tampered_probability"],
            "single_ai_probability": single["ai_generated_probability"],
            "multiview_prediction_index": multiview["predicted_class_index"],
            "multiview_authentic_probability": multiview["authentic_probability"],
            "multiview_tampered_probability": multiview["tampered_probability"],
            "multiview_ai_probability": multiview["ai_generated_probability"],
        })
        print(f"Evaluated {index}/{len(manifest)}: {item['sample_id']}")

    baseline = strategy_metrics(rows, "single")
    candidate = strategy_metrics(rows, "multiview")
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_split": args.split,
        "sample_count": len(rows),
        "checkpoint": str(args.model_path),
        "checkpoint_sha256": model.checkpoint_sha256,
        "baseline_model_version": model.model_version,
        "candidate_model_version": f"{model.model_version}-multiview-v1",
        "candidate_inference_strategy": "GLOBAL_PLUS_FIVE_PATCHES_MEAN_V1",
        "single_view": baseline,
        "multiview_candidate": candidate,
        "candidate_minus_single": numeric_delta(candidate, baseline),
        "promotion_status": "RESEARCH_ONLY_REQUIRES_EXTERNAL_CALIBRATION",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    predictions_output = args.predictions_output or args.output.with_name(
        args.output.stem + "_predictions.csv"
    )
    predictions_output.parent.mkdir(parents=True, exist_ok=True)
    with predictions_output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Comparison report: {args.output}")
    print(f"Per-image predictions: {predictions_output}")
    print("The candidate remains excluded from the Trust Score until recalibrated.")


if __name__ == "__main__":
    main()

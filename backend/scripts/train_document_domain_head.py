"""Train a research-only document tampering head on disjoint source groups.

The active EfficientNet backbone is frozen. A train-only development carve-out
selects the epoch and calibrates temperature; the validation partition is
loaded once after training. The reserved test images are never opened here.
"""

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import torch
from PIL import Image
from torch import nn

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analysis.calibration_training import calibration_metrics, fit_temperature
from app.ml.evidence_authenticity_model import EvidenceAuthenticityModel


def read_manifest(manifest_path, provenance_path):
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    with provenance_path.open("r", encoding="utf-8-sig", newline="") as source:
        provenance = {row["sample_id"]: row for row in csv.DictReader(source)}
    if not rows or {row["split"] for row in rows} != {"train", "validation", "test"}:
        raise ValueError("Expected train, validation, and sealed test partitions.")
    if len({row["sample_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate sample IDs in document manifest.")
    group_splits = defaultdict(set)
    for row in rows:
        if int(row["label"]) not in (0, 1) or row["sample_id"] not in provenance:
            raise ValueError("Invalid document label or missing provenance.")
        if row["group_id"] != provenance[row["sample_id"]]["group_id"]:
            raise ValueError("Manifest/provenance source group mismatch.")
        group_splits[row["group_id"]].add(row["split"])
    if any(len(splits) != 1 for splits in group_splits.values()):
        raise ValueError("Document source group crossed partitions.")
    return rows, provenance


def development_partition(rows, seed):
    training = []
    development = []
    for label in (0, 1):
        matching = sorted(
            (row for row in rows if row["split"] == "train" and int(row["label"]) == label),
            key=lambda row: hashlib.sha256(
                f"{seed}:{row['group_id']}".encode("utf-8")
            ).digest(),
        )
        n_dev = max(1, round(len(matching) * 0.2))
        if len(matching) < 10:
            raise ValueError("Need at least ten training documents per class.")
        development.extend(matching[:n_dev])
        training.extend(matching[n_dev:])
    return training, development


@torch.no_grad()
def extract(model, rows, provenance, manifest_path, batch_size=16):
    features = []
    base_probabilities = []
    labels = []
    ids = []
    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        tensors = []
        for row in batch:
            if row["split"] == "test":
                raise ValueError("Sealed test images cannot be embedded during training.")
            image_path = Path(row["file_path"])
            if not image_path.is_absolute():
                image_path = manifest_path.parent / image_path
            raw = image_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != provenance[row["sample_id"]]["stored_sha256"]:
                raise ValueError(f"Image checksum mismatch: {row['sample_id']}")
            with Image.open(image_path) as source:
                tensors.append(model.transform(source.convert("RGB")))
        tensor = torch.stack(tensors).to(model.device)
        hidden = model.model.features(tensor)
        pooled = torch.flatten(model.model.avgpool(hidden), 1)
        logits = model.model.classifier(pooled)
        features.append(pooled.cpu())
        base_probabilities.extend(torch.softmax(logits, dim=1)[:, 1].cpu().tolist())
        labels.extend(int(row["label"]) for row in batch)
        ids.extend(row["sample_id"] for row in batch)
    return torch.cat(features), labels, base_probabilities, ids


def metric_rows(labels, probabilities):
    return [{"label": label, "raw_probability": float(probability)}
            for label, probability in zip(labels, probabilities)]


def train(args):
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    rows, provenance = read_manifest(args.manifest, args.provenance)
    dataset_metadata = json.loads(args.dataset_metadata.read_text(encoding="utf-8"))
    if dataset_metadata["manifest_sha256"] != hashlib.sha256(args.manifest.read_bytes()).hexdigest():
        raise ValueError("Document manifest changed since pack preparation.")
    training, development = development_partition(rows, args.seed)
    validation = [row for row in rows if row["split"] == "validation"]
    if {int(row["label"]) for row in validation} != {0, 1}:
        raise ValueError("Validation must contain both document labels.")
    model = EvidenceAuthenticityModel(args.base_checkpoint)
    base_sha = model.checkpoint_sha256
    active_policy = json.loads(args.active_policy.read_text(encoding="utf-8"))
    active_tampering = active_policy["data_summary"]["model_checkpoints"]["TAMPERING_DETECTION"]
    if active_tampering["model_sha256"] != base_sha:
        raise ValueError("Base checkpoint differs from the active multiview checkpoint.")
    active_temperature = active_policy["detectors"]["TAMPERING_DETECTION"]["temperature"]
    train_x, train_y, _, _ = extract(model, training, provenance, args.manifest)
    dev_x, dev_y, _, _ = extract(model, development, provenance, args.manifest)
    head = nn.Linear(train_x.shape[1], 1)
    with torch.no_grad():
        base_head = model.model.classifier[1]
        head.weight.copy_(base_head.weight[1:2] - base_head.weight[0:1])
        head.bias.copy_(base_head.bias[1:2] - base_head.bias[0:1])
    optimizer = torch.optim.AdamW(head.parameters(), lr=args.learning_rate,
                                  weight_decay=args.weight_decay)
    criterion = nn.BCEWithLogitsLoss()
    train_target = torch.tensor(train_y, dtype=torch.float32)
    dev_target = torch.tensor(dev_y, dtype=torch.float32)
    best_loss = float("inf")
    best_state = None
    best_epoch = 0
    stale = 0
    for epoch in range(1, args.epochs + 1):
        head.train()
        optimizer.zero_grad(set_to_none=True)
        loss = criterion(head(train_x).squeeze(1), train_target)
        loss.backward()
        optimizer.step()
        head.eval()
        with torch.no_grad():
            dev_loss = criterion(head(dev_x).squeeze(1), dev_target).item()
        if dev_loss < best_loss - 1e-5:
            best_loss = dev_loss
            best_epoch = epoch
            best_state = {key: value.detach().clone() for key, value in head.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if stale >= args.patience:
            break
    head.load_state_dict(best_state)
    head.eval()
    with torch.no_grad():
        dev_probabilities = torch.sigmoid(head(dev_x).squeeze(1)).tolist()
    temperature = fit_temperature(metric_rows(dev_y, dev_probabilities))

    # Validation is first read after the architecture, epoch, and temperature
    # have all been fixed by training/development data.
    val_x, val_y, baseline_probabilities, val_ids = extract(
        model, validation, provenance, args.manifest
    )
    with torch.no_grad():
        candidate_probabilities = torch.sigmoid(head(val_x).squeeze(1)).tolist()
    baseline_metrics = calibration_metrics(metric_rows(val_y, baseline_probabilities), active_temperature)
    candidate_metrics = calibration_metrics(metric_rows(val_y, candidate_probabilities), temperature)
    multiview_probabilities = []
    for row in validation:
        image_path = Path(row["file_path"])
        if not image_path.is_absolute():
            image_path = args.manifest.parent / image_path
        multiview_probabilities.append(model.predict_multiview(image_path)["tampered_probability"])
    multiview_metrics = calibration_metrics(metric_rows(val_y, multiview_probabilities), active_temperature)
    requirements = {"minimum_auroc": 0.70, "maximum_ece": 0.15,
                    "minimum_auroc_gain": 0.03}
    passed = (
        candidate_metrics["auroc"] >= requirements["minimum_auroc"]
        and candidate_metrics["expected_calibration_error"] <= requirements["maximum_ece"]
        and candidate_metrics["auroc"] >= baseline_metrics["auroc"] + requirements["minimum_auroc_gain"]
    )
    checkpoint = {
        "head_state_dict": head.state_dict(),
        "base_checkpoint_sha256": base_sha,
        "base_checkpoint_name": args.base_checkpoint.name,
        "input_features": train_x.shape[1],
        "positive_label": "DOCUMENT_TAMPERED",
        "temperature": temperature,
        "preprocessing": "RGB_resize_224_bicubic_ImageNet_normalization",
        "research_only": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, args.output)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "VALIDATION_PILOT_PASSED" if passed else "VALIDATION_PILOT_FAILED",
        "deployment_status": "NOT_APPROVED_RESEARCH_ONLY",
        "dataset": "kriyam-ai/kriyam-tamperflow",
        "license": "CC-BY-NC-4.0",
        "stored_format": "resized JPEG derivatives of source C2 documents",
        "dataset_audit": {
            "available_c2_source_counts": dataset_metadata["available_c2_source_counts"],
            "dataset_card_authentic_claim": 350,
            "paired_authentic_tampered_source_ids": 0,
            "risk": "Unpaired authentic and tampered documents may differ in document type or capture source; the pilot cannot isolate tampering cues.",
        },
        "base_checkpoint_sha256": base_sha,
        "candidate_checkpoint_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "training_count": len(training), "development_count": len(development),
        "validation_count": len(validation),
        "test_count_reserved": sum(row["split"] == "test" for row in rows),
        "test_inference_status": "NOT_RUN",
        "selection": {"best_epoch": best_epoch, "epochs_allowed": args.epochs,
                      "development_loss": best_loss, "temperature": temperature},
        "readiness_requirements": requirements,
        "baseline_global_resize": {key: baseline_metrics[key] for key in (
            "auroc", "expected_calibration_error", "balanced_accuracy", "precision",
            "recall", "f1", "count")},
        "active_multiview": {key: multiview_metrics[key] for key in (
            "auroc", "expected_calibration_error", "balanced_accuracy", "precision",
            "recall", "f1", "count")},
        "candidate_global_resize": {key: candidate_metrics[key] for key in (
            "auroc", "expected_calibration_error", "balanced_accuracy", "precision",
            "recall", "f1", "count")},
        "validation_sample_ids": val_ids,
        "decision": "Research checkpoint only. Do not route document claims or change the active Trust Score without independent original-format claim-domain evaluation.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "status", "training_count", "development_count", "validation_count",
        "test_inference_status", "baseline_global_resize", "active_multiview",
        "candidate_global_resize")}, indent=2))


def main():
    calibration = BACKEND_DIR / "calibration"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=calibration / "document_domain_manifest.csv")
    parser.add_argument("--provenance", type=Path, default=calibration / "document_domain_provenance.csv")
    parser.add_argument("--dataset-metadata", type=Path, default=calibration / "document_domain_provenance.json")
    parser.add_argument("--base-checkpoint", type=Path, default=BACKEND_DIR / "training_outputs/evidence_authenticity_forensic_multiview_candidate.pth")
    parser.add_argument("--active-policy", type=Path, default=calibration / "artifacts/active.json")
    parser.add_argument("--output", type=Path, default=BACKEND_DIR / "training_outputs/document_tampering_head_candidate.pth")
    parser.add_argument("--report", type=Path, default=BACKEND_DIR / "training_outputs/document_tampering_head_report.json")
    parser.add_argument("--seed", type=int, default=20261028)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    train(parser.parse_args())


if __name__ == "__main__":
    main()

"""Gate an external validation set before any policy retuning or test inference."""

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analysis.calibration_training import calibration_metrics
from scripts.audit_active_calibration import rate_record
from scripts.calibrate_fusion import build_validation_scores, read_observations


def evaluate(artifact_path, observations_path, manifest_path, metadata_path):
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as source:
        manifest = list(csv.DictReader(source))
    validation = {row["sample_id"]: row for row in manifest if row["split"] == "validation"}
    test = {row["sample_id"] for row in manifest if row["split"] == "test"}
    if not validation or not test or set(validation) & test:
        raise ValueError("External pack must have disjoint validation and test partitions.")
    rows = read_observations(observations_path)
    if {row["split"] for row in rows} != {"validation"}:
        raise ValueError("Only validation observations may be inspected at this stage.")
    if {row["sample_id"] for row in rows} != set(validation):
        raise ValueError("Validation observations do not cover the validation manifest exactly.")
    requirements = artifact["validation_assessment"]["requirements"]
    detectors = {}
    for detector, policy in artifact["detectors"].items():
        detector_rows = [row for row in rows if row["detector"] == detector]
        if len(detector_rows) != len(validation):
            raise ValueError(f"{detector} is missing validation observations.")
        expected_checkpoint = artifact["data_summary"]["model_checkpoints"][detector]
        if {row["model_sha256"] for row in detector_rows} != {expected_checkpoint["model_sha256"]}:
            raise ValueError(f"{detector} checkpoint differs from the active policy.")
        if {row["model_version"] for row in detector_rows} != {expected_checkpoint["model_version"]}:
            raise ValueError(f"{detector} model version differs from the active policy.")
        metrics = calibration_metrics(detector_rows, policy["temperature"])
        reliability = max(0.0, min(1.0, 2 * metrics["balanced_accuracy"] - 1))
        failures = []
        if metrics["auroc"] < requirements["minimum_test_auroc"]:
            failures.append("AUROC below the existing readiness gate")
        if metrics["expected_calibration_error"] > requirements["maximum_test_ece"]:
            failures.append("Calibration error above the existing readiness gate")
        if reliability < requirements["minimum_reliability"]:
            failures.append("Held-out reliability below the existing readiness gate")
        detectors[detector] = {
            "metrics": {key: metrics[key] for key in (
                "count", "positive_count", "negative_count", "auroc",
                "expected_calibration_error", "brier_score", "balanced_accuracy",
                "precision", "recall", "f1",
            )},
            "youden_reliability": round(reliability, 6),
            "passed": not failures,
            "failures": failures,
        }
    scores = build_validation_scores(rows, artifact["detectors"], split="validation")
    if len(scores) != len(validation):
        raise ValueError("Some validation samples lack a paired fusion score.")
    thresholds = artifact["thresholds"]
    for item in scores:
        if item["conflict"] >= thresholds["conflict_review"]:
            reason = "detector_conflict"
        elif item["uncertainty"] >= thresholds["uncertainty_review"]:
            reason = "fusion_uncertainty"
        elif item["trust_score"] >= thresholds["approve"]:
            reason = "low_concern"
        elif item["trust_score"] <= thresholds["reject"]:
            reason = "low_score_band"
        else:
            reason = "manual_review_band"
        item["reason"] = reason
    authentic = [item for item in scores if item["label"] == 0]
    suspicious = [item for item in scores if item["label"] == 1]
    suspicious_low_concern = sum(item["reason"] == "low_concern" for item in suspicious)
    authentic_low_concern = sum(item["reason"] == "low_concern" for item in authentic)
    ready = all(item["passed"] for item in detectors.values())
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "READY_FOR_POLICY_SEARCH" if ready else "BLOCKED_BY_DOMAIN_SHIFT",
        "active_policy": artifact["policy_version"],
        "dataset": metadata["dataset"],
        "delivery_format": metadata["delivery_format"],
        "delivery_limitation": metadata["delivery_limitation"],
        "observations_sha256": hashlib.sha256(observations_path.read_bytes()).hexdigest(),
        "validation_samples": len(validation),
        "test_samples_reserved": len(test),
        "test_inference_status": "NOT_RUN",
        "readiness_requirements": requirements,
        "detectors": detectors,
        "active_policy_triage": {
            "reason_counts": dict(Counter(item["reason"] for item in scores)),
            "suspicious_marked_low_concern": rate_record(suspicious_low_concern, len(suspicious)),
            "authentic_marked_low_concern": rate_record(authentic_low_concern, len(authentic)),
        },
        "candidate_policy": None,
        "decision": (
            "The existing detectors meet the predeclared gates; a validation-only policy search may proceed."
            if ready else
            "Do not relax thresholds or promote a policy on this source. Improve detector generalization first; keep the reserved test partition unscored."
        ),
    }


def main():
    calibration = BACKEND_DIR / "calibration"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=calibration / "artifacts/active.json")
    parser.add_argument("--observations", type=Path, default=calibration / "sofake_external_validation_observations.csv")
    parser.add_argument("--manifest", type=Path, default=calibration / "sofake_external_manifest.csv")
    parser.add_argument("--metadata", type=Path, default=calibration / "sofake_external_provenance.json")
    parser.add_argument("--output", type=Path, default=calibration / "artifacts/sofake-external-validation-gate.json")
    args = parser.parse_args()
    result = evaluate(args.artifact, args.observations, args.manifest, args.metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "status": result["status"], "detectors": result["detectors"], "active_policy_triage": result["active_policy_triage"], "test_inference_status": result["test_inference_status"]}, indent=2))


if __name__ == "__main__":
    main()

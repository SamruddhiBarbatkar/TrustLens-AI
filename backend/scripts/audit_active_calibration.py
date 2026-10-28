"""Reproduce the active policy's held-out image triage without refitting it."""

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analysis.calibration_training import calibration_metrics, select_operational_thresholds
from scripts.calibrate_fusion import build_validation_scores, read_observations


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_provenance(path):
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    required = {"group_id", "dataset", "dataset_split", "dataset_row", "sha256"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Invalid provenance file: {path}")
    return rows


def provenance_keys(rows):
    return {
        "source_groups": {row["group_id"] for row in rows if row["group_id"]},
        "dataset_rows": {
            (row["dataset"], row["dataset_split"], row["dataset_row"])
            for row in rows if row["dataset_row"]
        },
        "image_hashes": {row["sha256"] for row in rows if row["sha256"]},
    }


def wilson_interval(successes, total, z=1.959963984540054):
    if total == 0:
        return None
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, center - radius), 6), round(min(1.0, center + radius), 6)]


def rate_record(successes, total):
    return {
        "events": successes,
        "total": total,
        "rate": round(successes / total, 6) if total else None,
        "wilson_95_interval": wilson_interval(successes, total),
    }


def audit(artifact_path, observations_path, current_provenance, prior_provenance, checkpoints):
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    source_hash = sha256_file(observations_path)
    if source_hash != artifact["data_summary"]["source_sha256"]:
        raise ValueError("Observation file differs from the active policy source.")
    rows = read_observations(observations_path)
    if len(rows) != artifact["data_summary"]["observation_count"]:
        raise ValueError("Observation count differs from the active policy.")

    checkpoint_audit = {}
    for detector, checkpoint in checkpoints.items():
        expected = artifact["data_summary"]["model_checkpoints"][detector]["model_sha256"]
        actual = sha256_file(checkpoint)
        if actual != expected:
            raise ValueError(f"{detector} checkpoint differs from the active policy.")
        row_hashes = {row["model_sha256"] for row in rows if row["detector"] == detector}
        if row_hashes != {actual}:
            raise ValueError(f"{detector} observation checkpoint hash differs.")
        checkpoint_audit[detector] = {"path": str(checkpoint), "sha256": actual, "matches": True}

    current_rows = read_provenance(current_provenance)
    current_keys = provenance_keys(current_rows)
    prior_rows = [row for path in prior_provenance for row in read_provenance(path)]
    prior_keys = provenance_keys(prior_rows)
    overlap = {
        name: len(current_keys[name] & prior_keys[name])
        for name in current_keys
    }
    if any(overlap.values()):
        raise ValueError(f"Evaluation pack overlaps earlier packs: {overlap}")
    observation_ids = {row["sample_id"] for row in rows}
    if observation_ids != {row["sample_id"] for row in current_rows}:
        raise ValueError("Provenance samples do not match observations.")

    detector_checks = {}
    for detector, policy in artifact["detectors"].items():
        test_rows = [row for row in rows if row["detector"] == detector and row["split"] == "test"]
        recalculated = calibration_metrics(test_rows, policy["temperature"])
        recorded = policy["metrics"]["test"]["calibrated"]
        for metric in ("auroc", "expected_calibration_error", "brier_score", "precision", "recall"):
            if abs(recalculated[metric] - recorded[metric]) > 1e-8:
                raise ValueError(f"{detector} test {metric} does not reproduce.")
        detector_checks[detector] = {metric: recalculated[metric] for metric in (
            "auroc", "expected_calibration_error", "brier_score", "precision", "recall"
        )}

    validation_scores = build_validation_scores(rows, artifact["detectors"], split="validation")
    thresholds = artifact["thresholds"]
    repeated_thresholds = select_operational_thresholds(
        validation_scores,
        maximum_false_acceptance_rate=thresholds["maximum_false_acceptance_rate"],
        maximum_false_rejection_rate=thresholds["maximum_false_rejection_rate"],
    )
    for key in ("approve", "reject"):
        if repeated_thresholds[key] != thresholds[key]:
            raise ValueError(f"Active {key} threshold does not reproduce from validation data.")

    test_scores = build_validation_scores(rows, artifact["detectors"], split="test")
    expected_test_ids = {row["sample_id"] for row in rows if row["split"] == "test"}
    if len(test_scores) != len(expected_test_ids):
        raise ValueError("Some held-out images lack paired detector scores.")
    decisions = []
    for item in test_scores:
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
        decisions.append({
            **item,
            "triage": "LOW_CONCERN" if reason == "low_concern" else "REVIEW_NEEDED",
            "reason": reason,
        })

    authentic = [item for item in decisions if item["label"] == 0]
    suspicious = [item for item in decisions if item["label"] == 1]
    low_concern_suspicious = sum(item["triage"] == "LOW_CONCERN" for item in suspicious)
    review_authentic = sum(item["triage"] == "REVIEW_NEEDED" for item in authentic)
    low_score_authentic = sum(item["trust_score"] <= thresholds["reject"] for item in authentic)
    classes = {}
    test_rows_by_id = {}
    for row in rows:
        if row["split"] == "test":
            test_rows_by_id.setdefault(row["sample_id"], {})[row["detector"]] = row
    for item in decisions:
        sample = test_rows_by_id[item["sample_id"]]
        if int(sample["AI_GENERATION"]["detector_label"]):
            kind = "synthetic"
        elif int(sample["TAMPERING_DETECTION"]["detector_label"]):
            kind = "tampered"
        else:
            kind = "authentic"
        classes.setdefault(kind, []).append(item)

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy_version": artifact["policy_version"],
        "scope": "Held-out image-level fusion triage; not final administrator decisions or claim-level OCR/ELA evaluation.",
        "limitations": [
            "Wilson intervals describe uncertainty from this held-out pack and are not deployment guarantees.",
            "The audit checks separation between local evaluation packs; checkpoint files alone cannot prove training-data exclusion.",
            "The image-level audit does not measure full claim outcomes, OCR or ELA branches, or performance on a new institution's data.",
            "The test split informed the existing policy's promotion readiness; this is a reproduction, not a new independent external replication.",
            "Changing the active policy using these test results would contaminate this holdout; use new validation data and a new untouched test set.",
        ],
        "source_observations": str(observations_path),
        "source_sha256": source_hash,
        "checkpoint_audit": checkpoint_audit,
        "provenance_audit": {"current": str(current_provenance), "earlier_packs": [str(path) for path in prior_provenance], "overlap": overlap},
        "detector_test_metrics_reproduced": detector_checks,
        "thresholds_reproduced_from_validation": {key: repeated_thresholds[key] for key in ("approve", "reject")},
        "test_triage": {
            "sample_count": len(decisions),
            "class_counts": {name: len(items) for name, items in classes.items()},
            "low_concern": sum(item["triage"] == "LOW_CONCERN" for item in decisions),
            "review_needed": sum(item["triage"] == "REVIEW_NEEDED" for item in decisions),
            "triage_reasons": dict(Counter(item["reason"] for item in decisions)),
            "suspicious_marked_low_concern": rate_record(low_concern_suspicious, len(suspicious)),
            "authentic_sent_to_review": rate_record(review_authentic, len(authentic)),
            "authentic_in_low_score_band": rate_record(low_score_authentic, len(authentic)),
            "by_class": {
                name: {
                    "low_concern": sum(item["triage"] == "LOW_CONCERN" for item in items),
                    "review_needed": sum(item["triage"] == "REVIEW_NEEDED" for item in items),
                    "triage_reasons": dict(Counter(item["reason"] for item in items)),
                }
                for name, items in classes.items()
            },
        },
    }


def main():
    calibration = BACKEND_DIR / "calibration"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=calibration / "artifacts/active.json")
    parser.add_argument("--observations", type=Path, default=calibration / "fresh_external_forensic_multiview_observations.csv")
    parser.add_argument("--provenance", type=Path, default=calibration / "fresh_external_audit_provenance.csv")
    parser.add_argument("--ai-checkpoint", type=Path, default=BACKEND_DIR / "training_outputs/ai_detector_multigen_candidate.pth")
    parser.add_argument("--tampering-checkpoint", type=Path, default=BACKEND_DIR / "training_outputs/evidence_authenticity_forensic_multiview_candidate.pth")
    parser.add_argument("--output", type=Path, default=calibration / "artifacts/heldout-score-audit.json")
    args = parser.parse_args()
    prior = sorted(path for path in calibration.glob("*provenance.csv") if path.resolve() != args.provenance.resolve())
    result = audit(args.artifact, args.observations, args.provenance, prior, {
        "AI_GENERATION": args.ai_checkpoint,
        "TAMPERING_DETECTION": args.tampering_checkpoint,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "test_triage": result["test_triage"], "provenance_overlap": result["provenance_audit"]["overlap"]}, indent=2))


if __name__ == "__main__":
    main()

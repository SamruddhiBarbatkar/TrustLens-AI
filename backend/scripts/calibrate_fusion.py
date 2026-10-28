"""Fit and optionally activate TrustLens detector calibration artifacts."""

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.analysis.calibration_training import (
    assess_detector_readiness,
    calibration_metrics,
    fit_temperature,
    reliability_by_quality,
    select_operational_thresholds,
    temperature_scale,
    validate_partitions,
)
from app.analysis.reliability_calibrated_fusion import (
    combine_belief_masses,
    make_belief_mass,
)


SUPPORTED_DETECTORS = {
    "TAMPERING_DETECTION",
    "AI_GENERATION",
}


def read_observations(path):
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    required_columns = {"detector_label", "claim_label"}
    if rows and not required_columns.issubset(rows[0]):
        raise ValueError(
            "Calibration CSV must include detector_label and claim_label."
        )
    for row in rows:
        row["detector_label"] = int(row["detector_label"])
        row["claim_label"] = int(row["claim_label"])
        # Calibration utilities use label as the detector-specific target.
        row["label"] = row["detector_label"]
        row["raw_probability"] = float(row["raw_probability"])
        row["detector"] = row["detector"].strip().upper()
        row["quality_status"] = row["quality_status"].strip().upper()
        row["split"] = row["split"].strip().lower()
    validate_partitions(rows)
    duplicates = [
        key
        for key, count in _counts(
            (row["detector"], row["sample_id"], row["split"])
            for row in rows
        ).items()
        if count > 1
    ]
    if duplicates:
        raise ValueError(f"Duplicate detector observations: {duplicates[:5]}")
    unsupported = sorted({row["detector"] for row in rows} - SUPPORTED_DETECTORS)
    if unsupported:
        raise ValueError(f"Unsupported detectors: {unsupported}")
    return rows


def _counts(values):
    result = defaultdict(int)
    for value in values:
        result[value] += 1
    return result


def build_detector_policies(rows, minimum_samples):
    policies = {}
    for detector in sorted({row["detector"] for row in rows}):
        detector_rows = [row for row in rows if row["detector"] == detector]
        splits = {
            split: [row for row in detector_rows if row["split"] == split]
            for split in ("calibration", "validation", "test")
        }
        for required_split in ("calibration", "validation"):
            if len(splits[required_split]) < minimum_samples:
                raise ValueError(
                    f"{detector} requires at least {minimum_samples} "
                    f"{required_split} observations."
                )
        temperature = fit_temperature(splits["calibration"])
        reliabilities, reliability_metrics = reliability_by_quality(
            splits["validation"],
            temperature,
        )
        policies[detector] = {
            "method": "TEMPERATURE_SCALING",
            "temperature": temperature,
            "reliability_method": "YOUDEN_BALANCED_ACCURACY",
            "reliability_by_quality": reliabilities,
            "metrics": {
                split: {
                    "raw": calibration_metrics(observations, 1.0),
                    "calibrated": calibration_metrics(observations, temperature),
                }
                for split, observations in splits.items()
                if observations
            },
            "reliability_metrics": reliability_metrics,
        }
    return policies


def build_validation_scores(rows, detector_policies, split="validation"):
    if split not in {"calibration", "validation", "test"}:
        raise ValueError(f"Unsupported evaluation split: {split}")
    samples = defaultdict(list)
    for row in rows:
        if row["split"] == split:
            samples[row["sample_id"]].append(row)

    scored = []
    for sample_id, observations in samples.items():
        if {row["detector"] for row in observations} != set(detector_policies):
            continue
        labels = {row["claim_label"] for row in observations}
        if len(labels) != 1:
            raise ValueError(f"Detectors disagree on ground-truth label for {sample_id}.")
        masses = []
        for row in observations:
            policy = detector_policies[row["detector"]]
            probability = temperature_scale(
                row["raw_probability"],
                policy["temperature"],
            )
            reliability = policy["reliability_by_quality"].get(
                row["quality_status"],
                policy["reliability_by_quality"]["OVERALL"],
            )
            masses.append(make_belief_mass(probability, reliability))
        if not masses:
            continue
        combined = masses[0]
        remaining_agreement = 1.0
        for mass in masses[1:]:
            combined, step_conflict = combine_belief_masses(combined, mass)
            remaining_agreement *= 1.0 - step_conflict
            if combined is None:
                break
        if combined is None:
            continue
        scored.append({
            "sample_id": sample_id,
            "label": labels.pop(),
            "trust_score": max(0.0, min(
                100.0 * (
                    combined["authentic"]
                    + 0.5 * combined["uncertainty"]
                ),
                100.0,
            )),
            "uncertainty": 100.0 * combined["uncertainty"],
            "conflict": 100.0 * (1.0 - remaining_agreement),
        })
    return scored


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy-version", required=True)
    parser.add_argument("--minimum-samples", type=int, default=30)
    parser.add_argument("--maximum-far", type=float, default=0.05)
    parser.add_argument("--maximum-frr", type=float, default=0.05)
    parser.add_argument("--uncertainty-review", type=float, default=35.0)
    parser.add_argument("--conflict-review", type=float, default=40.0)
    parser.add_argument("--minimum-test-auroc", type=float, default=0.70)
    parser.add_argument("--maximum-test-ece", type=float, default=0.15)
    parser.add_argument("--minimum-reliability", type=float, default=0.20)
    parser.add_argument("--mark-validated", action="store_true")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()

    if args.activate and not args.mark_validated:
        parser.error("--activate requires --mark-validated")

    rows = read_observations(args.input_csv)
    model_checkpoints = {}
    for detector in sorted({row["detector"] for row in rows}):
        detector_rows = [row for row in rows if row["detector"] == detector]
        versions = {
            row.get("model_version", "UNKNOWN") for row in detector_rows
        }
        hashes = {
            row.get("model_sha256", "UNKNOWN") for row in detector_rows
        }
        if len(versions) != 1 or len(hashes) != 1:
            raise ValueError(
                f"{detector} observations mix multiple model checkpoints."
            )
        model_checkpoints[detector] = {
            "model_version": versions.pop(),
            "model_sha256": hashes.pop(),
        }
    policies = build_detector_policies(rows, args.minimum_samples)
    if args.mark_validated:
        for detector in policies:
            test_rows = [
                row
                for row in rows
                if row["detector"] == detector and row["split"] == "test"
            ]
            if len(test_rows) < args.minimum_samples:
                raise ValueError(
                    f"{detector} requires at least {args.minimum_samples} "
                    "test observations before validation."
                )
            if {row["label"] for row in test_rows} != {0, 1}:
                raise ValueError(
                    f"{detector} test data must contain both labels."
                )
    readiness = assess_detector_readiness(
        policies,
        minimum_test_auroc=args.minimum_test_auroc,
        maximum_test_ece=args.maximum_test_ece,
        minimum_reliability=args.minimum_reliability,
    )
    if args.mark_validated and not readiness["ready"]:
        failures = []
        for detector, assessment in readiness["detectors"].items():
            failures.extend(
                f"{detector}: {failure}"
                for failure in assessment["failures"]
            )
        raise ValueError(
            "Calibration cannot be marked validated. " + "; ".join(failures)
        )
    scored = build_validation_scores(rows, policies)
    thresholds = select_operational_thresholds(
        scored,
        maximum_false_acceptance_rate=args.maximum_far,
        maximum_false_rejection_rate=args.maximum_frr,
    )
    thresholds.update({
        "uncertainty_review": args.uncertainty_review,
        "conflict_review": args.conflict_review,
        "validated": args.mark_validated,
    })
    if args.mark_validated and thresholds["reject"] >= thresholds["approve"]:
        raise ValueError(
            "Validation did not produce a non-overlapping approve/reject "
            "threshold pair. Collect more representative data or revise the "
            "operational constraints."
        )
    artifact = {
        "policy_version": args.policy_version,
        "validated": args.mark_validated,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "calibration": {
            "method": "TEMPERATURE_SCALING",
            "artifact_version": args.policy_version,
        },
        "detectors": policies,
        "validation_assessment": readiness,
        "thresholds": thresholds,
        "data_summary": {
            "source_file": args.input_csv.name,
            "source_sha256": hashlib.sha256(
                args.input_csv.read_bytes()
            ).hexdigest(),
            "observation_count": len(rows),
            "sample_count": len({row["sample_id"] for row in rows}),
            "split_counts": dict(_counts(row["split"] for row in rows)),
            "model_checkpoints": model_checkpoints,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"Wrote calibration artifact: {args.output}")

    if args.activate:
        active_path = BACKEND_DIR / "calibration" / "artifacts" / "active.json"
        active_path.parent.mkdir(parents=True, exist_ok=True)
        active_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        print(f"Activated calibration artifact: {active_path}")


if __name__ == "__main__":
    main()

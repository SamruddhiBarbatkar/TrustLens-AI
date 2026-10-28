"""Compare existing checkpoints on one external validation partition only."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analysis.calibration_training import calibration_metrics
from scripts.calibrate_fusion import read_observations


def compare(files):
    candidates = {}
    expected_samples = None
    for name, path in files.items():
        rows = read_observations(path)
        if {row["split"] for row in rows} != {"validation"}:
            raise ValueError(f"{name} contains non-validation predictions.")
        samples = {row["sample_id"] for row in rows}
        if expected_samples is None:
            expected_samples = samples
        elif samples != expected_samples:
            raise ValueError(f"{name} does not cover the same validation images.")
        branches = {}
        for detector in ("AI_GENERATION", "TAMPERING_DETECTION"):
            detector_rows = [row for row in rows if row["detector"] == detector]
            if len(detector_rows) != len(samples):
                raise ValueError(f"{name} is missing {detector} predictions.")
            versions = {row["model_version"] for row in detector_rows}
            hashes = {row["model_sha256"] for row in detector_rows}
            if len(versions) != 1 or len(hashes) != 1:
                raise ValueError(f"{name} mixes {detector} checkpoints.")
            metrics = calibration_metrics(detector_rows)
            branches[detector] = {
                "model_version": versions.pop(),
                "model_sha256": hashes.pop(),
                "raw_validation_metrics": {key: metrics[key] for key in (
                    "auroc", "expected_calibration_error", "brier_score",
                    "balanced_accuracy", "precision", "recall", "f1",
                )},
            }
        candidates[name] = {
            "observations": str(path),
            "observations_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "branches": branches,
        }
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Exploratory checkpoint comparison on one external validation partition; no test predictions or policy activation.",
        "sample_count": len(expected_samples),
        "candidates": candidates,
    }


def main():
    calibration = BACKEND_DIR / "calibration"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=calibration / "artifacts/sofake-validation-model-comparison.json")
    args = parser.parse_args()
    files = {
        "active_forensic_multiview": calibration / "sofake_external_validation_observations.csv",
        "resnet_shadow_tampering": calibration / "sofake_external_validation_resnet_observations.csv",
        "three_class_single_view_tampering": calibration / "sofake_external_validation_threeclass_observations.csv",
        "shared_three_class_single_view": calibration / "sofake_external_validation_shared_threeclass_observations.csv",
    }
    result = compare(files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, candidate in result["candidates"].items():
        summary = {
            detector: candidate["branches"][detector]["raw_validation_metrics"]
            for detector in ("AI_GENERATION", "TAMPERING_DETECTION")
        }
        print(name, json.dumps(summary))
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()

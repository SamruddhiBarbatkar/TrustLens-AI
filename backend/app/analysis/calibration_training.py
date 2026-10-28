"""Dependency-free calibration and validation utilities.

Labels use 0 for authentic and 1 for manipulated/synthetic. Raw probability
must therefore represent the suspicious class probability.
"""

import math
from collections import defaultdict


EPSILON = 1e-12


def clamp_probability(value):
    return max(EPSILON, min(float(value), 1.0 - EPSILON))


def temperature_scale(probability, temperature):
    probability = clamp_probability(probability)
    temperature = max(float(temperature), EPSILON)
    logit = math.log(probability / (1.0 - probability))
    return 1.0 / (1.0 + math.exp(-logit / temperature))


def binary_log_loss(rows, temperature=1.0):
    if not rows:
        raise ValueError("At least one observation is required.")
    loss = 0.0
    for row in rows:
        probability = clamp_probability(
            temperature_scale(row["raw_probability"], temperature)
        )
        label = int(row["label"])
        loss -= label * math.log(probability)
        loss -= (1 - label) * math.log(1.0 - probability)
    return loss / len(rows)


def fit_temperature(rows):
    """Fit one positive temperature with golden-section optimization."""
    if {int(row["label"]) for row in rows} != {0, 1}:
        raise ValueError("Calibration data must contain both labels 0 and 1.")

    lower = math.log(0.05)
    upper = math.log(20.0)
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    left = upper - ratio * (upper - lower)
    right = lower + ratio * (upper - lower)

    for _ in range(100):
        left_loss = binary_log_loss(rows, math.exp(left))
        right_loss = binary_log_loss(rows, math.exp(right))
        if left_loss < right_loss:
            upper = right
            right = left
            left = upper - ratio * (upper - lower)
        else:
            lower = left
            left = right
            right = lower + ratio * (upper - lower)

    return round(math.exp((lower + upper) / 2.0), 8)


def calibration_metrics(rows, temperature=1.0, bins=10):
    if not rows:
        return None

    predictions = [
        temperature_scale(row["raw_probability"], temperature)
        for row in rows
    ]
    labels = [int(row["label"]) for row in rows]
    brier = sum(
        (probability - label) ** 2
        for probability, label in zip(predictions, labels)
    ) / len(rows)

    ece = 0.0
    reliability_bins = []
    for bin_index in range(bins):
        low = bin_index / bins
        high = (bin_index + 1) / bins
        indexes = [
            index
            for index, probability in enumerate(predictions)
            if low <= probability < high
            or (bin_index == bins - 1 and probability == 1.0)
        ]
        if not indexes:
            continue
        confidence = sum(predictions[index] for index in indexes) / len(indexes)
        observed = sum(labels[index] for index in indexes) / len(indexes)
        ece += (len(indexes) / len(rows)) * abs(confidence - observed)
        reliability_bins.append({
            "lower_bound": low,
            "upper_bound": high,
            "count": len(indexes),
            "mean_probability": round(confidence, 8),
            "observed_rate": round(observed, 8),
        })

    true_positive = sum(
        label == 1 and probability >= 0.5
        for probability, label in zip(predictions, labels)
    )
    true_negative = sum(
        label == 0 and probability < 0.5
        for probability, label in zip(predictions, labels)
    )
    positive_count = sum(labels)
    negative_count = len(labels) - positive_count
    false_positive = negative_count - true_negative
    false_negative = positive_count - true_positive
    tpr = true_positive / positive_count if positive_count else 0.0
    tnr = true_negative / negative_count if negative_count else 0.0
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0
    )
    f1 = (
        2.0 * precision * tpr / (precision + tpr)
        if precision + tpr
        else 0.0
    )

    auroc = None
    average_precision = None
    if positive_count and negative_count:
        positive_scores = [
            probability
            for probability, label in zip(predictions, labels)
            if label == 1
        ]
        negative_scores = [
            probability
            for probability, label in zip(predictions, labels)
            if label == 0
        ]
        wins = sum(
            1.0 if positive > negative else 0.5 if positive == negative else 0.0
            for positive in positive_scores
            for negative in negative_scores
        )
        auroc = wins / (positive_count * negative_count)

        ordered = sorted(
            zip(predictions, labels),
            key=lambda item: item[0],
            reverse=True,
        )
        seen_positive = 0
        precision_sum = 0.0
        for index, (_, label) in enumerate(ordered, start=1):
            if label == 1:
                seen_positive += 1
                precision_sum += seen_positive / index
        average_precision = precision_sum / positive_count

    return {
        "count": len(rows),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "log_loss": round(binary_log_loss(rows, temperature), 8),
        "brier_score": round(brier, 8),
        "expected_calibration_error": round(ece, 8),
        "balanced_accuracy": round((tpr + tnr) / 2.0, 8),
        "precision": round(precision, 8),
        "recall": round(tpr, 8),
        "f1": round(f1, 8),
        "auroc": round(auroc, 8) if auroc is not None else None,
        "average_precision": (
            round(average_precision, 8)
            if average_precision is not None
            else None
        ),
        "false_acceptance_rate": (
            round(false_negative / positive_count, 8)
            if positive_count
            else None
        ),
        "false_rejection_rate": (
            round(false_positive / negative_count, 8)
            if negative_count
            else None
        ),
        "reliability_bins": reliability_bins,
    }


def validate_partitions(rows):
    required = {
        "detector",
        "sample_id",
        "group_id",
        "split",
        "label",
        "raw_probability",
        "quality_status",
    }
    allowed_splits = {"calibration", "validation", "test"}
    sample_splits = defaultdict(set)
    group_splits = defaultdict(set)

    for row in rows:
        missing = required.difference(row)
        if missing:
            raise ValueError(
                "Observation is missing fields: " + ", ".join(sorted(missing))
            )
        if row["split"] not in allowed_splits:
            raise ValueError(f"Unsupported split: {row['split']}")
        if int(row["label"]) not in {0, 1}:
            raise ValueError("Labels must be 0 (authentic) or 1 (suspicious).")
        probability = float(row["raw_probability"])
        if not 0.0 <= probability <= 1.0:
            raise ValueError("raw_probability must be between 0 and 1.")
        sample_splits[row["sample_id"]].add(row["split"])
        group_splits[row["group_id"]].add(row["split"])

    leaking_samples = sorted(key for key, splits in sample_splits.items() if len(splits) > 1)
    leaking_groups = sorted(key for key, splits in group_splits.items() if len(splits) > 1)
    if leaking_samples or leaking_groups:
        raise ValueError(
            "Partition leakage detected. Samples: "
            f"{leaking_samples[:5]}; groups: {leaking_groups[:5]}"
        )


def reliability_by_quality(rows, temperature, minimum_group_samples=10):
    """Estimate reliability as held-out Youden-informed balanced accuracy."""
    groups = defaultdict(list)
    for row in rows:
        groups[row["quality_status"].upper()].append(row)
    groups["OVERALL"] = list(rows)

    reliabilities = {}
    details = {}
    for name, observations in groups.items():
        labels = {int(row["label"]) for row in observations}
        if (
            name != "OVERALL"
            and (
                len(observations) < minimum_group_samples
                or labels != {0, 1}
            )
        ):
            continue
        if labels != {0, 1}:
            raise ValueError(
                "Validation data must contain both labels for reliability "
                "estimation."
            )
        metrics = calibration_metrics(observations, temperature)
        balanced_accuracy = metrics["balanced_accuracy"]
        # Youden's J maps chance performance to zero reliability.
        reliability = max(0.0, min(1.0, 2.0 * balanced_accuracy - 1.0))
        reliabilities[name] = round(reliability, 6)
        details[name] = metrics
    return reliabilities, details


def select_operational_thresholds(
    scored_rows,
    maximum_false_acceptance_rate=0.05,
    maximum_false_rejection_rate=0.05,
):
    """Select validation thresholds subject to FAR and FRR constraints."""
    authentic = [row for row in scored_rows if int(row["label"]) == 0]
    suspicious = [row for row in scored_rows if int(row["label"]) == 1]
    if not authentic or not suspicious:
        raise ValueError("Threshold selection requires both authentic and suspicious samples.")

    candidates = sorted({0.0, 100.0, *[float(row["trust_score"]) for row in scored_rows]})
    approve = next(
        (
            threshold
            for threshold in candidates
            if sum(row["trust_score"] >= threshold for row in suspicious)
            / len(suspicious) <= maximum_false_acceptance_rate
        ),
        100.0,
    )
    reject = next(
        (
            threshold
            for threshold in reversed(candidates)
            if sum(row["trust_score"] <= threshold for row in authentic)
            / len(authentic) <= maximum_false_rejection_rate
        ),
        0.0,
    )

    far = sum(row["trust_score"] >= approve for row in suspicious) / len(suspicious)
    frr = sum(row["trust_score"] <= reject for row in authentic) / len(authentic)
    return {
        "approve": round(approve, 4),
        "reject": round(reject, 4),
        "maximum_false_acceptance_rate": maximum_false_acceptance_rate,
        "maximum_false_rejection_rate": maximum_false_rejection_rate,
        "observed_false_acceptance_rate": round(far, 8),
        "observed_false_rejection_rate": round(frr, 8),
    }


def assess_detector_readiness(
    detector_policies,
    minimum_test_auroc=0.70,
    maximum_test_ece=0.15,
    minimum_reliability=0.20,
):
    """Assess whether every detector clears explicit activation gates."""
    detectors = {}
    for detector, policy in detector_policies.items():
        failures = []
        test_metrics = (
            policy.get("metrics", {})
            .get("test", {})
            .get("calibrated")
        )
        if not test_metrics:
            failures.append("missing calibrated test metrics")
        else:
            auroc = test_metrics.get("auroc")
            ece = test_metrics.get("expected_calibration_error")
            if auroc is None or auroc < minimum_test_auroc:
                failures.append(
                    f"test AUROC {auroc} is below {minimum_test_auroc}"
                )
            if ece is None or ece > maximum_test_ece:
                failures.append(
                    f"test ECE {ece} exceeds {maximum_test_ece}"
                )

        reliability = policy.get("reliability_by_quality", {}).get("OVERALL")
        if reliability is None or reliability < minimum_reliability:
            failures.append(
                f"overall reliability {reliability} is below "
                f"{minimum_reliability}"
            )
        detectors[detector] = {
            "passed": not failures,
            "failures": failures,
        }

    return {
        "ready": bool(detectors) and all(
            assessment["passed"] for assessment in detectors.values()
        ),
        "requirements": {
            "minimum_test_auroc": minimum_test_auroc,
            "maximum_test_ece": maximum_test_ece,
            "minimum_reliability": minimum_reliability,
        },
        "detectors": detectors,
    }

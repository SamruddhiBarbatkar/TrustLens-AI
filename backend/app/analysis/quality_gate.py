from app.analysis.base import create_analysis_output


def evaluate_quality_gate(
    image_quality_result,
    evidence_id
):
    """
    Evaluate whether evidence has sufficient
    image quality for downstream analysis.
    """

    if image_quality_result is None:
        return create_analysis_output(
            analysis_type="QUALITY_GATE",
            evidence_id=evidence_id,
            status="ERROR",
            result={
                "quality_status": "UNKNOWN"
            },
            message=(
                "Image quality analysis is unavailable."
            )
        )

    width = image_quality_result.get("width", 0)
    height = image_quality_result.get("height", 0)

    brightness = image_quality_result.get(
        "brightness_mean",
        0
    )

    contrast = image_quality_result.get(
        "contrast_std",
        0
    )

    sharpness = image_quality_result.get(
        "sharpness_score",
        0
    )

    reasons = []

    # Resolution
    if width < 500 or height < 500:
        reasons.append(
            "Low image resolution."
        )

    # Brightness
    if brightness < 40:
        reasons.append(
            "Image is too dark."
        )

    if brightness > 220:
        reasons.append(
            "Image is too bright."
        )

    # Contrast
    if contrast < 20:
        reasons.append(
            "Low contrast."
        )

    # Sharpness
    if sharpness < 50:
        reasons.append(
            "Image appears blurry."
        )

    # Overall quality classification
    if len(reasons) == 0:
        quality_status = "GOOD"

    elif len(reasons) <= 2:
        quality_status = "WARNING"

    else:
        quality_status = "POOR"

    result = {
        "quality_status": quality_status,
        "reasons": reasons,
        "metrics": {
            "width": width,
            "height": height,
            "brightness": brightness,
            "contrast": contrast,
            "sharpness": sharpness
        }
    }

    return create_analysis_output(
        analysis_type="QUALITY_GATE",
        evidence_id=evidence_id,
        status="COMPLETED",
        result=result,
        message=(
            "Evidence quality gate completed."
        )
    )
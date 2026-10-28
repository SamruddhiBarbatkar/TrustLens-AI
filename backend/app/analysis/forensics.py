from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageStat

from app.analysis.base import create_analysis_output


ELA_ANALYSIS_VERSION = "ela-recompression-v1"


def analyze_forensics(evidence):

    file_path = Path(evidence.file_path)

    if not file_path.exists():
        return create_analysis_output(
            analysis_type="FORENSICS",
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message="Evidence file not found."
        )

    if file_path.suffix.lower() == ".pdf":
        return create_analysis_output(
            analysis_type="FORENSICS",
            evidence_id=evidence.id,
            status="NOT_SUPPORTED",
            result=None,
            message="Image forensic analysis is not supported for PDF files yet."
        )

    try:

        with Image.open(file_path) as image:

            # Convert to RGB for consistent processing
            original = image.convert("RGB")

            # -------------------------------------------------
            # Basic image information
            # -------------------------------------------------

            width = original.width
            height = original.height

            # -------------------------------------------------
            # JPEG information
            # -------------------------------------------------

            jpeg_quality = None

            if original.format == "JPEG":
                jpeg_quality = image.info.get("quality")

            # -------------------------------------------------
            # ELA-style recompression analysis
            # -------------------------------------------------

            temp_path = file_path.with_name(
                f"{file_path.stem}_forensic_temp.jpg"
            )

            original.save(
                temp_path,
                format="JPEG",
                quality=90
            )

            with Image.open(temp_path) as recompressed:
                recompressed = recompressed.convert("RGB")

                difference = ImageChops.difference(
                    original,
                    recompressed
                )

                difference_stat = ImageStat.Stat(
                    difference
                )

                mean_difference = sum(
                    difference_stat.mean
                ) / len(difference_stat.mean)

                max_difference = max(
                    difference_stat.extrema[channel][1]
                    for channel in range(3)
                )

                # Enhance difference image
                enhanced = ImageEnhance.Brightness(
                    difference
                ).enhance(10)

                enhanced_stat = ImageStat.Stat(
                    enhanced
                )

                enhanced_mean = sum(
                    enhanced_stat.mean
                ) / len(enhanced_stat.mean)

            # Remove temporary file
            if temp_path.exists():
                temp_path.unlink()

            result = {
                "analysis_version": ELA_ANALYSIS_VERSION,
                "image_width": width,
                "image_height": height,
                "original_format": image.format,
                "jpeg_quality": jpeg_quality,
                "ela_mean_difference": round(
                    mean_difference,
                    4
                ),
                "ela_max_difference": round(
                    max_difference,
                    4
                ),
                "ela_enhanced_mean": round(
                    enhanced_mean,
                    4
                ),
                "ela_applicable": True,
                "ela_interpretation": (
                    "Recompression residual measurements are supporting "
                    "forensic features, not a standalone tampering verdict."
                )
            }

        return create_analysis_output(
            analysis_type="FORENSICS",
            evidence_id=evidence.id,
            status="COMPLETED",
            result=result,
            message=(
                "Forensic image analysis completed. "
                "Results are forensic indicators and "
                "are not an independent tampering verdict."
            )
        )

    except Exception as error:

        return create_analysis_output(
            analysis_type="FORENSICS",
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message=f"Forensic analysis failed: {str(error)}"
        )

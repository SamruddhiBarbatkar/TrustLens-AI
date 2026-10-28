from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

from app.analysis.base import create_analysis_output


def analyze_image_quality(evidence):

    file_path = Path(evidence.file_path)

    if not file_path.exists():
        return create_analysis_output(
            analysis_type="IMAGE_QUALITY",
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message="Evidence file not found."
        )

    try:
        file_size = file_path.stat().st_size

        with Image.open(file_path) as image:

            # Convert image to grayscale
            grayscale = image.convert("L")

            # Basic dimensions
            width = image.width
            height = image.height

            # Aspect ratio
            if height > 0:
                aspect_ratio = round(
                    width / height,
                    4
                )
            else:
                aspect_ratio = None

            # Brightness
            brightness_stats = ImageStat.Stat(
                grayscale
            )

            brightness_mean = round(
                brightness_stats.mean[0],
                2
            )

            # Contrast
            contrast_std = round(
                brightness_stats.stddev[0],
                2
            )

            # Simple sharpness / blur proxy
            edges = grayscale.filter(
                ImageFilter.FIND_EDGES
            )

            edge_stats = ImageStat.Stat(edges)

            sharpness_score = round(
                edge_stats.var[0],
                2
            )

            result = {
                "width": width,
                "height": height,
                "aspect_ratio": aspect_ratio,
                "file_size_bytes": file_size,
                "brightness_mean": brightness_mean,
                "contrast_std": contrast_std,
                "sharpness_score": sharpness_score
            }

        return create_analysis_output(
            analysis_type="IMAGE_QUALITY",
            evidence_id=evidence.id,
            status="COMPLETED",
            result=result,
            message="Image quality analysis completed successfully."
        )

    except Exception as error:

        return create_analysis_output(
            analysis_type="IMAGE_QUALITY",
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message=f"Image quality analysis failed: {str(error)}"
        )
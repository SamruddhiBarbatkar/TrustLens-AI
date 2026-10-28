from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS

from app.analysis.base import create_analysis_output


def analyze_metadata(evidence):

    file_path = Path(evidence.file_path)

    # Check whether file exists
    if not file_path.exists():

        return create_analysis_output(
            analysis_type="METADATA",
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message="Evidence file not found."
        )

    try:

        # Basic file information
        file_size = file_path.stat().st_size

        result = {
            "filename": evidence.original_filename,
            "stored_filename": evidence.stored_filename,
            "file_extension": file_path.suffix.lower(),
            "file_size_bytes": file_size
        }

        # Open image
        with Image.open(file_path) as image:

            result["format"] = image.format
            result["width"] = image.width
            result["height"] = image.height
            result["mode"] = image.mode

            # Extract EXIF metadata
            exif_data = image.getexif()

            exif = {}

            for tag_id, value in exif_data.items():

                tag_name = TAGS.get(
                    tag_id,
                    str(tag_id)
                )

                try:
                    exif[tag_name] = str(value)

                except Exception:
                    exif[tag_name] = "<unreadable>"

            result["exif"] = exif

        return create_analysis_output(
            analysis_type="METADATA",
            evidence_id=evidence.id,
            status="COMPLETED",
            result=result,
            message="Metadata extraction completed successfully."
        )

    except Exception as error:

        return create_analysis_output(
            analysis_type="METADATA",
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message=f"Metadata extraction failed: {str(error)}"
        )
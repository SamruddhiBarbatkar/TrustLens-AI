from PIL import Image

from app.services.quality import ImageQualityService


def test_quality_service_returns_measured_image_properties() -> None:
    image = Image.new("RGB", (4, 4), "white")

    result = ImageQualityService().analyze(image)

    assert result.width == 4
    assert result.height == 4
    assert result.brightness_mean == 255
    assert result.contrast_standard_deviation == 0
    assert result.sharpness_laplacian_variance == 0
    assert "not proof" in result.limitations[0]

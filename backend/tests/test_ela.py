from PIL import Image, ImageDraw

from app.services.ela import ELAService


def test_ela_returns_documented_measurements_for_a_decoded_image() -> None:
    image = Image.new("RGB", (32, 32), "white")
    ImageDraw.Draw(image).rectangle((8, 8, 23, 23), fill="red")

    result = ELAService().analyze(image)

    assert result.recompression_quality == 90
    assert 0 <= result.mean_absolute_difference <= 255
    assert 0 <= result.root_mean_square_difference <= 255
    assert 0 <= result.max_channel_difference <= 255
    assert 0 <= result.differing_pixel_fraction <= 1
    assert "not image authenticity" in result.limitations[0]
    assert "quality 90" in result.method


def test_ela_is_deterministic_for_the_same_image() -> None:
    image = Image.new("RGBA", (16, 16), (20, 80, 180, 127))
    service = ELAService()

    first = service.analyze(image)
    second = service.analyze(image)

    assert first == second


def test_ela_reports_zero_difference_for_a_black_image() -> None:
    result = ELAService().analyze(Image.new("RGB", (8, 8), "black"))

    assert result.mean_absolute_difference == 0
    assert result.root_mean_square_difference == 0
    assert result.max_channel_difference == 0
    assert result.differing_pixel_fraction == 0

from pydantic import BaseModel, Field


class ImageQualityResult(BaseModel):
    """Measured image properties used as contextual quality evidence."""

    width: int = Field(ge=1)
    height: int = Field(ge=1)
    brightness_mean: float = Field(ge=0, le=255)
    contrast_standard_deviation: float = Field(ge=0)
    sharpness_laplacian_variance: float = Field(ge=0)
    method: str
    limitations: tuple[str, ...]

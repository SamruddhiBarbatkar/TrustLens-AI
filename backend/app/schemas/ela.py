from pydantic import BaseModel, Field


class ELAResult(BaseModel):
    """Measured JPEG recompression differences; not an authenticity determination."""

    recompression_quality: int = Field(ge=1, le=95)
    mean_absolute_difference: float = Field(ge=0, le=255)
    root_mean_square_difference: float = Field(ge=0, le=255)
    max_channel_difference: int = Field(ge=0, le=255)
    differing_pixel_fraction: float = Field(ge=0, le=1)
    method: str
    limitations: tuple[str, ...]

from pydantic import BaseModel, Field


class OCRPoint(BaseModel):
    x: float
    y: float


class OCRTextRegion(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)
    bounding_box: tuple[OCRPoint, OCRPoint, OCRPoint, OCRPoint]


class OCRResult(BaseModel):
    regions: list[OCRTextRegion]

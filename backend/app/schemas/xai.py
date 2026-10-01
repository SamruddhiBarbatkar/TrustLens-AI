"""Typed, persisted explanation data derived from analysis outputs.

These schemas deliberately describe evidence already produced by the analysis
pipeline. They do not contain model internals, source paths, credentials, or
claims of image provenance.
"""

from typing import Literal

from pydantic import BaseModel, Field


SignalStatus = Literal["available", "unavailable", "failed"]
EvidenceDirection = Literal["supports_authenticity", "requires_review", "context_only"]


class ExplanationFactor(BaseModel):
    """One named item of evidence used in a human-readable explanation."""

    signal: str
    direction: EvidenceDirection
    explanation: str


class TrustScoreExplanation(BaseModel):
    """Explanation of the server-derived score, when scoring is possible."""

    score: int | None = Field(default=None, ge=0, le=100)
    category: str | None = None
    explanation: str | None = None
    contributing_factors: tuple[ExplanationFactor, ...] = ()
    caution_factors: tuple[ExplanationFactor, ...] = ()


class ModelSignalExplanation(BaseModel):
    """Classification and interpretation from one existing model signal."""

    status: SignalStatus
    classification: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    interpretation: str | None = None
    contribution: str | None = None
    limitations: tuple[str, ...] = ()


class OCRExplanation(BaseModel):
    """Summary of OCR output without treating text as authenticity proof."""

    status: SignalStatus
    text_region_count: int | None = Field(default=None, ge=0)
    aggregate_confidence: float | None = Field(default=None, ge=0, le=1)
    interpretation: str | None = None
    limitations: tuple[str, ...] = ()


class ImageQualityExplanation(BaseModel):
    """Contextual quality measurements and their plain-language observations."""

    status: SignalStatus
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    brightness_mean: float | None = Field(default=None, ge=0, le=255)
    contrast_standard_deviation: float | None = Field(default=None, ge=0)
    sharpness_laplacian_variance: float | None = Field(default=None, ge=0)
    interpretation: str | None = None
    limitations: tuple[str, ...] = ()


class ELAExplanation(BaseModel):
    """ELA observations described as forensic-supporting context only."""

    status: SignalStatus
    observations: tuple[str, ...] = ()
    interpretation: str | None = None
    limitations: tuple[str, ...] = ()


class FusionExplanation(BaseModel):
    """The evidence considered by the actual adaptive fusion calculation."""

    signals_considered: tuple[str, ...] = ()
    positive_signals: tuple[ExplanationFactor, ...] = ()
    suspicious_signals: tuple[ExplanationFactor, ...] = ()
    signal_weights: dict[str, float] = Field(default_factory=dict)
    explanation: str | None = None
    limitations: tuple[str, ...] = ()


class AnalysisExplanation(BaseModel):
    """Optional XAI payload stored alongside a completed analysis.

    Every component is optional to keep partially completed analyses and
    historical records representable without inventing unavailable evidence.
    """

    overall_summary: str | None = None
    trust_score: TrustScoreExplanation | None = None
    tampering: ModelSignalExplanation | None = None
    ai_generated: ModelSignalExplanation | None = None
    ocr: OCRExplanation | None = None
    image_quality: ImageQualityExplanation | None = None
    ela: ELAExplanation | None = None
    fusion: FusionExplanation | None = None
    limitations: tuple[str, ...] = ()

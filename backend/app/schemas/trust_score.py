from typing import Literal

from pydantic import BaseModel, Field


class TrustScore(BaseModel):
    """Transparent, server-derived decision-support score.

    ``score`` is calculated only from available model signals with a verified
    authenticity-direction mapping. Other signals remain visible as evidence
    but are not converted into an unvalidated authenticity probability.
    """

    score: int = Field(ge=0, le=100)
    category: Literal["Likely Authentic", "Needs Review", "Potentially Suspicious"]
    signal_weights: dict[str, float]
    contributing_signals: tuple[str, ...]
    limitations: tuple[str, ...]

"""Select the detector checkpoints used by each verification policy.

Candidate checkpoints are explicit configuration. The default remains the
legacy policy until a locked candidate has passed final confirmation and the
operator changes ``DETECTOR_POLICY_MODE``.
"""

from functools import lru_cache
from pathlib import Path

from app.core.config import BACKEND_DIR, settings
from app.ml.ai_generation_model import AIGenerationModel, MODEL_PATH as AI_LEGACY_PATH
from app.ml.evidence_authenticity_model import EvidenceAuthenticityModel
from app.ml.tampering_model import (
    MODEL_PATH as TAMPERING_LEGACY_PATH,
    TamperingDetectionModel,
)


LEGACY_MODE = "LEGACY"
HYBRID_CANDIDATE_MODE = "HYBRID_CANDIDATE"
HYBRID_V1_MODE = "HYBRID_V1"
HYBRID_V2_MODE = "HYBRID_V2"
HYBRID_MODES = {HYBRID_CANDIDATE_MODE, HYBRID_V1_MODE, HYBRID_V2_MODE}


def resolve_model_path(path):
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = BACKEND_DIR / candidate
    return candidate.resolve()


@lru_cache(maxsize=4)
def _ai_model(path):
    return AIGenerationModel(path)


@lru_cache(maxsize=4)
def _tampering_model(path):
    return TamperingDetectionModel(path)


@lru_cache(maxsize=4)
def _authenticity_model(path):
    return EvidenceAuthenticityModel(path)


def get_primary_ai_generation_model():
    if settings.detector_policy_mode in HYBRID_MODES:
        path = settings.ai_generation_candidate_path
    else:
        path = AI_LEGACY_PATH
    return _ai_model(resolve_model_path(path))


def get_primary_tampering_model():
    if settings.detector_policy_mode == HYBRID_V2_MODE:
        return _authenticity_model(resolve_model_path(
            settings.multiview_candidate_path
        ))
    if settings.detector_policy_mode in HYBRID_MODES:
        return _authenticity_model(resolve_model_path(
            settings.evidence_authenticity_candidate_path
        ))
    return _tampering_model(resolve_model_path(TAMPERING_LEGACY_PATH))


def primary_tampering_uses_multiview():
    return settings.detector_policy_mode == HYBRID_V2_MODE


def resnet_shadow_enabled():
    return (
        settings.detector_policy_mode in HYBRID_MODES
        and settings.enable_resnet_shadow
    )


def get_resnet_shadow_model():
    if not resnet_shadow_enabled():
        return None
    return _tampering_model(resolve_model_path(
        settings.resnet_shadow_candidate_path
    ))


def multiview_candidate_enabled():
    return (
        settings.detector_policy_mode in {
            HYBRID_CANDIDATE_MODE,
            HYBRID_V1_MODE,
        }
        and settings.enable_multiview_candidate
    )


def get_multiview_candidate_model():
    if not multiview_candidate_enabled():
        return None
    return _authenticity_model(resolve_model_path(
        settings.multiview_candidate_path
    ))


def clear_model_cache():
    """Release cached model objects, primarily for tests and policy reloads."""
    _ai_model.cache_clear()
    _tampering_model.cache_clear()
    _authenticity_model.cache_clear()

from itertools import combinations

from app.analysis.claim_context import (
    get_evidence_relationship,
    build_financial_relationship_summary
)


REQUIRED_EVIDENCE_TYPES = {
    "invoice",
    "product",
    "damage"
}


EVIDENCE_PAIRS = [
    ("invoice", "product"),
    ("invoice", "damage"),
    ("product", "damage")
]


COMPARISON_RULES = {
    "dates",
    "datetimes",
    "emails",
    "phone_numbers"
}

OCR_CROSS_EVIDENCE_VERSION = "ocr-cross-evidence-v1"


def _get_ocr_entities(
    db,
    verification_run_id,
    evidence_id
):
    from app.db.models import AnalysisResult

    result = (
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.verification_run_id == verification_run_id,
            AnalysisResult.evidence_id == evidence_id,
            AnalysisResult.analysis_type == "OCR_ENTITIES"
        )
        .first()
    )

    if not result:
        return None

    if result.status != "COMPLETED":
        return None

    return result.result


def _compare_values(
    values_a,
    values_b,
    evidence_a,
    evidence_b
):
    if not values_a or not values_b:
        return {
            "status": "NOT_COMPARABLE",
            "values_a": values_a,
            "values_b": values_b,
            "evidence_a": evidence_a,
            "evidence_b": evidence_b,
            "shared_values": []
        }

    shared_values = sorted(
        set(values_a).intersection(values_b)
    )

    if shared_values:
        return {
            "status": "MATCH",
            "values_a": values_a,
            "values_b": values_b,
            "evidence_a": evidence_a,
            "evidence_b": evidence_b,
            "shared_values": shared_values
        }

    return {
        "status": "CONFLICT",
        "values_a": values_a,
        "values_b": values_b,
        "evidence_a": evidence_a,
        "evidence_b": evidence_b,
        "shared_values": []
    }


def _compare_datetimes(
    values_a,
    values_b,
    evidence_a,
    evidence_b,
    identifiers_a,
    identifiers_b
):
    if not values_a or not values_b:
        return {
            "status": "NOT_COMPARABLE",
            "reason": (
                "Datetime comparison requires datetime "
                "values in both evidence items."
            ),
            "values_a": values_a,
            "values_b": values_b,
            "evidence_a": evidence_a,
            "evidence_b": evidence_b,
            "shared_values": []
        }

    shared_identifier_values = {
        item["normalized"]
        for item in identifiers_a
        if item.get("normalized")
    }.intersection(
        {
            item["normalized"]
            for item in identifiers_b
            if item.get("normalized")
        }
    )

    if not shared_identifier_values:
        return {
            "status": "NOT_COMPARABLE",
            "reason": (
                "Different timestamps are not treated "
                "as a conflict unless a shared transaction "
                "or event identity is established."
            ),
            "values_a": values_a,
            "values_b": values_b,
            "evidence_a": evidence_a,
            "evidence_b": evidence_b,
            "shared_values": []
        }

    return _compare_values(
        values_a,
        values_b,
        evidence_a,
        evidence_b
    )


def _compare_identifiers(
    identifiers_a,
    identifiers_b,
    evidence_a,
    evidence_b
):
    comparable_pairs = []

    for identifier_a in identifiers_a:
        type_a = identifier_a.get("type")
        value_a = identifier_a.get("normalized")

        if not type_a or not value_a:
            continue

        for identifier_b in identifiers_b:
            type_b = identifier_b.get("type")
            value_b = identifier_b.get("normalized")

            if not type_b or not value_b:
                continue

            if type_a == type_b:
                comparable_pairs.append(
                    {
                        "type": type_a,
                        "value_a": value_a,
                        "value_b": value_b
                    }
                )

    if not comparable_pairs:
        return {
            "status": "NOT_COMPARABLE",
            "evidence_a": evidence_a,
            "evidence_b": evidence_b,
            "shared_values": [],
            "conflicting_identifiers": [],
            "comparable_identifier_types": []
        }

    shared_values = []
    conflicting_identifiers = []
    comparable_identifier_types = []

    for pair in comparable_pairs:

        if pair["type"] not in comparable_identifier_types:
            comparable_identifier_types.append(
                pair["type"]
            )

        if pair["value_a"] == pair["value_b"]:
            shared_values.append(
                pair["value_a"]
            )
        else:
            conflicting_identifiers.append(
                {
                    "type": pair["type"],
                    "value_a": pair["value_a"],
                    "value_b": pair["value_b"]
                }
            )

    if conflicting_identifiers:
        status = "CONFLICT"
    elif shared_values:
        status = "MATCH"
    else:
        status = "NOT_COMPARABLE"

    return {
        "status": status,
        "evidence_a": evidence_a,
        "evidence_b": evidence_b,
        "shared_values": shared_values,
        "conflicting_identifiers": conflicting_identifiers,
        "comparable_identifier_types": (
            comparable_identifier_types
        )
    }


def _compare_financial_amounts(
    financial_amounts_a,
    financial_amounts_b,
    evidence_a,
    evidence_b
):
    relationship_summary = (
        build_financial_relationship_summary(
            financial_amounts_a,
            financial_amounts_b
        )
    )

    directly_comparable = []
    semantically_related = []

    for relationship in relationship_summary:

        if relationship["relationship"] == (
            "DIRECTLY_COMPARABLE"
        ):
            directly_comparable.append(
                relationship
            )

        elif relationship["relationship"] == (
            "SEMANTICALLY_RELATED"
        ):
            semantically_related.append(
                relationship
            )

    # --------------------------------------------------
    # Directly comparable fields
    # --------------------------------------------------

    if directly_comparable:

        matches = []
        conflicts = []

        for comparison in directly_comparable:

            if (
                comparison["value_a"]
                == comparison["value_b"]
            ):
                matches.append(comparison)
            else:
                conflicts.append(comparison)

        if conflicts:
            status = "CONFLICT"
        elif matches:
            status = "MATCH"
        else:
            status = "NOT_COMPARABLE"

        return {
            "status": status,
            "evidence_a": evidence_a,
            "evidence_b": evidence_b,
            "financial_comparisons": (
                relationship_summary
            ),
            "directly_comparable": (
                directly_comparable
            ),
            "semantically_related": (
                semantically_related
            )
        }

    # --------------------------------------------------
    # Semantic relationship only
    # --------------------------------------------------

    if semantically_related:

        return {
            "status": "SEMANTICALLY_RELATED",
            "reason": (
                "Financial fields are semantically "
                "related but are not directly comparable "
                "under the current comparison rules."
            ),
            "evidence_a": evidence_a,
            "evidence_b": evidence_b,
            "financial_comparisons": (
                relationship_summary
            ),
            "directly_comparable": [],
            "semantically_related": (
                semantically_related
            )
        }

    # --------------------------------------------------
    # Nothing comparable
    # --------------------------------------------------

    return {
        "status": "NOT_COMPARABLE",
        "reason": (
            "No comparable or semantically related "
            "financial field exists between the evidence "
            "items."
        ),
        "evidence_a": evidence_a,
        "evidence_b": evidence_b,
        "financial_comparisons": (
            relationship_summary
        ),
        "directly_comparable": [],
        "semantically_related": []
    }


def analyze_cross_evidence(
    db,
    claim,
    verification_run
):
    evidence_by_type = {
        evidence.evidence_type.lower(): evidence
        for evidence in claim.evidence
    }

    missing_evidence = sorted(
        REQUIRED_EVIDENCE_TYPES
        - set(evidence_by_type.keys())
    )

    evidence_presence = {
        evidence_type: evidence_type in evidence_by_type
        for evidence_type in REQUIRED_EVIDENCE_TYPES
    }

    ocr_entities_by_type = {}

    for evidence_type, evidence in evidence_by_type.items():

        ocr_entities_by_type[evidence_type] = (
            _get_ocr_entities(
                db,
                verification_run.id,
                evidence.id
            )
        )

    ocr_availability = {}

    for evidence_type in REQUIRED_EVIDENCE_TYPES:

        entities = ocr_entities_by_type.get(
            evidence_type
        )

        if entities:
            ocr_availability[evidence_type] = {
                "available": bool(
                    entities.get(
                        "text_available",
                        False
                    )
                ),
                "word_count": entities.get(
                    "word_count",
                    0
                ),
                "text_length": entities.get(
                    "text_length",
                    0
                )
            }
        else:
            ocr_availability[evidence_type] = {
                "available": False,
                "word_count": 0,
                "text_length": 0
            }

    match_count = 0
    conflict_count = 0
    not_comparable_count = 0

    entity_comparisons = {}

    # --------------------------------------------------
    # Evidence relationship context
    # --------------------------------------------------

    evidence_relationships = {}

    for evidence_a_type, evidence_b_type in EVIDENCE_PAIRS:

        relationship = get_evidence_relationship(
            evidence_a_type,
            evidence_b_type
        )

        pair_key = (
            f"{evidence_a_type}_"
            f"{evidence_b_type}"
        )

        evidence_relationships[pair_key] = {
            "evidence_a": evidence_a_type,
            "evidence_b": evidence_b_type,
            "relationship": relationship[
                "relationship"
            ],
            "description": relationship[
                "description"
            ]
        }

    # --------------------------------------------------
    # Standard entity comparisons
    # --------------------------------------------------

    for entity_type in COMPARISON_RULES:

        pair_comparisons = []
        entity_match_count = 0
        entity_conflict_count = 0

        for evidence_a_type, evidence_b_type in EVIDENCE_PAIRS:

            entities_a = ocr_entities_by_type.get(
                evidence_a_type
            ) or {}

            entities_b = ocr_entities_by_type.get(
                evidence_b_type
            ) or {}

            values_a = entities_a.get(
                entity_type,
                []
            )

            values_b = entities_b.get(
                entity_type,
                []
            )

            if entity_type == "datetimes":

                identifiers_a = entities_a.get(
                    "identifiers",
                    []
                )

                identifiers_b = entities_b.get(
                    "identifiers",
                    []
                )

                comparison = _compare_datetimes(
                    values_a,
                    values_b,
                    evidence_a_type,
                    evidence_b_type,
                    identifiers_a,
                    identifiers_b
                )

            else:

                comparison = _compare_values(
                    values_a,
                    values_b,
                    evidence_a_type,
                    evidence_b_type
                )

            pair_comparisons.append(comparison)

            if comparison["status"] == "MATCH":
                entity_match_count += 1

            elif comparison["status"] == "CONFLICT":
                entity_conflict_count += 1

        if entity_conflict_count:
            entity_status = "CONFLICT"
        elif entity_match_count:
            entity_status = "MATCH"
        else:
            entity_status = "NOT_COMPARABLE"

        entity_comparisons[entity_type] = {
            "status": entity_status,
            "match_count": entity_match_count,
            "conflict_count": entity_conflict_count,
            "pair_comparisons": pair_comparisons
        }

        match_count += entity_match_count
        conflict_count += entity_conflict_count

        not_comparable_count += sum(
            1
            for comparison in pair_comparisons
            if comparison["status"] == "NOT_COMPARABLE"
        )

    # --------------------------------------------------
    # URLs
    # --------------------------------------------------

    entity_comparisons["urls"] = {
        "status": "NOT_COMPARABLE",
        "reason": (
            "URLs are contextual evidence and are not "
            "currently used as cross-evidence consistency "
            "signals."
        ),
        "pair_comparisons": []
    }

    # --------------------------------------------------
    # Generic amounts
    # --------------------------------------------------

    entity_comparisons["amounts"] = {
        "status": "NOT_COMPARABLE",
        "reason": (
            "Generic monetary values are not used as "
            "cross-evidence consistency signals. "
            "Semantic financial fields are compared "
            "through financial_amounts."
        ),
        "pair_comparisons": []
    }

    # --------------------------------------------------
    # Identifiers
    # --------------------------------------------------

    identifier_pair_comparisons = []
    identifier_match_count = 0
    identifier_conflict_count = 0

    for evidence_a_type, evidence_b_type in EVIDENCE_PAIRS:

        entities_a = ocr_entities_by_type.get(
            evidence_a_type
        ) or {}

        entities_b = ocr_entities_by_type.get(
            evidence_b_type
        ) or {}

        comparison = _compare_identifiers(
            entities_a.get("identifiers", []),
            entities_b.get("identifiers", []),
            evidence_a_type,
            evidence_b_type
        )

        identifier_pair_comparisons.append(
            comparison
        )

        if comparison["status"] == "MATCH":
            identifier_match_count += 1

        elif comparison["status"] == "CONFLICT":
            identifier_conflict_count += 1

    if identifier_conflict_count:
        identifier_status = "CONFLICT"
    elif identifier_match_count:
        identifier_status = "MATCH"
    else:
        identifier_status = "NOT_COMPARABLE"

    entity_comparisons["identifiers"] = {
        "status": identifier_status,
        "match_count": identifier_match_count,
        "conflict_count": identifier_conflict_count,
        "pair_comparisons": (
            identifier_pair_comparisons
        )
    }

    match_count += identifier_match_count
    conflict_count += identifier_conflict_count

    not_comparable_count += sum(
        1
        for comparison in identifier_pair_comparisons
        if comparison["status"] == "NOT_COMPARABLE"
    )

    # --------------------------------------------------
    # Financial semantic relationships
    # --------------------------------------------------

    financial_pair_comparisons = []
    financial_match_count = 0
    financial_conflict_count = 0

    for evidence_a_type, evidence_b_type in EVIDENCE_PAIRS:

        entities_a = ocr_entities_by_type.get(
            evidence_a_type
        ) or {}

        entities_b = ocr_entities_by_type.get(
            evidence_b_type
        ) or {}

        comparison = _compare_financial_amounts(
            entities_a.get(
                "financial_amounts",
                []
            ),
            entities_b.get(
                "financial_amounts",
                []
            ),
            evidence_a_type,
            evidence_b_type
        )

        financial_pair_comparisons.append(
            comparison
        )

        if comparison["status"] == "MATCH":
            financial_match_count += 1

        elif comparison["status"] == "CONFLICT":
            financial_conflict_count += 1

    if financial_conflict_count:
        financial_status = "CONFLICT"
    elif financial_match_count:
        financial_status = "MATCH"
    elif any(
        comparison["status"] == "SEMANTICALLY_RELATED"
        for comparison in financial_pair_comparisons
    ):
        financial_status = "SEMANTICALLY_RELATED"
    else:
        financial_status = "NOT_COMPARABLE"

    entity_comparisons["financial_amounts"] = {
        "status": financial_status,
        "match_count": financial_match_count,
        "conflict_count": financial_conflict_count,
        "pair_comparisons": (
            financial_pair_comparisons
        )
    }

    match_count += financial_match_count
    conflict_count += financial_conflict_count

    not_comparable_count += sum(
        1
        for comparison in financial_pair_comparisons
        if comparison["status"] == "NOT_COMPARABLE"
    )

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------

    if missing_evidence:
        overall_status = "INCOMPLETE"
    else:
        overall_status = "COMPLETED"

    return {
        "status": overall_status,
        "result": {
            "analysis_version": OCR_CROSS_EVIDENCE_VERSION,
            "evidence_count": len(claim.evidence),

            "evidence_types": sorted(
                evidence_by_type.keys()
            ),

            "missing_evidence": missing_evidence,

            "evidence_presence": evidence_presence,

            "required_evidence_present": (
                not missing_evidence
            ),

            "checks": {
                "required_evidence_present": (
                    not missing_evidence
                ),

                "invoice_ocr_available": (
                    ocr_availability["invoice"][
                        "available"
                    ]
                    if "invoice"
                    in ocr_availability
                    else False
                ),

                "product_ocr_available": (
                    ocr_availability["product"][
                        "available"
                    ]
                    if "product"
                    in ocr_availability
                    else False
                ),

                "damage_ocr_available": (
                    ocr_availability["damage"][
                        "available"
                    ]
                    if "damage"
                    in ocr_availability
                    else False
                )
            },

            "ocr_availability": ocr_availability,

            "evidence_relationships": (
                evidence_relationships
            ),

            "comparison_summary": {
                "match_count": match_count,
                "conflict_count": conflict_count,
                "not_comparable_count": (
                    not_comparable_count
                )
            },

            "entity_comparisons": entity_comparisons
        },

        "message": (
            "Applicability-aware cross-evidence "
            "analysis completed with explicit "
            "evidence and semantic relationship context."
        )
    }

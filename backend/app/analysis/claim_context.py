from typing import Dict, List


# --------------------------------------------------
# Evidence-level relationship definitions
# --------------------------------------------------

EVIDENCE_RELATIONSHIPS = {
    ("invoice", "product"): {
        "relationship": "PURCHASE_CONTEXT",
        "description": (
            "Invoice and product evidence may describe "
            "the same claimed purchase."
        )
    },

    ("invoice", "damage"): {
        "relationship": "CLAIM_SUPPORT",
        "description": (
            "Invoice and damage evidence may support "
            "different aspects of the same claim."
        )
    },

    ("product", "damage"): {
        "relationship": "PRODUCT_DAMAGE_CONTEXT",
        "description": (
            "Product and damage evidence may refer to "
            "the same physical item."
        )
    }
}


# --------------------------------------------------
# Financial semantic relationships
# --------------------------------------------------

FINANCIAL_FIELD_RELATIONSHIPS = {
    "PAYMENT_AMOUNT": {
        "semantically_related_to": {
            "COURSE_AMOUNT",
            "TOTAL_AMOUNT",
            "INVOICE_AMOUNT",
            "ORDER_AMOUNT"
        }
    },

    "COURSE_AMOUNT": {
        "semantically_related_to": {
            "PAYMENT_AMOUNT",
            "TOTAL_AMOUNT"
        }
    },

    "TOTAL_AMOUNT": {
        "semantically_related_to": {
            "PAYMENT_AMOUNT",
            "COURSE_AMOUNT",
            "INVOICE_AMOUNT",
            "ORDER_AMOUNT"
        }
    },

    "INVOICE_AMOUNT": {
        "semantically_related_to": {
            "PAYMENT_AMOUNT",
            "TOTAL_AMOUNT",
            "ORDER_AMOUNT"
        }
    },

    "ORDER_AMOUNT": {
        "semantically_related_to": {
            "PAYMENT_AMOUNT",
            "TOTAL_AMOUNT",
            "INVOICE_AMOUNT"
        }
    }
}


# --------------------------------------------------
# Direct comparison rules
# --------------------------------------------------

DIRECTLY_COMPARABLE_FINANCIAL_FIELDS = {
    ("PAYMENT_AMOUNT", "PAYMENT_AMOUNT"),
    ("COURSE_AMOUNT", "COURSE_AMOUNT"),
    ("TOTAL_AMOUNT", "TOTAL_AMOUNT"),
    ("INVOICE_AMOUNT", "INVOICE_AMOUNT"),
    ("ORDER_AMOUNT", "ORDER_AMOUNT"),
}


def get_evidence_relationship(
    evidence_type_a: str,
    evidence_type_b: str
) -> Dict:

    a = evidence_type_a.lower()
    b = evidence_type_b.lower()

    relationship = EVIDENCE_RELATIONSHIPS.get(
        (a, b)
    )

    if relationship:
        return relationship

    relationship = EVIDENCE_RELATIONSHIPS.get(
        (b, a)
    )

    if relationship:
        return relationship

    return {
        "relationship": "UNKNOWN",
        "description": (
            "No explicit evidence relationship has "
            "been defined."
        )
    }


def classify_financial_relationship(
    field_a: str,
    field_b: str
) -> str:

    field_a = field_a.upper()
    field_b = field_b.upper()

    if (
        field_a,
        field_b
    ) in DIRECTLY_COMPARABLE_FINANCIAL_FIELDS:

        return "DIRECTLY_COMPARABLE"

    related_fields = FINANCIAL_FIELD_RELATIONSHIPS.get(
        field_a,
        {}
    ).get(
        "semantically_related_to",
        set()
    )

    if field_b in related_fields:
        return "SEMANTICALLY_RELATED"

    return "NOT_COMPARABLE"


def build_financial_relationship_summary(
    financial_amounts_a: List[Dict],
    financial_amounts_b: List[Dict]
) -> List[Dict]:

    relationships = []

    for amount_a in financial_amounts_a:
        type_a = amount_a.get("type")

        if not type_a:
            continue

        for amount_b in financial_amounts_b:
            type_b = amount_b.get("type")

            if not type_b:
                continue

            relationship = classify_financial_relationship(
                type_a,
                type_b
            )

            relationships.append(
                {
                    "field_a": type_a,
                    "value_a": amount_a.get("value"),
                    "field_b": type_b,
                    "value_b": amount_b.get("value"),
                    "relationship": relationship
                }
            )

    return relationships
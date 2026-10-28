import re

from app.analysis.base import create_analysis_output


# ============================================================
# AMOUNT EXTRACTION
# ============================================================

AMOUNT_PATTERN = re.compile(
    r"(?:₹|Rs\.?|INR)\s*"
    r"\d[\d,]*(?:\.\d{1,2})?"
    r"|"
    r"\b\d[\d,]*(?:\.\d{1,2})?\s*(?:₹|INR)\b",
    re.IGNORECASE
)


# ============================================================
# SEMANTIC FINANCIAL AMOUNTS
# ============================================================

FINANCIAL_AMOUNT_PATTERNS = {

    "PAYMENT_AMOUNT": [
        re.compile(
            r"\bpayment\s+amount"
            r"\s*(?:\([^)]*\))?"
            r"\s*(?:[:=]\s*)?"
            r"(?:₹|Rs\.?|INR|%|\$)?"
            r"\s*"
            r"(\d[\d,]*(?:\.\d{1,2})?)",
            re.IGNORECASE
        )
    ],

    "COURSE_AMOUNT": [
        re.compile(
            r"\bcourse\s+amount"
            r"[\s\S]{0,200}?"
            r"(?:=|:)\s*"
            r"(?:₹|Rs\.?|INR|%|\$)?"
            r"\s*"
            r"(\d[\d,]*(?:\.\d{1,2})?)",
            re.IGNORECASE
        )
    ],

    "TOTAL_AMOUNT": [
        re.compile(
            r"\btotal\s+amount"
            r"\s*(?:[:=]\s*)?"
            r"(?:₹|Rs\.?|INR|%|\$)?"
            r"\s*"
            r"(\d[\d,]*(?:\.\d{1,2})?)",
            re.IGNORECASE
        )
    ],

    "INVOICE_AMOUNT": [
        re.compile(
            r"\binvoice\s+amount"
            r"\s*(?:[:=]\s*)?"
            r"(?:₹|Rs\.?|INR|%|\$)?"
            r"\s*"
            r"(\d[\d,]*(?:\.\d{1,2})?)",
            re.IGNORECASE
        )
    ],

    "ORDER_AMOUNT": [
        re.compile(
            r"\border\s+amount"
            r"\s*(?:[:=]\s*)?"
            r"(?:₹|Rs\.?|INR|%|\$)?"
            r"\s*"
            r"(\d[\d,]*(?:\.\d{1,2})?)",
            re.IGNORECASE
        )
    ]
}


# ============================================================
# DATE / DATETIME EXTRACTION
# ============================================================

DATE_PATTERN = re.compile(
    r"\b"
    r"(?:"
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|"
    r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
    r")"
    r"\b"
)


DATETIME_PATTERN = re.compile(
    r"\b"
    r"(?:"
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|"
    r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
    r")"
    r"\s+"
    r"\d{1,2}:\d{2}"
    r"(?::\d{2})?"
    r"(?:\s+[A-Za-z]{2,5})?"
    r"\b",
    re.IGNORECASE
)


MERGED_DATETIME_PATTERN = re.compile(
    r"\b"
    r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})"
    r"(?:\s*)"
    r"(\d{1,2}:\d{2}(?::\d{2})?)"
    r"(?:([+-]\d{2}:\d{2}))?"
    r"\b"
)


# ============================================================
# URL / EMAIL / PHONE
# ============================================================

URL_PATTERN = re.compile(
    r"\b"
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"(?:[a-zA-Z0-9-]+\.)+"
    r"[a-zA-Z]{2,}"
    r"(?:/[^\s<>\"]*)?"
)


EMAIL_PATTERN = re.compile(
    r"\b"
    r"[A-Za-z0-9._%+-]+"
    r"@"
    r"[A-Za-z0-9.-]+"
    r"\.[A-Za-z]{2,}"
    r"\b"
)


PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\+91[\s-]?)?"
    r"[6-9]\d{9}"
    r"(?!\d)"
)


# ============================================================
# TYPED IDENTIFIERS
# ============================================================

IDENTIFIER_LABELS = {
    "COLLEGE_ORDER_ID": [
        r"college\s+order\s+(?:id|!d|number|no)"
    ],

    "ORDER_ID": [
        r"(?<!college\s)order\s+(?:id|!d|number|no)"
    ],

    "TRANSACTION_ID": [
        r"(?<!bank\s)transaction\s+(?:id|!d|number|no)"
    ],

    "BANK_TRANSACTION_NUMBER": [
        r"bank\s+transaction\s+(?:number|no|id)"
    ],

    "BANK_REFERENCE": [
        r"bank\s+reference\s+(?:number|no|id)"
    ],

    "REFERENCE_ID": [
        r"reference\s+(?:id|!d)"
    ],

    "RECEIPT_ID": [
        r"receipt\s+(?:no|number|id)"
    ]
}


IDENTIFIER_VALUE_PATTERN = (
    r"([A-Za-z0-9][A-Za-z0-9_-]{3,})"
)


STOP_IDENTIFIER_VALUES = {
    "for",
    "future",
    "reference",
    "the",
    "is",
    "successful",
    "details"
}


# ============================================================
# HELPERS
# ============================================================

def unique_values(values):
    return list(dict.fromkeys(values))


def normalize_value(value):
    return re.sub(
        r"\s+",
        " ",
        str(value).strip()
    )


def normalize_identifier(value):
    return re.sub(
        r"[^A-Za-z0-9]",
        "",
        str(value)
    ).upper()


# ============================================================
# IDENTIFIERS
# ============================================================

def extract_labeled_identifiers(text):

    identifiers = []

    for identifier_type, patterns in (
        IDENTIFIER_LABELS.items()
    ):

        for label_pattern in patterns:

            pattern = re.compile(
                r"\b"
                + label_pattern
                + r"\s*[:#-]?\s*"
                + IDENTIFIER_VALUE_PATTERN
                + r"\b",
                re.IGNORECASE
            )

            for match in pattern.finditer(text):

                raw_value = match.group(1)

                normalized = normalize_identifier(
                    raw_value
                )

                if (
                    normalized.lower()
                    in STOP_IDENTIFIER_VALUES
                ):
                    continue

                identifiers.append({
                    "type": identifier_type,
                    "raw": raw_value,
                    "normalized": normalized
                })

    return identifiers


def deduplicate_identifiers(
    identifiers
):

    seen = set()
    result = []

    for identifier in identifiers:

        key = (
            identifier["type"],
            identifier["normalized"]
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(identifier)

    return result


# ============================================================
# GENERIC AMOUNTS
# ============================================================

def extract_amounts(text):

    amounts = []

    for match in AMOUNT_PATTERN.finditer(text):

        amounts.append(
            normalize_value(
                match.group(0)
            )
        )

    return unique_values(amounts)


# ============================================================
# SEMANTIC FINANCIAL AMOUNTS
# ============================================================

def extract_financial_amounts(text):

    financial_amounts = []

    for financial_type, patterns in (
        FINANCIAL_AMOUNT_PATTERNS.items()
    ):

        for pattern in patterns:

            for match in pattern.finditer(text):

                amount = normalize_value(
                    match.group(1)
                )

                financial_amounts.append({
                    "type": financial_type,
                    "value": amount
                })

    return financial_amounts


# ============================================================
# DATETIME
# ============================================================

def extract_datetimes(text):

    datetimes = []

    # --------------------------------------------------------
    # OCR-corrupted merged datetime
    #
    # Example:
    # 2025-07-21119:44:37+05:30
    #
    # The OCR has produced a three-digit hour-like sequence
    # "119". We treat the final two digits ("19") as the
    # intended hour when they form a valid 00-23 hour.
    # --------------------------------------------------------

    OCR_CORRUPTED_DATETIME_PATTERN = re.compile(
        r"\b"
        r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})"
        r"(\d{3})"
        r":(\d{2})"
        r":(\d{2})"
        r"(?:([+-]\d{2}:\d{2}))?"
        r"\b"
    )

    corrupted_datetime_spans = []

    for match in OCR_CORRUPTED_DATETIME_PATTERN.finditer(
        text
    ):

        date_part = match.group(1)
        hour_candidate = match.group(2)[-2:]
        minute = match.group(3)
        second = match.group(4)
        timezone = match.group(5)

        hour = int(hour_candidate)

        if hour > 23:
            continue

        corrected_value = (
            f"{date_part} "
            f"{hour_candidate}:"
            f"{minute}:"
            f"{second}"
        )

        if timezone:
            corrected_value += f" {timezone}"

        datetimes.append(
            normalize_value(corrected_value)
        )

        corrupted_datetime_spans.append(
            match.span()
        )

    # --------------------------------------------------------
    # Normal datetime
    # --------------------------------------------------------

    for match in DATETIME_PATTERN.finditer(
        text
    ):

        # Skip a normal match if it falls inside an
        # OCR-corrupted datetime that we already corrected.
        if any(
            start <= match.start()
            and match.end() <= end
            for start, end in corrupted_datetime_spans
        ):
            continue

        datetimes.append(
            normalize_value(
                match.group(0)
            )
        )

    # --------------------------------------------------------
    # Normal merged datetime
    #
    # Example:
    # 2025-07-2119:44:37+05:30
    # --------------------------------------------------------

    for match in MERGED_DATETIME_PATTERN.finditer(
        text
    ):

        # Skip a merged match if it overlaps an
        # OCR-corrupted datetime that we already corrected.
        if any(
            not (
                match.end() <= start
                or match.start() >= end
            )
            for start, end in corrupted_datetime_spans
        ):
            continue

        date_part = match.group(1)
        time_part = match.group(2)
        timezone = match.group(3)

        value = (
            f"{date_part} "
            f"{time_part}"
        )

        if timezone:
            value += (
                f" {timezone}"
            )

        datetimes.append(
            normalize_value(value)
        )

    return unique_values(datetimes)


# ============================================================
# MAIN OCR ENTITY ANALYZER
# ============================================================

def remove_datetime_from_dates(
    dates,
    datetimes
):
    """
    Remove date values that are already part of
    extracted datetime values.

    Example:
        dates = ["2025-07-21"]
        datetimes = ["2025-07-21 19:44:37 +05:30"]

    Result:
        []
    """

    if not dates:
        return []

    if not datetimes:
        return dates

    filtered_dates = []

    for date_value in dates:

        is_part_of_datetime = any(
            date_value in datetime_value
            for datetime_value in datetimes
        )

        if not is_part_of_datetime:
            filtered_dates.append(date_value)

    return unique_values(filtered_dates)

def extract_ocr_entities(
    evidence,
    ocr_result
):

    if ocr_result is None:

        return create_analysis_output(
            analysis_type="OCR_ENTITIES",
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message=(
                "OCR result is unavailable."
            )
        )

    text = ocr_result.get(
        "text",
        ""
    )

    if not text.strip():

        return create_analysis_output(
            analysis_type="OCR_ENTITIES",
            evidence_id=evidence.id,
            status="COMPLETED",
            result={
                "text_available": False,
                "amounts": [],
                "financial_amounts": [],
                "dates": [],
                "datetimes": [],
                "urls": [],
                "emails": [],
                "phone_numbers": [],
                "identifiers": []
            },
            message=(
                "No OCR text available "
                "for entity extraction."
            )
        )

    amounts = extract_amounts(text)

    financial_amounts = (
        extract_financial_amounts(text)
    )

    datetimes = extract_datetimes(text)

    raw_dates = unique_values(
        normalize_value(
            match.group(0)
        )
        for match in DATE_PATTERN.finditer(text)
    )

    dates = remove_datetime_from_dates(
        raw_dates,
        datetimes
    )

    urls = unique_values(
        normalize_value(
            match.group(0).rstrip(
                ".,);"
            )
        )
        for match in URL_PATTERN.finditer(text)
    )

    emails = unique_values(
        normalize_value(
            match.group(0)
        )
        for match in EMAIL_PATTERN.finditer(text)
    )

    phone_numbers = unique_values(
        normalize_value(
            match.group(0)
        )
        for match in PHONE_PATTERN.finditer(text)
    )

    identifiers = (
        extract_labeled_identifiers(text)
    )

    identifiers = (
        deduplicate_identifiers(
            identifiers
        )
    )

    result = {
        "text_available": True,
        "text_length": len(text),
        "word_count": len(text.split()),
        "amounts": amounts,
        "financial_amounts": financial_amounts,
        "dates": dates,
        "datetimes": datetimes,
        "urls": urls,
        "emails": emails,
        "phone_numbers": phone_numbers,
        "identifiers": identifiers
    }

    return create_analysis_output(
        analysis_type="OCR_ENTITIES",
        evidence_id=evidence.id,
        status="COMPLETED",
        result=result,
        message=(
            "Typed OCR entity extraction completed."
        )
    )
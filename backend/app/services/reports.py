"""Owner-safe, report-ready rendering of persisted TrustLens analysis data."""

from dataclasses import dataclass
from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.analysis import AnalysisInDatabase


DISCLAIMER = (
    "TrustLens provides AI-assisted decision support only. This report is not proof of authenticity, "
    "fraud, manipulation, provenance, ownership, copyright, or intent, and is not a legal or forensic determination."
)


@dataclass(frozen=True)
class ReportSection:
    """Textual report content derived only from one persisted analysis."""

    title: str
    lines: tuple[str, ...]


def collect_report_sections(analysis: AnalysisInDatabase) -> tuple[ReportSection, ...]:
    """Collect all printable report text without adding unrecorded evidence."""
    explanation = analysis.explanation
    trust_score = analysis.trust_score
    signals = analysis.signals

    sections = [
        ReportSection(
            "Report details",
            (
                f"Report name: {analysis.report_title}" if analysis.report_title else "Report name: Default TrustLens report.",
                f"Analysis ID: {analysis.id}",
                f"Created: {analysis.created_at.isoformat()}",
                "Original filename: Not retained with this analysis record.",
                (
                    "Original uploaded image: A normalized owner-authorized source image is retained "
                    "server-side and is not embedded in this PDF."
                    if analysis.image_artifact_filename
                    else "Original uploaded image: Not retained with this analysis record."
                ),
            ),
        ),
        ReportSection(
            "Trust Score",
            (
                f"Score: {trust_score.score}/100" if trust_score is not None else "Score: Not available.",
                f"Category: {trust_score.category}" if trust_score is not None else "Category: Not available.",
            ),
        ),
        ReportSection(
            "Executive summary",
            (
                explanation.overall_summary
                if explanation is not None and explanation.overall_summary
                else "A structured executive summary was not stored for this analysis.",
            ),
        ),
        ReportSection(
            "Explainable AI - Why this score?",
            _score_lines(explanation),
        ),
        _signal_section("Tampering Detection", signals.get("tampering"), explanation.tampering if explanation else None),
        _signal_section("AI-Generated Image Detection", signals.get("ai_generation"), explanation.ai_generated if explanation else None),
        _ocr_section(signals.get("ocr"), explanation.ocr if explanation else None),
        _quality_section(signals.get("quality"), explanation.image_quality if explanation else None),
        _ela_section(signals.get("ela"), explanation.ela if explanation else None),
        ReportSection("Multimodal evidence", _fusion_lines(explanation)),
        ReportSection("Positive / Supporting signals", _factor_lines(explanation, "positive_signals")),
        ReportSection("Caution / Review signals", _factor_lines(explanation, "suspicious_signals")),
        ReportSection("Technical analysis details", _technical_lines(analysis)),
        ReportSection("Limitations", _limitations(analysis)),
        ReportSection("Disclaimer", (DISCLAIMER,)),
    ]
    return tuple(sections)


def build_analysis_report(analysis: AnalysisInDatabase, generated_narrative: str | None = None) -> bytes:
    """Create a PDF from the saved, owner-scoped analysis record only."""
    report_title = analysis.report_title or "Comprehensive image-analysis report"
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.6 * inch,
        title=report_title,
        author="TrustLens",
    )
    styles = _styles()
    story: list[Any] = [
        Paragraph("TRUSTLENS AI", styles["brand"]),
        Paragraph(escape(report_title), styles["title"]),
        Paragraph("Private owner-scoped analysis record", styles["subtitle"]),
        Spacer(1, 0.18 * inch),
    ]

    for section in collect_report_sections(analysis):
        story.append(Paragraph(escape(section.title), styles["heading"]))
        if section.title in {"Trust Score", "Report details"}:
            story.append(_key_value_table(section.lines, styles))
        else:
            story.extend(Paragraph(escape(line), styles["body"]) for line in section.lines)
        story.append(Spacer(1, 0.05 * inch))

    if generated_narrative:
        story.append(Paragraph("AI-generated narrative", styles["heading"]))
        story.append(Paragraph("Generated from saved server-returned facts; decision support, not proof.", styles["body"]))
        story.append(Paragraph(escape(generated_narrative), styles["body"]))

    document.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def _score_lines(explanation: Any) -> tuple[str, ...]:
    if explanation is None or explanation.trust_score is None:
        return ("A structured Trust Score explanation was not stored for this analysis.",)
    score = explanation.trust_score
    lines = [score.explanation or "No Trust Score explanation was returned."]
    lines.extend(f"Supporting signal: {factor.explanation}" for factor in score.contributing_factors)
    lines.extend(f"Review signal: {factor.explanation}" for factor in score.caution_factors)
    return tuple(lines)


def _signal_section(title: str, signal: Any, explanation: Any) -> ReportSection:
    if signal is None:
        return ReportSection(title, ("Status: Not returned by the analysis pipeline.",))
    result = signal.result if isinstance(signal.result, dict) else {}
    lines = [f"Status: {signal.status}"]
    if signal.status == "available":
        if isinstance(result.get("label"), str):
            lines.append(f"Classification: {result['label']}")
        if isinstance(result.get("top_class_softmax_score"), (int, float)):
            lines.append(f"Recorded top-class score: {result['top_class_softmax_score'] * 100:.0f}%")
        if isinstance(result.get("preprocessing_note"), str):
            lines.append(f"Technical note: {result['preprocessing_note']}")
    elif signal.message:
        lines.append(f"Message: {signal.message}")
    if explanation is not None:
        if explanation.interpretation:
            lines.append(f"Interpretation: {explanation.interpretation}")
        if explanation.contribution:
            lines.append(f"Contribution: {explanation.contribution}")
    return ReportSection(title, tuple(lines))


def _ocr_section(signal: Any, explanation: Any) -> ReportSection:
    lines = [f"Status: {signal.status}" if signal is not None else "Status: Not returned by the analysis pipeline."]
    result = signal.result if signal is not None and isinstance(signal.result, dict) else {}
    regions = result.get("regions") if isinstance(result.get("regions"), list) else []
    if signal is not None and signal.status == "available":
        lines.append(f"Text regions returned: {len(regions)}")
        for index, region in enumerate(regions, start=1):
            if isinstance(region, dict):
                text = region.get("text") if isinstance(region.get("text"), str) else "Text unavailable"
                confidence = region.get("confidence")
                suffix = f" (confidence: {confidence * 100:.0f}%)" if isinstance(confidence, (int, float)) else ""
                lines.append(f"OCR region {index}: {text}{suffix}")
    elif signal is not None and signal.message:
        lines.append(f"Message: {signal.message}")
    if explanation is not None and explanation.interpretation:
        lines.append(f"Interpretation: {explanation.interpretation}")
    return ReportSection("OCR Results", tuple(lines))


def _quality_section(signal: Any, explanation: Any) -> ReportSection:
    lines = [f"Status: {signal.status}" if signal is not None else "Status: Not returned by the analysis pipeline."]
    result = signal.result if signal is not None and isinstance(signal.result, dict) else {}
    if signal is not None and signal.status == "available":
        if isinstance(result.get("width"), int) and isinstance(result.get("height"), int):
            lines.append(f"Resolution: {result['width']} x {result['height']}")
        for label, key in (
            ("Mean brightness", "brightness_mean"),
            ("Contrast deviation", "contrast_standard_deviation"),
            ("Sharpness variance", "sharpness_laplacian_variance"),
        ):
            if isinstance(result.get(key), (int, float)):
                lines.append(f"{label}: {result[key]:.2f}")
        if isinstance(result.get("method"), str):
            lines.append(f"Method: {result['method']}")
    elif signal is not None and signal.message:
        lines.append(f"Message: {signal.message}")
    if explanation is not None and explanation.interpretation:
        lines.append(f"Interpretation: {explanation.interpretation}")
    return ReportSection("Image Quality", tuple(lines))


def _ela_section(signal: Any, explanation: Any) -> ReportSection:
    lines = [f"Status: {signal.status}" if signal is not None else "Status: Not returned by the analysis pipeline."]
    result = signal.result if signal is not None and isinstance(signal.result, dict) else {}
    if signal is not None and signal.status == "available":
        for label, key, suffix in (
            ("Mean absolute difference", "mean_absolute_difference", ""),
            ("Differing pixel fraction", "differing_pixel_fraction", "%"),
            ("JPEG recompression quality", "recompression_quality", ""),
        ):
            value = result.get(key)
            if isinstance(value, (int, float)):
                rendered = f"{value * 100:.0f}%" if suffix == "%" else f"{value:.2f}" if isinstance(value, float) else str(value)
                lines.append(f"{label}: {rendered}")
        if isinstance(result.get("method"), str):
            lines.append(f"Method: {result['method']}")
    elif signal is not None and signal.message:
        lines.append(f"Message: {signal.message}")
    if explanation is not None:
        lines.extend(f"Observation: {observation}" for observation in explanation.observations)
        if explanation.interpretation:
            lines.append(f"Interpretation: {explanation.interpretation}")
    lines.append("ELA visualization: Not available because this analysis record does not retain an ELA image artifact.")
    return ReportSection("ELA Analysis", tuple(lines))


def _fusion_lines(explanation: Any) -> tuple[str, ...]:
    if explanation is None or explanation.fusion is None:
        return ("A structured multimodal fusion explanation was not stored for this analysis.",)
    fusion = explanation.fusion
    lines = [fusion.explanation or "No multimodal fusion explanation was returned."]
    if fusion.signals_considered:
        lines.append(f"Signals considered: {', '.join(fusion.signals_considered)}")
    lines.extend(f"Supporting signal: {factor.explanation}" for factor in fusion.positive_signals)
    lines.extend(f"Review signal: {factor.explanation}" for factor in fusion.suspicious_signals)
    lines.extend(f"Returned weight - {name}: {weight * 100:.0f}%" for name, weight in fusion.signal_weights.items())
    return tuple(lines)


def _factor_lines(explanation: Any, attribute: str) -> tuple[str, ...]:
    fusion = explanation.fusion if explanation is not None else None
    factors = getattr(fusion, attribute, ()) if fusion is not None else ()
    if not factors:
        return ("No persisted factors were returned for this section.",)
    return tuple(factor.explanation for factor in factors)


def _technical_lines(analysis: AnalysisInDatabase) -> tuple[str, ...]:
    lines: list[str] = []
    for name, signal in analysis.signals.items():
        result = signal.result if isinstance(signal.result, dict) else {}
        lines.append(f"{name}: {signal.status}")
        method = result.get("method")
        if isinstance(method, str):
            lines.append(f"{name} method: {method}")
    return tuple(lines) or ("No technical signal details were stored for this analysis.",)


def _limitations(analysis: AnalysisInDatabase) -> tuple[str, ...]:
    values: list[str] = []
    if analysis.explanation is not None:
        values.extend(analysis.explanation.limitations)
        if analysis.explanation.fusion is not None:
            values.extend(analysis.explanation.fusion.limitations)
    if analysis.trust_score is not None:
        values.extend(analysis.trust_score.limitations)
    for signal in analysis.signals.values():
        result = signal.result if isinstance(signal.result, dict) else {}
        limitations = result.get("limitations")
        if isinstance(limitations, (list, tuple)):
            values.extend(item for item in limitations if isinstance(item, str))
    if not values:
        values.append("No structured limitations were stored for this analysis. Treat all signals as decision support, not proof.")
    return tuple(dict.fromkeys(values))


def _key_value_table(lines: tuple[str, ...], styles: dict[str, ParagraphStyle]) -> Table:
    rows = []
    for line in lines:
        key, value = line.split(": ", 1) if ": " in line else ("Detail", line)
        rows.append([Paragraph(escape(key), styles["table_key"]), Paragraph(escape(value), styles["table_value"])])
    table = Table(rows, colWidths=[1.55 * inch, 5.65 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle("TrustLensBrand", parent=base["BodyText"], textColor=colors.HexColor("#0F766E"), fontName="Helvetica-Bold", fontSize=9, leading=11, spaceAfter=5),
        "title": ParagraphStyle("TrustLensTitle", parent=base["Title"], textColor=colors.HexColor("#102A43"), fontName="Helvetica-Bold", fontSize=21, leading=25, spaceAfter=4),
        "subtitle": ParagraphStyle("TrustLensSubtitle", parent=base["BodyText"], textColor=colors.HexColor("#526B84"), fontSize=9.5, leading=13),
        "heading": ParagraphStyle("TrustLensHeading", parent=base["Heading2"], textColor=colors.HexColor("#102A43"), fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=3, spaceAfter=6),
        "body": ParagraphStyle("TrustLensBody", parent=base["BodyText"], textColor=colors.HexColor("#334E68"), fontSize=9, leading=11, spaceAfter=2),
        "table_key": ParagraphStyle("TrustLensTableKey", parent=base["BodyText"], textColor=colors.HexColor("#102A43"), fontName="Helvetica-Bold", fontSize=8, leading=10),
        "table_value": ParagraphStyle("TrustLensTableValue", parent=base["BodyText"], textColor=colors.HexColor("#334E68"), fontSize=8, leading=10),
    }


def _page_footer(pdf: Any, _document: Any) -> None:
    pdf.saveState()
    pdf.setStrokeColor(colors.HexColor("#CBD5E1"))
    pdf.line(0.65 * inch, 0.45 * inch, 7.85 * inch, 0.45 * inch)
    pdf.setFillColor(colors.HexColor("#526B84"))
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(0.65 * inch, 0.28 * inch, "TrustLens AI - decision support, not proof")
    pdf.drawRightString(7.85 * inch, 0.28 * inch, f"Page {pdf.getPageNumber()}")
    pdf.restoreState()

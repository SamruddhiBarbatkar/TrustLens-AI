import { useEffect, useMemo, useState } from "react";
import {
    Camera,
    CheckCircle,
    Circle,
    FileText,
    Package,
    SpinnerGap,
    WarningCircle,
} from "@phosphor-icons/react";
import { getVerificationRun } from "../services/verificationService";


const EVIDENCE_STAGES = [
    "IMAGE_QUALITY",
    "QUALITY_GATE",
    "FORENSICS",
    "TAMPERING_DETECTION",
    "TAMPERING_MULTIVIEW_CANDIDATE",
    "TAMPERING_RESNET_SHADOW",
    "AI_GENERATION",
    "METADATA",
    "OCR",
    "OCR_ENTITIES",
];

const GLOBAL_STAGES = [
    "CROSS_EVIDENCE",
    "FUSION",
    "UNCERTAINTY",
    "TRUST_ASSESSMENT",
];

const STAGE_LABELS = {
    IMAGE_QUALITY: "Image Quality",
    QUALITY_GATE: "Quality Gate",
    FORENSICS: "Forensics",
    TAMPERING_DETECTION: "Tampering Detection",
    TAMPERING_MULTIVIEW_CANDIDATE: "Global + Patch Candidate",
    TAMPERING_RESNET_SHADOW: "ResNet Research Signal",
    AI_GENERATION: "AI Generation",
    METADATA: "Metadata",
    OCR: "OCR",
    OCR_ENTITIES: "OCR Entities",
    EVIDENCE_RELIABILITY: "Evidence Reliability",
    CROSS_EVIDENCE: "Cross-Evidence",
    FUSION: "Fusion",
    UNCERTAINTY: "Uncertainty",
    TRUST_ASSESSMENT: "Trust Assessment",
};

const EVIDENCE_ICONS = {
    invoice: FileText,
    product: Package,
    damage: Camera,
};

const EVIDENCE_LABELS = {
    invoice: "Invoice",
    product: "Product",
    damage: "Damage",
};


function formatEvidenceType(type, index) {
    if (!type) {
        return `Evidence ${index + 1}`;
    }

    const normalized = String(type).toLowerCase();

    return (
        EVIDENCE_LABELS[normalized] ||
        normalized
            .replaceAll("_", " ")
            .replace(/\b\w/g, (letter) => letter.toUpperCase())
    );
}


function getEvidenceIcon(type) {
    const normalized = String(type || "").toLowerCase();
    const Icon = EVIDENCE_ICONS[normalized] || FileText;

    return <Icon aria-hidden="true" />;
}


function getResult(analysis) {
    return analysis?.result || {};
}


function getStageState(analysis) {
    if (!analysis) {
        return {
            label: "Not available",
            type: "neutral",
        };
    }

    const result = getResult(analysis);

    if (analysis.status === "ERROR") {
        return {
            label: "Error",
            type: "error",
        };
    }

    if (
        analysis.status === "MODEL_UNAVAILABLE" ||
        analysis.status === "NOT_SUPPORTED"
    ) {
        return {
            label: "Unavailable",
            type: "warning",
        };
    }

    if (analysis.analysis_type === "QUALITY_GATE") {
        const qualityStatus = result?.quality_status;

        if (qualityStatus === "WARNING") {
            return {
                label: "Warning",
                type: "warning",
            };
        }

        if (qualityStatus === "POOR") {
            return {
                label: "Poor Quality",
                type: "warning",
            };
        }

        if (qualityStatus === "GOOD") {
            return {
                label: "Good",
                type: "success",
            };
        }
    }

    if (analysis.analysis_type === "AI_GENERATION") {
        if (result.prediction === "AI_GENERATED") {
            return {
                label: "AI Generated",
                type: "warning",
            };
        }

        if (result.prediction === "REAL") {
            return {
                label: "Real",
                type: "success",
            };
        }
    }

    if ([
        "TAMPERING_DETECTION",
        "TAMPERING_MULTIVIEW_CANDIDATE",
        "TAMPERING_RESNET_SHADOW",
    ].includes(analysis.analysis_type)) {
        if (result.prediction === "TAMPERED") {
            return {
                label: "Tampering Signal",
                type: "warning",
            };
        }

        if (result.prediction === "AUTHENTIC") {
            return {
                label: "Authentic Signal",
                type: "success",
            };
        }
    }

    if (analysis.status === "COMPLETED") {
        return {
            label: "Completed",
            type: "success",
        };
    }

    return {
        label: analysis.status || "Pending",
        type: "neutral",
    };
}


function formatPercentage(value) {
    if (value === null || value === undefined) {
        return null;
    }

    const number = Number(value);

    if (Number.isNaN(number)) {
        return null;
    }

    return `${(number * 100).toFixed(2)}%`;
}


function getStageDescription(analysis) {
    if (!analysis) {
        return "This analysis was not available.";
    }

    const result = getResult(analysis);

    switch (analysis.analysis_type) {
        case "AI_GENERATION": {
            if (result.prediction === "AI_GENERATED") {
                return `AI-generation signal: ${formatPercentage(
                    result.ai_generated_probability
                )}`;
            }

            if (result.prediction === "REAL") {
                return `Real-image signal: ${formatPercentage(
                    result.real_image_probability
                )}`;
            }

            return "AI-generation analysis completed.";
        }

        case "TAMPERING_DETECTION": {
            if (result.prediction === "TAMPERED") {
                return `Tampering signal: ${formatPercentage(
                    result.tampered_probability
                )}`;
            }

            if (result.prediction === "AUTHENTIC") {
                return `Authentic-image signal: ${formatPercentage(
                    result.authentic_probability
                )}`;
            }

            return "Tampering analysis was unavailable.";
        }

        case "TAMPERING_MULTIVIEW_CANDIDATE": {
            if (analysis.status === "SKIPPED") {
                return "Research comparison is disabled. It never affects the Trust Score.";
            }
            const probability = formatPercentage(result.tampered_probability);
            return (
                `Research-only global-and-patch result${probability ? `: ${probability} tampering signal` : ""}. ` +
                "Excluded from the Trust Score until external calibration passes."
            );
        }

        case "TAMPERING_RESNET_SHADOW":
            return (
                "Research-only ResNet comparison. " +
                "This output is excluded from the Trust Score."
            );

        case "QUALITY_GATE":
            if (result.quality_status === "WARNING") {
                return (
                    result.reasons?.join(" ") ||
                    "Image quality contains one or more warnings."
                );
            }

            if (result.quality_status === "GOOD") {
                return "No quality warning was detected by the current baseline gate.";
            }

            return analysis.message || "Evidence quality gate completed.";

        case "FORENSICS":
            return (
                "Forensic indicators were extracted. " +
                "These indicators are not an independent tampering verdict."
            );

        case "IMAGE_QUALITY":
            return "Image quality characteristics were measured.";

        case "METADATA":
            return "Image metadata and provenance signals were inspected.";

        case "OCR":
            return "Text was extracted from the evidence image.";

        case "OCR_ENTITIES":
            return "Structured entities were extracted from the OCR text.";

        case "EVIDENCE_RELIABILITY":
            return (
                result.profile_status === "READY"
                    ? "Evidence has all currently required analysis signals."
                    : "Evidence contains one or more reliability limitations."
            );

        default:
            return (
                analysis.message ||
                `${STAGE_LABELS[analysis.analysis_type] || analysis.analysis_type
                } analysis completed.`
            );
    }
}


function StatusPill({ state }) {
    return (
        <span
            style={{
                ...styles.statusPill,
                ...(state.type === "success"
                    ? styles.statusSuccess
                    : state.type === "warning"
                        ? styles.statusWarning
                        : state.type === "error"
                            ? styles.statusError
                            : styles.statusNeutral),
            }}
        >
            {state.label}
        </span>
    );
}


function StageRow({ analysis }) {
    const state = getStageState(analysis);

    return (
        <div style={styles.stageRow}>
            <div style={styles.stageLeft}>
                <div
                    style={{
                        ...styles.stageIcon,
                        ...(state.type === "success"
                            ? styles.stageIconSuccess
                            : state.type === "warning"
                                ? styles.stageIconWarning
                                : styles.stageIconNeutral),
                    }}
                >
                    {state.type === "success"
                        ? <CheckCircle aria-hidden="true" />
                        : state.type === "warning"
                            ? <WarningCircle aria-hidden="true" />
                            : <Circle aria-hidden="true" />}
                </div>

                <div style={styles.stageText}>
                    <div style={styles.stageTitle}>
                        {STAGE_LABELS[analysis?.analysis_type] ||
                            analysis?.analysis_type ||
                            "Analysis"}
                    </div>

                    <div style={styles.stageDescription}>
                        {getStageDescription(analysis)}
                    </div>
                </div>
            </div>

            <StatusPill state={state} />
        </div>
    );
}


function EvidenceCard({ evidence, index }) {
    const stages = evidence.stages;

    const reliability = evidence.reliability;

    const aiAnalysis = stages.AI_GENERATION;

    const aiResult = getResult(aiAnalysis);

    const reliabilityResult = getResult(reliability);

    return (
        <div style={styles.evidenceCard}>
            <div className="verification-evidence-header" style={styles.evidenceHeader}>
                <div style={styles.evidenceIdentity}>
                    <div style={styles.evidenceIcon}>
                        {getEvidenceIcon(evidence.evidenceType)}
                    </div>

                    <div>
                        <div style={styles.evidenceNumber}>
                            Evidence {index + 1}
                        </div>

                        <div style={styles.evidenceTitle}>
                            {formatEvidenceType(
                                evidence.evidenceType,
                                index
                            )}
                        </div>

                        <div style={styles.evidenceId}>
                            Evidence ID #{evidence.evidenceId}
                        </div>
                    </div>
                </div>

                <div style={styles.evidenceSummary}>
                    {aiAnalysis && (
                        <StatusPill
                            state={getStageState(aiAnalysis)}
                        />
                    )}
                </div>
            </div>

            {aiAnalysis && (
                <div className="verification-ai-highlight" style={styles.aiHighlight}>
                    <div>
                        <div style={styles.aiLabel}>
                            AI-generation signal
                        </div>

                        <div style={styles.aiPrediction}>
                            {aiResult.prediction === "AI_GENERATED"
                                ? "AI Generated"
                                : aiResult.prediction === "REAL"
                                    ? "Real"
                                    : "Unavailable"}
                        </div>
                    </div>

                    <div style={styles.aiMetric}>
                        <div style={styles.aiMetricLabel}>
                            Signal
                        </div>

                        <div style={styles.aiMetricValue}>
                            {aiResult.prediction === "AI_GENERATED"
                                ? formatPercentage(
                                    aiResult.ai_generated_probability
                                )
                                : aiResult.prediction === "REAL"
                                    ? formatPercentage(
                                        aiResult.real_image_probability
                                    )
                                    : "—"}
                        </div>
                    </div>

                    <div style={styles.aiMetric}>
                        <div style={styles.aiMetricLabel}>
                            Model
                        </div>

                        <div style={styles.aiMetricValueSmall}>
                            {aiResult.model_name || "—"}
                        </div>
                    </div>
                </div>
            )}

            <div style={styles.stageList}>
                {EVIDENCE_STAGES.map((stage) => (
                    <StageRow
                        key={`${evidence.evidenceId}-${stage}`}
                        analysis={stages[stage]}
                    />
                ))}
            </div>

            {reliability && (
                <div className="verification-reliability-box" style={styles.reliabilityBox}>
                    <div>
                        <div style={styles.reliabilityTitle}>
                            Evidence Reliability
                        </div>

                        <div style={styles.reliabilityText}>
                            {reliabilityResult.profile_status === "READY"
                                ? "All currently required analysis signals are available."
                                : reliabilityResult.reliability_factors?.join(
                                    " • "
                                ) ||
                                "Evidence has one or more reliability limitations."}
                        </div>
                    </div>

                    <StatusPill
                        state={{
                            label:
                                reliabilityResult.profile_status ||
                                "Completed",
                            type:
                                reliabilityResult.profile_status ===
                                    "READY"
                                    ? "success"
                                    : "warning",
                        }}
                    />
                </div>
            )}
        </div>
    );
}


function GlobalStageCard({ analysis }) {
    const result = getResult(analysis);

    let extraText = analysis?.message || "";

    if (analysis?.analysis_type === "TRUST_ASSESSMENT") {
        if (result.assessment) {
            extraText = `Final baseline assessment: ${result.assessment}.`;
        }
    }

    if (analysis?.analysis_type === "CROSS_EVIDENCE") {
        const comparisonSummary =
            result.comparison_summary || {};

        const matchCount = comparisonSummary.match_count ?? 0;
        const conflictCount = comparisonSummary.conflict_count ?? 0;
        const notComparableCount =
            comparisonSummary.not_comparable_count ?? 0;

        extraText =
            `Matches: ${matchCount} • ` +
            `Conflicts: ${conflictCount} • ` +
            `Not comparable: ${notComparableCount}`;
    }

    if (analysis?.analysis_type === "FUSION") {
        extraText =
            "Evidence-aware baseline signals were assembled. " +
            "Current fusion is descriptive and does not produce calibrated authenticity probabilities.";
    }

    if (analysis?.analysis_type === "UNCERTAINTY") {
        extraText =
            "Diagnostic uncertainty factors were assessed without producing calibrated probability scores.";
    }

    return (
        <div style={styles.globalCard}>
            <div style={styles.globalIcon}>
                <CheckCircle aria-hidden="true" />
            </div>

            <div style={styles.globalContent}>
                <div style={styles.globalTitle}>
                    {STAGE_LABELS[analysis?.analysis_type] ||
                        analysis?.analysis_type}
                </div>

                <div style={styles.globalDescription}>
                    {extraText}
                </div>
            </div>

            <StatusPill
                state={{
                    label:
                        analysis?.status === "COMPLETED"
                            ? "Completed"
                            : analysis?.status || "Pending",
                    type:
                        analysis?.status === "COMPLETED"
                            ? "success"
                            : "warning",
                }}
            />
        </div>
    );
}


export default function VerificationProgress({ runId }) {
    const [verification, setVerification] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        let cancelled = false;

        async function loadVerification() {
            if (!runId) {
                setLoading(false);
                return;
            }

            try {
                setLoading(true);
                setError("");

                const result = await getVerificationRun(runId);

                if (!cancelled) {
                    setVerification(result);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(
                        err?.message ||
                        "Unable to load verification results."
                    );
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        loadVerification();

        return () => {
            cancelled = true;
        };
    }, [runId]);


    const analysisResults = useMemo(
        () => verification?.analysis_results || [],
        [verification]
    );

    const completedCount = analysisResults.filter(
        (item) => item.status === "COMPLETED"
    ).length;

    const totalCount = analysisResults.length;

    const completionRatio =
        totalCount > 0
            ? Math.round((completedCount / totalCount) * 100)
            : 0;


    const { evidenceGroups, globalAnalyses } = useMemo(() => {
        const groups = new Map();

        const global = {};

        const fusionAnalysis = analysisResults.find(
            (item) => item.analysis_type === "FUSION"
        );

        const fusionDimensions =
            fusionAnalysis?.result?.fusion_inputs?.evidence_dimensions ||
            {};

        const reliabilityResults = analysisResults.filter(
            (item) =>
                item.analysis_type ===
                "EVIDENCE_RELIABILITY"
        );

        for (const analysis of analysisResults) {
            if (GLOBAL_STAGES.includes(analysis.analysis_type)) {
                global[analysis.analysis_type] = analysis;
                continue;
            }

            if (
                analysis.analysis_type ===
                "EVIDENCE_RELIABILITY"
            ) {
                continue;
            }

            if (!analysis.evidence_id) {
                continue;
            }

            const evidenceId = String(analysis.evidence_id);

            if (!groups.has(evidenceId)) {
                groups.set(evidenceId, {
                    evidenceId: analysis.evidence_id,
                    evidenceType:
                        fusionDimensions[evidenceId]
                            ?.evidence_type ||
                        null,
                    stages: {},
                    reliability: null,
                });
            }

            const group = groups.get(evidenceId);

            group.stages[analysis.analysis_type] =
                analysis;

            if (!group.evidenceType) {
                group.evidenceType =
                    fusionDimensions[evidenceId]
                        ?.evidence_type ||
                    null;
            }
        }

        for (const reliability of reliabilityResults) {
            const evidenceId = String(
                reliability.evidence_id
            );

            if (!groups.has(evidenceId)) {
                groups.set(evidenceId, {
                    evidenceId: reliability.evidence_id,
                    evidenceType:
                        reliability.result?.evidence_type ||
                        null,
                    stages: {},
                    reliability,
                });
            } else {
                groups.get(evidenceId).reliability =
                    reliability;

                if (
                    !groups.get(evidenceId).evidenceType
                ) {
                    groups.get(evidenceId).evidenceType =
                        reliability.result?.evidence_type ||
                        null;
                }
            }
        }

        const sortedGroups = Array.from(groups.values()).sort(
            (a, b) =>
                Number(a.evidenceId) -
                Number(b.evidenceId)
        );

        return {
            evidenceGroups: sortedGroups,
            globalAnalyses: GLOBAL_STAGES
                .map((stage) => global[stage])
                .filter(Boolean),
        };
    }, [analysisResults]);


    const trustAssessment = globalAnalyses.find(
        (item) =>
            item.analysis_type === "TRUST_ASSESSMENT"
    );

    const trustResult = getResult(trustAssessment);


    if (loading) {
        return (
            <div className="verification-progress-page" style={styles.page}>
                <div style={styles.loadingCard}>
                    <div style={styles.loadingSpinner}>
                        <SpinnerGap aria-label="Loading" />
                    </div>
                    <h2 style={styles.loadingTitle}>
                        Loading verification...
                    </h2>
                    <p style={styles.loadingText}>
                        Retrieving TrustLens analysis results.
                    </p>
                </div>
            </div>
        );
    }


    if (error) {
        return (
            <div className="verification-progress-page" style={styles.page}>
                <div style={styles.errorCard}>
                    <div style={styles.errorIcon}>!</div>

                    <h2 style={styles.errorTitle}>
                        Unable to load verification
                    </h2>

                    <p style={styles.errorText}>
                        {error}
                    </p>

                    <p style={styles.errorHint}>
                        Verification Run #{runId}
                    </p>
                </div>
            </div>
        );
    }


    if (!verification) {
        return (
            <div className="verification-progress-page" style={styles.page}>
                <div style={styles.errorCard}>
                    <h2 style={styles.errorTitle}>
                        Verification not found
                    </h2>

                    <p style={styles.errorText}>
                        No verification data was returned for
                        this run.
                    </p>
                </div>
            </div>
        );
    }


    return (
        <div className="verification-progress-page" style={styles.page}>
            <div style={styles.container}>

                {/* Header */}
                <div className="verification-page-header" style={styles.header}>
                    <div>
                        <div style={styles.eyebrow}>
                            TrustLens verification
                        </div>

                        <h1 style={styles.title}>
                            Verification Run #{verification.id}
                        </h1>

                        <p style={styles.subtitle}>
                            Evidence analysis and decision
                            support pipeline.
                        </p>
                    </div>

                    <StatusPill
                        state={{
                            label:
                                verification.status ===
                                    "COMPLETED"
                                    ? "Completed"
                                    : verification.status,
                            type:
                                verification.status ===
                                    "COMPLETED"
                                    ? "success"
                                    : "warning",
                        }}
                    />
                </div>


                {/* Completion */}
                <div style={styles.completionCard}>
                    <div className="verification-completion-header" style={styles.completionHeader}>
                        <div>
                            <div style={styles.sectionLabel}>
                                Pipeline completion
                            </div>

                            <div style={styles.completionValue}>
                                {completionRatio}%
                            </div>
                        </div>

                        <div style={styles.completionCount}>
                            {completedCount} / {totalCount} analyses
                            completed
                        </div>
                    </div>

                    <div style={styles.progressTrack}>
                        <div
                            style={{
                                ...styles.progressBar,
                                width: `${completionRatio}%`,
                            }}
                        />
                    </div>
                </div>


                {/* Final Assessment */}
                {trustAssessment && (
                    <div
                        className="verification-assessment-card"
                        style={{
                            ...styles.assessmentCard,
                            ...(trustResult.assessment ===
                                "REVIEW_NEEDED"
                                ? styles.assessmentReview
                                : {}),
                        }}
                    >
                        <div>
                            <div style={styles.sectionLabel}>
                                TrustLens calibrated assessment
                            </div>

                            <div style={styles.assessmentTitle}>
                                {trustResult.assessment ||
                                    "Assessment available"}
                            </div>

                            <div style={styles.assessmentText}>
                                {trustResult.assessment_basis ||
                                    "The baseline assessment is based on the currently available evidence and analysis signals."}
                            </div>
                        </div>

                        <div style={styles.assessmentBadge}>
                            {trustResult.assessment ||
                                "REVIEW"}
                        </div>
                    </div>
                )}


                {/* Evidence */}
                <div style={styles.sectionHeader}>
                    <div>
                        <div style={styles.sectionLabel}>
                            Evidence analysis
                        </div>

                        <h2 style={styles.sectionTitle}>
                            Evidence-level results
                        </h2>

                        <p style={styles.sectionDescription}>
                            Each uploaded evidence item is
                            evaluated independently before
                            cross-evidence analysis.
                        </p>
                    </div>
                </div>


                <div style={styles.evidenceList}>
                    {evidenceGroups.map((evidence, index) => (
                        <EvidenceCard
                            key={evidence.evidenceId}
                            evidence={evidence}
                            index={index}
                        />
                    ))}
                </div>


                {/* Decision Pipeline */}
                <div style={styles.sectionHeader}>
                    <div>
                        <div style={styles.sectionLabel}>
                            Decision pipeline
                        </div>

                        <h2 style={styles.sectionTitle}>
                            Cross-evidence and assessment
                        </h2>

                        <p style={styles.sectionDescription}>
                            These stages combine and interpret
                            the evidence-level signals.
                        </p>
                    </div>
                </div>


                <div style={styles.globalList}>
                    {globalAnalyses.map((analysis) => (
                        <GlobalStageCard
                            key={analysis.id}
                            analysis={analysis}
                        />
                    ))}
                </div>


                {/* Research note */}
                <div style={styles.researchNote}>
                    <div style={styles.researchNoteTitle}>
                        Research interpretation
                    </div>

                    <div style={styles.researchNoteText}>
                        AI-generation predictions, forensic
                        indicators, and fusion observations are
                        research signals. They should not be
                        interpreted as independently calibrated
                        authenticity probabilities or definitive
                        fraud conclusions.
                    </div>
                </div>

            </div>
        </div>
    );
}


const styles = {
    page: {
        minHeight: "100vh",
        background:
            "linear-gradient(180deg, #f6f9fc 0%, #eef3f7 100%)",
        padding: "42px 24px 80px",
        boxSizing: "border-box",
        fontFamily:
            "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        color: "#18212b",
    },

    container: {
        width: "100%",
        maxWidth: "1120px",
        margin: "0 auto",
    },

    header: {
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        gap: "24px",
        marginBottom: "28px",
    },

    eyebrow: {
        fontSize: "12px",
        fontWeight: 700,
        letterSpacing: "0.18em",
        color: "#718096",
        marginBottom: "10px",
    },

    title: {
        margin: 0,
        fontSize: "32px",
        lineHeight: 1.15,
        fontWeight: 750,
        letterSpacing: "-0.025em",
    },

    subtitle: {
        margin: "10px 0 0",
        color: "#718096",
        fontSize: "14px",
    },

    statusPill: {
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: "82px",
        padding: "6px 11px",
        borderRadius: "999px",
        fontSize: "12px",
        fontWeight: 700,
        whiteSpace: "nowrap",
    },

    statusSuccess: {
        background: "#dcf5e7",
        color: "#28764c",
    },

    statusWarning: {
        background: "#fff0cf",
        color: "#94651b",
    },

    statusError: {
        background: "#fde2e2",
        color: "#a33a3a",
    },

    statusNeutral: {
        background: "#e8edf2",
        color: "#667381",
    },

    completionCard: {
        background: "#ffffff",
        border: "1px solid #e4eaf0",
        borderRadius: "20px",
        padding: "24px 26px",
        boxShadow: "0 12px 30px rgba(44, 62, 80, 0.08)",
        marginBottom: "22px",
    },

    completionHeader: {
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        gap: "20px",
    },

    sectionLabel: {
        fontSize: "12px",
        letterSpacing: "0.14em",
        fontWeight: 750,
        color: "#8995a3",
    },

    completionValue: {
        fontSize: "34px",
        fontWeight: 800,
        lineHeight: 1,
        marginTop: "6px",
    },

    completionCount: {
        fontSize: "14px",
        color: "#7a8795",
        paddingBottom: "3px",
    },

    progressTrack: {
        height: "8px",
        borderRadius: "999px",
        background: "#e9eef3",
        overflow: "hidden",
        marginTop: "18px",
    },

    progressBar: {
        height: "100%",
        borderRadius: "999px",
        background:
            "linear-gradient(90deg, #5669f6 0%, #6678ff 100%)",
        transition: "width 0.4s ease",
    },

    assessmentCard: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "24px",
        background: "#ffffff",
        border: "1px solid #e4eaf0",
        borderRadius: "20px",
        padding: "24px 26px",
        marginBottom: "40px",
        boxShadow: "0 12px 30px rgba(44, 62, 80, 0.07)",
    },

    assessmentReview: {
        borderColor: "#eadfbf",
    },

    assessmentTitle: {
        fontSize: "23px",
        fontWeight: 800,
        marginTop: "7px",
        letterSpacing: "-0.015em",
    },

    assessmentText: {
        color: "#697786",
        fontSize: "14px",
        lineHeight: 1.55,
        marginTop: "7px",
        maxWidth: "700px",
    },

    assessmentBadge: {
        padding: "9px 14px",
        borderRadius: "999px",
        background: "#fff0cf",
        color: "#94651b",
        fontSize: "12px",
        fontWeight: 800,
        whiteSpace: "nowrap",
    },

    sectionHeader: {
        marginBottom: "18px",
    },

    sectionTitle: {
        margin: "5px 0 0",
        fontSize: "22px",
        fontWeight: 750,
        letterSpacing: "-0.015em",
    },

    sectionDescription: {
        margin: "7px 0 0",
        fontSize: "14px",
        color: "#7a8795",
    },

    evidenceList: {
        display: "grid",
        gap: "18px",
        marginBottom: "46px",
    },

    evidenceCard: {
        background: "#ffffff",
        border: "1px solid #e2e8ee",
        borderRadius: "20px",
        padding: "22px",
        boxShadow: "0 10px 26px rgba(44, 62, 80, 0.065)",
    },

    evidenceHeader: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "20px",
        paddingBottom: "18px",
        borderBottom: "1px solid #edf1f4",
    },

    evidenceIdentity: {
        display: "flex",
        alignItems: "center",
        gap: "14px",
    },

    evidenceIcon: {
        width: "48px",
        height: "48px",
        borderRadius: "14px",
        background: "#f1f5f8",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "22px",
    },

    evidenceNumber: {
        fontSize: "12px",
        color: "#8995a3",
        fontWeight: 700,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
    },

    evidenceTitle: {
        fontSize: "18px",
        fontWeight: 750,
        marginTop: "2px",
    },

    evidenceId: {
        fontSize: "12px",
        color: "#8995a3",
        marginTop: "3px",
    },

    evidenceSummary: {
        display: "flex",
        alignItems: "center",
    },

    aiHighlight: {
        display: "grid",
        gridTemplateColumns:
            "minmax(180px, 1fr) minmax(120px, 160px) minmax(140px, 180px)",
        gap: "18px",
        marginTop: "18px",
        padding: "16px 18px",
        borderRadius: "14px",
        background: "#f6f8ff",
        border: "1px solid #e4e8ff",
    },

    aiLabel: {
        fontSize: "12px",
        letterSpacing: "0.12em",
        fontWeight: 800,
        color: "#7a86a8",
    },

    aiPrediction: {
        fontSize: "17px",
        fontWeight: 800,
        marginTop: "4px",
    },

    aiMetric: {
        borderLeft: "1px solid #e0e5f5",
        paddingLeft: "18px",
    },

    aiMetricLabel: {
        fontSize: "12px",
        color: "#8792a3",
    },

    aiMetricValue: {
        fontSize: "18px",
        fontWeight: 800,
        marginTop: "3px",
    },

    aiMetricValueSmall: {
        fontSize: "14px",
        fontWeight: 700,
        marginTop: "6px",
    },

    stageList: {
        marginTop: "16px",
        display: "grid",
        gap: "7px",
    },

    stageRow: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "18px",
        padding: "12px 13px",
        borderRadius: "12px",
        background: "#f8fafb",
        border: "1px solid #edf1f4",
    },

    stageLeft: {
        display: "flex",
        alignItems: "center",
        gap: "11px",
        minWidth: 0,
    },

    stageIcon: {
        flexShrink: 0,
        width: "25px",
        height: "25px",
        borderRadius: "50%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "12px",
        fontWeight: 800,
    },

    stageIconSuccess: {
        background: "#e0f5e9",
        color: "#34805a",
    },

    stageIconWarning: {
        background: "#fff0d0",
        color: "#9b6a1e",
    },

    stageIconNeutral: {
        background: "#e8edf2",
        color: "#697887",
    },

    stageText: {
        minWidth: 0,
    },

    stageTitle: {
        fontSize: "14px",
        fontWeight: 750,
    },

    stageDescription: {
        marginTop: "2px",
        color: "#8995a3",
        fontSize: "13px",
        lineHeight: 1.4,
    },

    reliabilityBox: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
        marginTop: "12px",
        padding: "14px 16px",
        borderRadius: "13px",
        background: "#f5f7f9",
        border: "1px solid #e8edf1",
    },

    reliabilityTitle: {
        fontSize: "13px",
        fontWeight: 750,
    },

    reliabilityText: {
        fontSize: "13px",
        color: "#7d8995",
        marginTop: "3px",
    },

    globalList: {
        display: "grid",
        gap: "10px",
        marginBottom: "28px",
    },

    globalCard: {
        display: "flex",
        alignItems: "center",
        gap: "14px",
        background: "#ffffff",
        border: "1px solid #e3e9ee",
        borderRadius: "16px",
        padding: "17px 18px",
        boxShadow: "0 7px 20px rgba(44, 62, 80, 0.05)",
    },

    globalIcon: {
        flexShrink: 0,
        width: "30px",
        height: "30px",
        borderRadius: "50%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#e0f5e9",
        color: "#34805a",
        fontWeight: 800,
        fontSize: "13px",
    },

    globalContent: {
        flex: 1,
        minWidth: 0,
    },

    globalTitle: {
        fontSize: "14px",
        fontWeight: 750,
    },

    globalDescription: {
        marginTop: "4px",
        color: "#7d8995",
        fontSize: "13px",
        lineHeight: 1.45,
    },

    researchNote: {
        padding: "18px 20px",
        borderRadius: "16px",
        background: "#f5f7f9",
        border: "1px solid #e5eaf0",
    },

    researchNoteTitle: {
        fontSize: "13px",
        fontWeight: 800,
        color: "#536171",
    },

    researchNoteText: {
        marginTop: "5px",
        fontSize: "13px",
        lineHeight: 1.55,
        color: "#7b8794",
    },

    loadingCard: {
        maxWidth: "500px",
        margin: "100px auto",
        textAlign: "center",
        background: "#ffffff",
        borderRadius: "20px",
        padding: "40px",
        boxShadow: "0 12px 30px rgba(44, 62, 80, 0.08)",
    },

    loadingSpinner: {
        fontSize: "32px",
        color: "#5669f6",
    },

    loadingTitle: {
        margin: "15px 0 0",
        fontSize: "20px",
    },

    loadingText: {
        color: "#7b8794",
        fontSize: "14px",
    },

    errorCard: {
        maxWidth: "560px",
        margin: "100px auto",
        textAlign: "center",
        background: "#ffffff",
        borderRadius: "20px",
        padding: "40px",
        boxShadow: "0 12px 30px rgba(44, 62, 80, 0.08)",
    },

    errorIcon: {
        width: "42px",
        height: "42px",
        borderRadius: "50%",
        margin: "0 auto",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#fde2e2",
        color: "#a33a3a",
        fontWeight: 800,
    },

    errorTitle: {
        margin: "14px 0 0",
        fontSize: "20px",
    },

    errorText: {
        color: "#7b8794",
        fontSize: "14px",
        lineHeight: 1.5,
    },

    errorHint: {
        color: "#9aa4ae",
        fontSize: "13px",
        marginTop: "18px",
    },
};

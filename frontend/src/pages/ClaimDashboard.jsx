import { useEffect, useState } from "react";
import {
    ArrowRight,
    Camera,
    CheckCircle,
    FileText,
    Package,
    SpinnerGap,
    WarningCircle,
} from "@phosphor-icons/react";

import { getClaim } from "../services/api";


function ClaimDashboard({
    claimId,
    onSubmitClaim,
    submitting = false,
}) {
    const [claim, setClaim] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");


    useEffect(() => {
        async function loadClaim() {
            try {
                setLoading(true);
                setError("");

                const data = await getClaim(claimId);

                setClaim(data);

            } catch (error) {
                console.error(error);
                setError(
                    error?.message ||
                    "Unable to load claim."
                );
            } finally {
                setLoading(false);
            }
        }

        loadClaim();

    }, [claimId]);


    if (loading) {
        return (
            <div className="standalone-claim-dashboard" style={styles.page}>
                <div style={styles.stateCard}>
                    <div style={styles.loader}>
                        <SpinnerGap aria-label="Loading" />
                    </div>

                    <h2 style={styles.stateTitle}>
                        Loading claim...
                    </h2>

                    <p style={styles.stateText}>
                        Preparing your evidence workspace.
                    </p>
                </div>
            </div>
        );
    }


    if (error) {
        return (
            <div className="standalone-claim-dashboard" style={styles.page}>
                <div style={styles.stateCard}>
                    <div style={styles.errorIcon}>
                        !
                    </div>

                    <h2 style={styles.stateTitle}>
                        Unable to load claim
                    </h2>

                    <p style={styles.stateText}>
                        {error}
                    </p>
                </div>
            </div>
        );
    }


    if (!claim) {
        return (
            <div className="standalone-claim-dashboard" style={styles.page}>
                <div style={styles.stateCard}>
                    <h2 style={styles.stateTitle}>
                        Claim not found
                    </h2>

                    <p style={styles.stateText}>
                        No claim information was returned.
                    </p>
                </div>
            </div>
        );
    }


    const evidence = Array.isArray(claim.evidence)
        ? claim.evidence
        : [];


    const invoice = evidence.find(
        item => item.type === "invoice"
    );


    const product = evidence.find(
        item => item.type === "product"
    );


    const damage = evidence.find(
        item => item.type === "damage"
    );


    const canSubmitClaim = evidence.length > 0;


    return (
        <div className="standalone-claim-dashboard" style={styles.page}>
            <div style={styles.container}>

                {/* =========================================
                    HEADER
                ========================================= */}

                <section className="standalone-claim-header" style={styles.header}>
                    <div>
                        <div style={styles.eyebrow}>
                            Claim overview
                        </div>

                        <h1 style={styles.title}>
                            {claim.claim_number}
                        </h1>

                        <p style={styles.subtitle}>
                            Review your submitted evidence
                            before starting TrustLens verification.
                        </p>
                    </div>

                    <StatusPill
                        label={claim.status || "PENDING"}
                        type="pending"
                    />
                </section>


                {/* =========================================
                    CLAIM SUMMARY
                ========================================= */}

                <section className="standalone-claim-summary" style={styles.summaryGrid}>

                    <SummaryCard
                        label="Claim ID"
                        value={`#${claim.id}`}
                    />

                    <SummaryCard
                        label="Evidence"
                        value={`${evidence.length} / 3`}
                    />

                    <SummaryCard
                        label="Verification"
                        value="Ready"
                    />

                </section>


                {/* =========================================
                    EVIDENCE SECTION
                ========================================= */}

                <section style={styles.sectionHeader}>
                    <div>
                        <div style={styles.eyebrow}>
                            Evidence inventory
                        </div>

                        <h2 style={styles.sectionTitle}>
                            Submitted evidence
                        </h2>

                        <p style={styles.sectionDescription}>
                            TrustLens uses multiple evidence
                            sources to build a more reliable
                            verification assessment.
                        </p>
                    </div>

                    <div style={styles.evidenceCounter}>
                        {evidence.length} of 3 uploaded
                    </div>
                </section>


                <div className="standalone-evidence-grid" style={styles.evidenceGrid}>

                    <EvidenceCard
                        title="Invoice"
                        icon={<FileText aria-hidden="true" />}
                        description="Proof of purchase and financial information."
                        evidence={invoice}
                    />


                    <EvidenceCard
                        title="Product"
                        icon={<Package aria-hidden="true" />}
                        description="Visual reference for the claimed product."
                        evidence={product}
                    />


                    <EvidenceCard
                        title="Damage"
                        icon={<Camera aria-hidden="true" />}
                        description="Visual evidence of the reported damage."
                        evidence={damage}
                    />

                </div>


                {/* =========================================
                    VERIFICATION PREVIEW
                ========================================= */}

                <section className="standalone-pipeline-card" style={styles.pipelineCard}>

                    <div style={styles.pipelineIcon}>
                        <CheckCircle aria-hidden="true" />
                    </div>


                    <div style={styles.pipelineContent}>

                        <div style={styles.eyebrow}>
                            Next step
                        </div>

                        <h2 style={styles.pipelineTitle}>
                            Submit for administrator verification
                        </h2>

                        <p style={styles.pipelineDescription}>
                            Once submitted, the evidence is locked and an
                            administrator can run TrustLens analysis before
                            recording the final claim decision.
                        </p>


                        <div style={styles.pipelineStages}>

                            <PipelineStage
                                label="Image Quality"
                            />

                            <PipelineStage
                                label="Forensics"
                            />

                            <PipelineStage
                                label="AI Detection"
                            />

                            <PipelineStage
                                label="OCR"
                            />

                            <PipelineStage
                                label="Cross-Evidence"
                            />

                            <PipelineStage
                                label="Trust Assessment"
                            />

                        </div>

                    </div>


                    <button
                        style={{
                            ...styles.primaryButton,
                            ...(canSubmitClaim
                                ? {}
                                : styles.disabledButton),
                        }}
                        onClick={
                            canSubmitClaim
                                ? onSubmitClaim
                                : undefined
                        }
                        disabled={!canSubmitClaim || submitting}
                    >
                        {canSubmitClaim
                            ? <><span>{submitting ? "Submitting claim..." : "Submit claim"}</span><ArrowRight aria-hidden="true" /></>
                            : "Upload evidence first"}
                    </button>

                </section>


                {/* =========================================
                    INFORMATION NOTE
                ========================================= */}

                <section style={styles.infoCard}>

                    <div style={styles.infoIcon}>
                        i
                    </div>

                    <div>
                        <div style={styles.infoTitle}>
                            Evidence-aware verification
                        </div>

                        <div style={styles.infoText}>
                            TrustLens does not rely on a single
                            signal. Multiple evidence-level
                            analyses are combined before a
                            baseline assessment is produced.
                        </div>
                    </div>

                </section>

            </div>
        </div>
    );
}


// ========================================
// STATUS PILL
// ========================================

function StatusPill({
    label,
    type = "neutral"
}) {
    return (
        <span
            style={{
                ...styles.statusPill,

                ...(type === "pending"
                    ? styles.statusPending
                    : type === "success"
                        ? styles.statusSuccess
                        : styles.statusNeutral),
            }}
        >
            {label}
        </span>
    );
}


// ========================================
// SUMMARY CARD
// ========================================

function SummaryCard({
    label,
    value
}) {
    return (
        <div style={styles.summaryCard}>

            <div style={styles.summaryLabel}>
                {label}
            </div>

            <div style={styles.summaryValue}>
                {value}
            </div>

        </div>
    );
}


// ========================================
// EVIDENCE CARD
// ========================================

function EvidenceCard({
    title,
    icon,
    description,
    evidence
}) {
    return (
        <div style={styles.evidenceCard}>

            <div style={styles.evidenceTop}>

                <div style={styles.evidenceIcon}>
                    {icon}
                </div>

                <StatusPill
                    label={
                        evidence
                            ? "UPLOADED"
                            : "MISSING"
                    }
                    type={
                        evidence
                            ? "success"
                            : "neutral"
                    }
                />

            </div>


            <h3 style={styles.evidenceTitle}>
                {title}
            </h3>


            <p style={styles.evidenceDescription}>
                {description}
            </p>


            {evidence ? (
                <div style={styles.fileBox}>

                    <div style={styles.fileIcon}>
                        <CheckCircle aria-hidden="true" />
                    </div>

                    <div style={styles.fileContent}>

                        <div style={styles.fileName}>
                            {evidence.original_filename}
                        </div>

                        <div style={styles.fileStatus}>
                            Evidence registered
                        </div>

                    </div>

                </div>
            ) : (
                <div style={styles.missingBox}>

                    <div style={styles.missingIcon}>
                        <WarningCircle aria-hidden="true" />
                    </div>

                    <div>
                        <div style={styles.missingTitle}>
                            Evidence missing
                        </div>

                        <div style={styles.missingText}>
                            Upload this evidence before
                            verification.
                        </div>
                    </div>

                </div>
            )}

        </div>
    );
}


// ========================================
// PIPELINE STAGE
// ========================================

function PipelineStage({
    label
}) {
    return (
        <div style={styles.pipelineStage}>

            <span style={styles.pipelineCheck}>
                <CheckCircle aria-hidden="true" />
            </span>

            <span>
                {label}
            </span>

        </div>
    );
}


// ========================================
// STYLES
// ========================================

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
        fontWeight: 800,
        letterSpacing: "0.16em",
        color: "#8793a1",
        textTransform: "uppercase",
    },


    title: {
        margin: "8px 0 0",
        fontSize: "34px",
        lineHeight: 1.12,
        fontWeight: 800,
        letterSpacing: "-0.03em",
    },


    subtitle: {
        margin: "10px 0 0",
        maxWidth: "650px",
        fontSize: "14px",
        lineHeight: 1.55,
        color: "#71808e",
    },


    statusPill: {
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "7px 12px",
        borderRadius: "999px",
        fontSize: "12px",
        fontWeight: 800,
        letterSpacing: "0.03em",
        whiteSpace: "nowrap",
    },


    statusPending: {
        background: "#fff0cf",
        color: "#93641c",
    },


    statusSuccess: {
        background: "#dcf5e7",
        color: "#28764c",
    },


    statusNeutral: {
        background: "#e9eef3",
        color: "#687786",
    },


    summaryGrid: {
        display: "grid",
        gridTemplateColumns:
            "repeat(3, minmax(0, 1fr))",
        gap: "16px",
        marginBottom: "42px",
    },


    summaryCard: {
        background: "#ffffff",
        border: "1px solid #e3e9ee",
        borderRadius: "18px",
        padding: "21px 22px",
        boxShadow:
            "0 10px 25px rgba(44, 62, 80, 0.06)",
    },


    summaryLabel: {
        fontSize: "12px",
        letterSpacing: "0.14em",
        fontWeight: 800,
        color: "#8b97a4",
    },


    summaryValue: {
        marginTop: "8px",
        fontSize: "25px",
        fontWeight: 800,
        letterSpacing: "-0.02em",
    },


    sectionHeader: {
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        gap: "20px",
        marginBottom: "18px",
    },


    sectionTitle: {
        margin: "6px 0 0",
        fontSize: "23px",
        fontWeight: 800,
        letterSpacing: "-0.02em",
    },


    sectionDescription: {
        margin: "7px 0 0",
        maxWidth: "700px",
        fontSize: "13px",
        lineHeight: 1.5,
        color: "#788694",
    },


    evidenceCounter: {
        padding: "8px 12px",
        borderRadius: "999px",
        background: "#ffffff",
        border: "1px solid #e1e7ed",
        color: "#73808e",
        fontSize: "12px",
        fontWeight: 750,
        whiteSpace: "nowrap",
    },


    evidenceGrid: {
        display: "grid",
        gridTemplateColumns:
            "repeat(3, minmax(0, 1fr))",
        gap: "18px",
        marginBottom: "42px",
    },


    evidenceCard: {
        background: "#ffffff",
        border: "1px solid #e2e8ee",
        borderRadius: "19px",
        padding: "20px",
        boxShadow:
            "0 10px 26px rgba(44, 62, 80, 0.06)",
    },


    evidenceTop: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "12px",
    },


    evidenceIcon: {
        width: "46px",
        height: "46px",
        borderRadius: "14px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f2f5f8",
        fontSize: "21px",
    },


    evidenceTitle: {
        margin: "17px 0 0",
        fontSize: "18px",
        fontWeight: 800,
    },


    evidenceDescription: {
        margin: "6px 0 0",
        minHeight: "40px",
        fontSize: "14px",
        lineHeight: 1.5,
        color: "#7b8895",
    },


    fileBox: {
        display: "flex",
        alignItems: "center",
        gap: "10px",
        marginTop: "18px",
        padding: "11px",
        borderRadius: "12px",
        background: "#f6faf8",
        border: "1px solid #e2f0e8",
    },


    fileIcon: {
        width: "27px",
        height: "27px",
        flexShrink: 0,
        borderRadius: "50%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#dcf5e7",
        color: "#28764c",
        fontSize: "13px",
        fontWeight: 800,
    },


    fileContent: {
        minWidth: 0,
    },


    fileName: {
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
        fontSize: "13px",
        fontWeight: 700,
        color: "#44515e",
    },


    fileStatus: {
        marginTop: "2px",
        fontSize: "12px",
        color: "#6f8d7b",
    },


    missingBox: {
        display: "flex",
        alignItems: "center",
        gap: "10px",
        marginTop: "18px",
        padding: "11px",
        borderRadius: "12px",
        background: "#fafbfc",
        border: "1px solid #e9edf1",
    },


    missingIcon: {
        width: "27px",
        height: "27px",
        flexShrink: 0,
        borderRadius: "50%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#edf1f4",
        color: "#687786",
        fontSize: "13px",
        fontWeight: 800,
    },


    missingTitle: {
        fontSize: "13px",
        fontWeight: 750,
    },


    missingText: {
        marginTop: "2px",
        fontSize: "12px",
        color: "#8995a1",
    },


    pipelineCard: {
        display: "flex",
        alignItems: "flex-start",
        gap: "18px",
        padding: "25px",
        background: "#ffffff",
        border: "1px solid #e2e8ee",
        borderRadius: "20px",
        boxShadow:
            "0 12px 30px rgba(44, 62, 80, 0.07)",
        marginBottom: "18px",
    },


    pipelineIcon: {
        width: "44px",
        height: "44px",
        flexShrink: 0,
        borderRadius: "13px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#eef1ff",
        color: "#5669f6",
        fontWeight: 900,
        fontSize: "18px",
    },


    pipelineContent: {
        flex: 1,
        minWidth: 0,
    },


    pipelineTitle: {
        margin: "6px 0 0",
        fontSize: "20px",
        fontWeight: 800,
        letterSpacing: "-0.02em",
    },


    pipelineDescription: {
        margin: "7px 0 0",
        maxWidth: "700px",
        fontSize: "14px",
        lineHeight: 1.55,
        color: "#778593",
    },


    pipelineStages: {
        display: "flex",
        flexWrap: "wrap",
        gap: "7px",
        marginTop: "16px",
    },


    pipelineStage: {
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "7px 9px",
        borderRadius: "999px",
        background: "#f5f7f9",
        border: "1px solid #e8edf1",
        fontSize: "12px",
        fontWeight: 700,
        color: "#657381",
    },


    pipelineCheck: {
        color: "#4a7b61",
        fontSize: "12px",
    },


    primaryButton: {
        flexShrink: 0,
        alignSelf: "center",
        minHeight: "46px",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "8px",
        border: "1px solid #0b1620",
        borderRadius: "10px",
        padding: "0 18px",
        background: "#0b1620",
        color: "#f5f1e8",
        fontSize: "14px",
        fontWeight: 680,
        cursor: "pointer",
        boxShadow: "0 10px 24px rgba(11, 22, 32, 0.14)",
    },


    disabledButton: {
        background: "#cbd3db",
        boxShadow: "none",
        cursor: "not-allowed",
    },


    infoCard: {
        display: "flex",
        alignItems: "flex-start",
        gap: "12px",
        padding: "17px 19px",
        borderRadius: "16px",
        background: "#f5f7f9",
        border: "1px solid #e5eaf0",
    },


    infoIcon: {
        width: "25px",
        height: "25px",
        flexShrink: 0,
        borderRadius: "50%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#e5eaf0",
        color: "#697887",
        fontSize: "14px",
        fontWeight: 800,
    },


    infoTitle: {
        fontSize: "13px",
        fontWeight: 800,
        color: "#536171",
    },


    infoText: {
        marginTop: "4px",
        fontSize: "13px",
        lineHeight: 1.5,
        color: "#7b8794",
    },


    stateCard: {
        maxWidth: "500px",
        margin: "100px auto",
        padding: "40px",
        textAlign: "center",
        background: "#ffffff",
        border: "1px solid #e3e9ee",
        borderRadius: "20px",
        boxShadow:
            "0 12px 30px rgba(44, 62, 80, 0.08)",
    },


    loader: {
        fontSize: "32px",
        color: "#5669f6",
    },


    errorIcon: {
        width: "42px",
        height: "42px",
        margin: "0 auto",
        borderRadius: "50%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#fde2e2",
        color: "#a33a3a",
        fontWeight: 800,
    },


    stateTitle: {
        margin: "15px 0 0",
        fontSize: "20px",
        fontWeight: 800,
    },


    stateText: {
        margin: "8px 0 0",
        color: "#7b8794",
        fontSize: "14px",
        lineHeight: 1.5,
    },
};


export default ClaimDashboard;

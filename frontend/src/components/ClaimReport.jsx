import { useEffect, useMemo, useState } from "react";
import { Crosshair, Info, Printer } from "@phosphor-icons/react";

import { getClaim, getEvidenceImage } from "../services/api";
import { createClaimDecision } from "../services/adminService";
import { getVerificationRun } from "../services/verificationService";
import BrandMark from "./BrandMark";


const TERMINAL = new Set(["APPROVED", "REJECTED"]);

function label(value) {
    if (!value) return "Not available";
    return String(value).replaceAll("_", " ").toLowerCase()
        .replace(/\b\w/g, (character) => character.toUpperCase());
}

function percent(value) {
    return typeof value === "number" ? `${Math.round(value * 100)}%` : "Not available";
}

function formatDate(value, includeTime = false) {
    if (!value) return "Not provided";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Not provided";
    return date.toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        ...(includeTime ? {hour: "2-digit", minute: "2-digit"} : {}),
    });
}

function formatBytes(value) {
    if (typeof value !== "number") return "Not available";
    if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function narrative(value, fallback) {
    if (typeof value !== "string") return fallback;
    const cleanValue = value.trim();
    if (!cleanValue || cleanValue.startsWith("{") || cleanValue.startsWith("[")) return fallback;
    return cleanValue;
}

function analysisSummary(item) {
    const result = item.result || {};
    if (item.status !== "COMPLETED") return narrative(item.message, label(item.status));
    if (result.prediction && result.excluded_from_trust_score) {
        return `Research only: ${label(result.prediction)} (excluded from Trust Score)`;
    }
    if (result.prediction) {
        return `${label(result.prediction)}${typeof result.confidence === "number" ? `, ${percent(result.confidence)} confidence` : ""}`;
    }
    if (result.quality_status) return label(result.quality_status);
    if (result.extracted_text) return `Text extracted (${result.extracted_text.length} characters)`;
    if (typeof result.sharpness_score === "number") return `Sharpness ${result.sharpness_score}`;
    return narrative(item.message, "Analysis completed");
}

const PATCH_ORDER = [
    "top_left",
    "top_right",
    "center",
    "bottom_left",
    "bottom_right",
];

function signalLevel(value) {
    if (value >= 0.66) return "high";
    if (value >= 0.33) return "moderate";
    return "low";
}

function ForensicRegionExplanation({ analysis }) {
    const result = analysis?.result || {};
    const viewPredictions = Array.isArray(result.view_predictions)
        ? result.view_predictions
        : [];
    const byView = Object.fromEntries(
        viewPredictions.map((item) => [item.view, item])
    );
    const regionalViews = PATCH_ORDER.map((name) => byView[name]).filter(Boolean);

    if (analysis?.status !== "COMPLETED" || regionalViews.length !== 5) {
        return null;
    }

    const explanation = result.regional_explanation || {};
    const highest = regionalViews.reduce((current, item) => (
        item.tampered_probability > current.tampered_probability ? item : current
    ));
    const highestView = explanation.highest_signal_view || highest.view;
    const globalView = byView.global;

    return (
        <section className="forensic-region-explanation" aria-labelledby={`region-title-${analysis.id}`}>
            <div className="forensic-region-heading">
                <Crosshair aria-hidden="true" weight="duotone" />
                <div>
                    <span>Regional forensic explanation</span>
                    <strong id={`region-title-${analysis.id}`}>
                        Highest signal: {label(highestView)}
                    </strong>
                </div>
            </div>

            <div className="forensic-region-map" role="list" aria-label="Tampering signal by image region">
                {regionalViews.map((item) => {
                    const level = signalLevel(item.tampered_probability);
                    return (
                        <div
                            className={`forensic-region-cell region-${item.view} signal-${level}`}
                            key={item.view}
                            role="listitem"
                            aria-label={`${label(item.view)}: ${percent(item.tampered_probability)} tampering signal, ${level}`}
                        >
                            <span>{label(item.view)}</span>
                            <strong>{percent(item.tampered_probability)}</strong>
                            <small>{label(level)}</small>
                        </div>
                    );
                })}
            </div>

            <div className="forensic-region-context">
                <div>
                    <span>Whole image</span>
                    <strong>{percent(globalView?.tampered_probability)}</strong>
                </div>
                <div>
                    <span>Combined result</span>
                    <strong>{percent(result.tampered_probability)}</strong>
                </div>
            </div>

            <p className="forensic-region-note">
                <Info aria-hidden="true" />
                These are raw regional model signals. They identify the most suspicious crop,
                not the exact edited pixels, and must be interpreted with the calibrated Trust Score.
            </p>
        </section>
    );
}

export default function ClaimReport({
    claimId,
    initialClaim = null,
    initialRun = null,
    isAdmin = false,
    showDecisionActions = true,
    onUpdated,
}) {
    const [claim, setClaim] = useState(initialClaim);
    const [run, setRun] = useState(initialRun);
    const [images, setImages] = useState({});
    const [note, setNote] = useState("");
    const [loading, setLoading] = useState(!initialClaim);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");

    useEffect(() => {
        let active = true;
        async function load() {
            setLoading(true);
            setError("");
            try {
                const loadedClaim = initialClaim || await getClaim(claimId);
                if (!active) return;
                setClaim(loadedClaim);
                const runId = initialRun?.id || loadedClaim.verification_runs?.[0]?.id;
                if (initialRun) setRun(initialRun);
                else if (runId) setRun(await getVerificationRun(runId));
                else setRun(null);
            } catch (requestError) {
                if (active) setError(requestError.message);
            } finally {
                if (active) setLoading(false);
            }
        }
        load();
        return () => { active = false; };
    }, [claimId, initialClaim, initialRun]);

    useEffect(() => {
        let active = true;
        const urls = [];
        async function loadImages() {
            const entries = await Promise.all((claim?.evidence || []).map(async (evidence) => {
                try {
                    const blob = await getEvidenceImage(claim.id, evidence.id);
                    const url = URL.createObjectURL(blob);
                    urls.push(url);
                    return [evidence.id, url];
                } catch {
                    return [evidence.id, null];
                }
            }));
            if (active) setImages(Object.fromEntries(entries));
            else urls.forEach((url) => URL.revokeObjectURL(url));
        }
        if (claim?.evidence?.length) loadImages();
        return () => {
            active = false;
            urls.forEach((url) => URL.revokeObjectURL(url));
        };
    }, [claim]);

    const analyses = useMemo(() => run?.analysis_results || [], [run]);
    const trust = analyses.find((item) => item.analysis_type === "TRUST_ASSESSMENT")?.result
        || claim?.verification_runs?.[0]?.trust_assessment || null;
    const score = trust?.trust_score ?? null;
    const fusionSources = Array.isArray(trust?.fusion_sources) ? trust.fusion_sources : [];
    const conditionalBranchStatus = Array.isArray(trust?.conditional_branch_status)
        ? trust.conditional_branch_status
        : [];
    const evidenceAnalyses = useMemo(() => {
        const grouped = {};
        analyses.filter((item) => item.evidence_id).forEach((item) => {
            grouped[item.evidence_id] = [...(grouped[item.evidence_id] || []), item];
        });
        return grouped;
    }, [analyses]);

    async function decide(action) {
        if (!run?.id || note.trim().length < 3) {
            setError("Add a message of at least 3 characters explaining the decision.");
            return;
        }
        setSubmitting(true);
        setError("");
        try {
            const response = await createClaimDecision(claim.id, run.id, action, note.trim());
            const refreshed = await getClaim(claim.id);
            setClaim(refreshed);
            setNote("");
            setMessage(response.message);
            onUpdated?.(refreshed);
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSubmitting(false);
        }
    }

    if (loading) return <div className="claim-report-state">Preparing individual claim report...</div>;
    if (error && !claim) return <div className="admin-inline-error">{error}</div>;
    if (!claim) return null;

    const assessment = trust?.assessment || "NOT_ASSESSED";
    const decision = claim.review_decision;
    const hasFinalDecision = TERMINAL.has(claim.status);
    const canDecide = isAdmin && showDecisionActions && run?.status === "COMPLETED" && !TERMINAL.has(claim.status);
    const resultsRestricted = !isAdmin && Boolean(run?.results_restricted);

    return (
        <section className="claim-report">
            <header className="claim-report-header claim-report-masthead">
                <div className="claim-report-brand-lockup">
                    <BrandMark className="claim-report-brand-mark" />
                    <div>
                        <strong>TrustLens AI</strong>
                        <small>Evidence verification record</small>
                    </div>
                </div>
                <div className="claim-report-header-actions">
                    <button className="claim-report-print" type="button" onClick={() => window.print()}>
                        <Printer aria-hidden="true" />
                        Print or save PDF
                    </button>
                    <span className={`claim-report-verdict ${hasFinalDecision ? claim.status.toLowerCase() : assessment.toLowerCase()}`}>
                        {hasFinalDecision ? label(claim.status) : resultsRestricted ? "Under review" : label(assessment)}
                    </span>
                </div>
            </header>

            <section className="claim-report-title-block">
                <div>
                    <span>Individual claim report</span>
                    <h2>{claim.claim_number}</h2>
                    <p>Evidence authenticity, calibrated trust assessment, and administrative outcome.</p>
                </div>
                <dl className="claim-report-document-meta">
                    <div><dt>Updated</dt><dd>{formatDate(run?.completed_at || claim.created_at, true)}</dd></div>
                    <div><dt>Reference</dt><dd>{run?.id ? `VR-${run.id}` : "Awaiting verification"}</dd></div>
                </dl>
            </section>

            <section className="claim-report-party-grid" aria-label="Claim and claimant identification">
                <div>
                    <span>Claimant</span>
                    <strong>{claim.claimant?.full_name || "Legacy / unassigned"}</strong>
                    <small>{claim.claimant?.email || "No account email"}</small>
                </div>
                <div>
                    <span>Claim status</span>
                    <strong>{label(claim.status)}</strong>
                    <small>Claim record #{claim.id}</small>
                </div>
                <div>
                    <span>Submitted evidence</span>
                    <strong>{claim.evidence?.length || 0} files</strong>
                    <small>Created {formatDate(claim.created_at)}</small>
                </div>
            </section>

            {claim.claim_type && <section className="claim-report-intake" aria-label="Claim context">
                <div><span>Claim context</span><h3>{claim.item_name}</h3><p>{claim.incident_summary}</p></div>
                <dl>
                    <div><dt>Type</dt><dd>{label(claim.claim_type)}</dd></div>
                    <div><dt>Issue date</dt><dd>{formatDate(claim.incident_date)}</dd></div>
                    {claim.reference_number && <div><dt>Reference</dt><dd>{claim.reference_number}</dd></div>}
                </dl>
            </section>}

            {resultsRestricted ? (
                <div className="claim-results-restricted">
                    <span>Administrator review in progress</span>
                    <h3>Your evidence has been verified securely.</h3>
                    <p>
                        The detailed analysis, trust assessment, and reviewer explanation
                        will be shared here after an administrator records the final decision.
                    </p>
                </div>
            ) : <div className="claim-report-scoreboard">
                <div className="trust-score-ring" style={{"--score": score ?? 0}}>
                    <strong>{score ?? "Not available"}</strong><span>/100</span>
                </div>
                <div>
                    <span>Verification summary</span>
                    <h3>{hasFinalDecision ? `Claim ${claim.status.toLowerCase()} by reviewer` : assessment === "LOW_CONCERN" ? "No major concerns flagged" : assessment === "REVIEW_NEEDED" ? "A reviewer should check this claim" : "Verification is pending"}</h3>
                    <p>{hasFinalDecision ? "The score summarizes image checks; the final reviewer decision and explanation appear below." : score === null ? "A trust indicator will appear when verification completes." : "This score helps prioritize review. The administrator makes the final decision after checking the images and context."}</p>
                </div>
                <div className="claim-report-facts">
                    <ReportFact label="Current status" value={label(claim.status)} />
                    <ReportFact label="Image checks" value={label(run?.status || "NOT_STARTED")} />
                    <ReportFact label="Files reviewed" value={`${claim.evidence?.length || 0}`} />
                    <ReportFact label="Next step" value={TERMINAL.has(claim.status) ? "Decision shared" : run?.status === "COMPLETED" ? "Admin decision" : "Verification"} />
                </div>
            </div>}

            {isAdmin && !resultsRestricted && (fusionSources.length > 0 || conditionalBranchStatus.length > 0) && (
                <details className="claim-report-technical">
                <summary>Technical score details <span>For reviewers</span></summary>
                <section className="claim-report-contributors" aria-label="Trust Score contributors">
                    <div className="claim-report-contributors-heading">
                        <span>Score composition</span>
                        <h3>Evidence branches used by the Trust Score</h3>
                        <p>Only applicable branches with validated calibration can change the numerical score.</p>
                    </div>
                    <div className="claim-report-contributor-grid">
                        {fusionSources.map((source) => (
                            <article key={source.source} className="claim-report-contributor included">
                                <span>Included</span>
                                <strong>{label(source.source)}</strong>
                                <small>
                                    Suspicious signal {percent(source.calibrated_suspicious_probability)}
                                    {typeof source.reliability === "number" ? ` · reliability ${percent(source.reliability)}` : ""}
                                </small>
                                {Array.isArray(source.supporting_sources) && (
                                    <p>Built from {source.supporting_sources.map(label).join(" + ")}.</p>
                                )}
                            </article>
                        ))}
                        {conditionalBranchStatus
                            .filter((branch) => !String(branch.status).startsWith("INCLUDED"))
                            .map((branch) => (
                                <article key={branch.branch} className="claim-report-contributor excluded">
                                    <span>{label(branch.status)}</span>
                                    <strong>{label(branch.branch)}</strong>
                                    <small>{label(branch.reason)}</small>
                                </article>
                            ))}
                    </div>
                </section>
                <div className="claim-report-technical-facts">
                    <ReportFact label="Analysis coverage" value={percent(trust?.analysis_completion_ratio)} />
                    <ReportFact label="Fraud evidence" value={scoreOutput(trust?.fraud_evidence)} />
                    <ReportFact label="Uncertainty" value={scoreOutput(trust?.fusion_uncertainty)} />
                    <ReportFact label="Detector conflict" value={scoreOutput(trust?.fusion_conflict)} />
                    <ReportFact label="Score status" value={label(trust?.score_status)} />
                    <ReportFact label="Pipeline" value={run?.pipeline_version || "Not started"} />
                </div>
                </details>
            )}

            {!resultsRestricted && (trust?.reasons?.length > 0 || trust?.risk_signals?.length > 0) && (
                <div className="claim-report-findings">
                    <span>What the image checks found</span>
                    <p>{narrative(trust?.reasons?.[0], "Some evidence signals need reviewer attention.")}</p>
                    {isAdmin && ((trust?.reasons?.length || 0) > 1 || (trust?.risk_signals?.length || 0) > 0) && (
                        <details className="claim-report-reasons-detail">
                            <summary>See all review signals</summary>
                            {(trust.reasons || []).slice(1).map((reason, index) => <p key={index}>{reason}</p>)}
                            {(trust.risk_signals || []).map((signal, index) => (
                                <div className="claim-report-risk" key={`${signal.type}-${index}`}>
                                    <strong>{label(signal.type)}</strong><span>{narrative(signal.message, "A review signal was recorded.")}</span>
                                </div>
                            ))}
                        </details>
                    )}
                </div>
            )}

            <div className="claim-report-section-heading">
                <div><span>Evidence</span><h3>Images and per-file analysis</h3></div>
                <small>{claim.evidence?.length || 0} files</small>
            </div>
            <div className="claim-report-evidence-grid">
                {(claim.evidence || []).map((evidence) => {
                    const itemAnalyses = evidenceAnalyses[evidence.id] || [];
                    const forensicAnalysis = itemAnalyses.find(
                        (item) => item.analysis_type === "TAMPERING_DETECTION"
                    );
                    return (
                    <article className="claim-report-evidence" key={evidence.id}>
                        <div className="claim-report-image">
                            {images[evidence.id] ? <img src={images[evidence.id]} alt={`${evidence.type} evidence`} /> : <span>Image unavailable</span>}
                        </div>
                        <div className="claim-report-evidence-body">
                            <div className="claim-report-evidence-title">
                                <span>{label(evidence.type)}</span>
                                <h4>{evidence.original_filename}</h4>
                            </div>
                            <div className="claim-report-evidence-context">
                                <div className="evidence-context-narrative">
                                    <span>Claimant context</span>
                                    <p>{evidence.description || "No claimant description was provided for this evidence."}</p>
                                </div>
                                <dl>
                                    <div><dt>Origin</dt><dd>{label(evidence.source_type)}</dd></div>
                                    <div><dt>Captured or issued</dt><dd>{formatDate(evidence.captured_at, true)}</dd></div>
                                    <div><dt>Location</dt><dd>{evidence.location_label || "Not provided"}</dd></div>
                                    <div>
                                        <dt>File details</dt>
                                        <dd>
                                            {evidence.image_width && evidence.image_height
                                                ? `${evidence.image_width} × ${evidence.image_height} · ${formatBytes(evidence.file_size_bytes)}`
                                                : formatBytes(evidence.file_size_bytes)}
                                        </dd>
                                    </div>
                                </dl>
                            </div>
                            {itemAnalyses.length === 0 ? (
                                <p>
                                    {resultsRestricted
                                        ? "Analysis will be released after administrator review."
                                        : "No analysis result for this file yet."}
                                </p>
                            ) : <div className="claim-report-file-summary">{itemAnalyses.filter((item) => item.status === "COMPLETED").length} checks completed{itemAnalyses.some((item) => ["ERROR", "MODEL_UNAVAILABLE"].includes(item.status)) ? "; some checks need attention" : ""}.</div>}
                            {isAdmin && itemAnalyses.length > 0 && <details className="claim-report-file-details"><summary>View individual checks</summary>{itemAnalyses.map((item) => (
                                <div className="claim-report-analysis-row" key={item.id}>
                                    <span>{label(item.analysis_type)}</span>
                                    <strong>{analysisSummary(item)}</strong>
                                </div>
                            ))}
                            {!resultsRestricted && (
                                <ForensicRegionExplanation analysis={forensicAnalysis} />
                            )}
                            </details>}
                        </div>
                    </article>
                    );
                })}
            </div>

            {decision && (
                <div className={`claim-report-decision ${decision.resulting_status.toLowerCase()}`}>
                    <div><span>Administrative outcome</span><strong>{label(decision.resulting_status)}</strong></div>
                    <p>{narrative(decision.message, "The administrative review is complete.")}</p>
                </div>
            )}

            {canDecide && (
                <div className="claim-report-admin-actions">
                    <div><span>Admin decision</span><h3>Share an outcome with this claimant</h3><p>The message below appears in the claimant's individual report.</p></div>
                    <textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength="2000" placeholder="Explain why this claim is approved, rejected, or needs specialist review..." />
                    <div>
                        <button className="review-action approve" disabled={submitting} onClick={() => decide("APPROVE")}>Approve & share</button>
                        <button className="review-action reject" disabled={submitting} onClick={() => decide("REJECT")}>Reject & share</button>
                        {claim.status !== "ESCALATED" && <button className="review-action escalate" disabled={submitting} onClick={() => decide("ESCALATE")}>Send to review</button>}
                    </div>
                </div>
            )}
            {error && <div className="admin-inline-error">{error}</div>}
            {message && <div className="review-success-message">{message} The claimant can now see the result.</div>}
        </section>
    );
}

function ReportFact({label: factLabel, value}) {
    return <div><span>{factLabel}</span><strong>{value}</strong></div>;
}

function scoreOutput(value) {
    return typeof value === "number" ? `${value.toFixed(1)}/100` : "Not available";
}

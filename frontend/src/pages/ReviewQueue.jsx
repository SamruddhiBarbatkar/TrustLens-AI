import { useEffect, useState } from "react";
import {
    ArrowUpRight,
    CheckCircle,
    WarningCircle,
} from "@phosphor-icons/react";

import {
    createClaimDecision,
    getClaimDecisions,
    getReviewQueue,
} from "../services/adminService";
import ClaimReport from "../components/ClaimReport";


function ReviewQueue() {
    const [reviewClaims, setReviewClaims] = useState([]);
    const [selected, setSelected] = useState(null);
    const [history, setHistory] = useState([]);
    const [note, setNote] = useState("");
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");

    async function loadReviewQueue() {
        setLoading(true);
        setError("");
        try {
            const response = await getReviewQueue();
            setReviewClaims(response.claims || []);
        } catch (requestError) {
            setError(requestError.message || "Failed to load the review queue.");
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        let active = true;
        getReviewQueue()
            .then((response) => {
                if (active) {
                    setReviewClaims(response.claims || []);
                }
            })
            .catch((requestError) => {
                if (active) {
                    setError(requestError.message);
                }
            })
            .finally(() => {
                if (active) {
                    setLoading(false);
                }
            });

        return () => {
            active = false;
        };
    }, []);

    async function openReview(item) {
        setSelected(item);
        setNote("");
        setMessage("");
        setError("");
        try {
            const response = await getClaimDecisions(item.claim.id);
            setHistory(response.decisions || []);
        } catch (requestError) {
            setError(requestError.message);
        }
    }

    async function submitDecision(action) {
        if (!selected || note.trim().length < 3) {
            setError("Add a review note of at least 3 characters before deciding.");
            return;
        }

        setSubmitting(true);
        setError("");
        setMessage("");
        try {
            const result = await createClaimDecision(
                selected.claim.id,
                selected.run.id,
                action,
                note.trim()
            );
            setMessage(result.message);
            setNote("");

            const queueResponse = await getReviewQueue();
            const nextQueue = queueResponse.claims || [];
            setReviewClaims(nextQueue);

            const updatedSelection = nextQueue.find(
                (item) => item.claim.id === selected.claim.id
            );

            if (updatedSelection) {
                setSelected(updatedSelection);
                const auditResponse = await getClaimDecisions(selected.claim.id);
                setHistory(auditResponse.decisions || []);
            } else {
                setSelected(null);
                setHistory([]);
            }
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSubmitting(false);
        }
    }

    function formatDate(value) {
        if (!value) {
            return "Not available";
        }
        return new Date(value).toLocaleString("en-IN", {
            day: "2-digit",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    function getPriority(item) {
        return item.trust_assessment?.risk_signals?.length > 0
            ? "HIGH"
            : "MEDIUM";
    }

    function getReason(item) {
        const result = item.trust_assessment || {};
        return (
            result.reasons?.join(" ") ||
            result.assessment_basis ||
            "Trust assessment requires manual review."
        );
    }

    if (loading) {
        return <div className="loading-card">Loading review workspace...</div>;
    }

    return (
        <div className="review-queue-page">
            <section className="review-desk-header">
                <div className="review-desk-copy">
                    <div className="admin-section-label">Human decision desk</div>
                    <h2>Resolve the uncertain cases</h2>
                    <p>
                        Work through flagged and escalated claims, document your evidence,
                        and create an accountable decision trail.
                    </p>
                    <button className="secondary-button" onClick={loadReviewQueue}>
                        Refresh queue
                    </button>
                </div>
                <div className="review-desk-count" aria-label={`${reviewClaims.length} cases open`}>
                    <span>Cases open</span>
                    <strong>{reviewClaims.length}</strong>
                    <small>{reviewClaims.length === 1 ? "One decision waiting" : "Decisions waiting"}</small>
                </div>
            </section>

            {error && <div className="admin-inline-error">{error}</div>}
            {message && <div className="review-success-message">{message}</div>}

            <section className="review-triage-strip" aria-label="Review queue priority summary">
                <div className="review-triage-item">
                    <div className="review-summary-icon"><WarningCircle weight="duotone" /></div>
                    <div>
                        <span>Open cases</span>
                        <strong>{reviewClaims.length}</strong>
                    </div>
                </div>
                <div className="review-triage-item">
                    <div className="review-summary-icon high"><ArrowUpRight weight="bold" /></div>
                    <div>
                        <span>High priority</span>
                        <strong>
                            {reviewClaims.filter((item) => getPriority(item) === "HIGH").length}
                        </strong>
                    </div>
                </div>
                <div className="review-triage-item">
                    <div className="review-summary-icon escalated"><ArrowUpRight weight="duotone" /></div>
                    <div>
                        <span>Escalated</span>
                        <strong>
                            {reviewClaims.filter((item) => item.claim.status === "ESCALATED").length}
                        </strong>
                    </div>
                </div>
            </section>

            {selected && (
                <>
                <ClaimReport
                    key={`${selected.claim.id}-${selected.latest_decision?.id || 0}`}
                    claimId={selected.claim.id}
                    isAdmin
                    showDecisionActions={false}
                />
                <section className="review-workspace">
                    <div className="review-case-context">
                        <div className="review-workspace-heading">
                            <div>
                                <span>Active review</span>
                                <h3>{selected.claim.claim_number}</h3>
                            </div>
                            <button className="review-close" onClick={() => setSelected(null)}>
                                Close
                            </button>
                        </div>

                        <div className="review-context-grid">
                            <ContextValue label="Claimant" value={selected.claim.claimant} />
                            <ContextValue label="Email" value={selected.claim.claimant_email || "Not available"} />
                            <ContextValue label="Current status" value={selected.claim.status} />
                            <ContextValue label="Verification run" value={`#${selected.run.id}`} />
                            <ContextValue label="Evidence files" value={selected.claim.evidence_count} />
                        </div>

                        <div className="review-basis">
                            <span>Assessment basis</span>
                            <p>{getReason(selected)}</p>
                            {(selected.trust_assessment.risk_signals || []).map((signal, index) => (
                                <div className="review-risk-signal" key={`${signal.type}-${index}`}>
                                    <strong>{signal.type.replaceAll("_", " ")}</strong>
                                    <span>{signal.message}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="review-decision-panel">
                        <div className="review-workspace-heading">
                            <div>
                                <span>Decision</span>
                                <h3>Record reviewer outcome</h3>
                            </div>
                        </div>

                        <label className="review-note-field">
                            <span>Reviewer note</span>
                            <textarea
                                value={note}
                                onChange={(event) => setNote(event.target.value)}
                                maxLength="2000"
                                placeholder="Document the evidence and reasoning behind this decision..."
                            />
                            <small>{note.length}/2000 characters</small>
                        </label>

                        <div className="review-actions">
                            <button
                                className="review-action approve"
                                onClick={() => submitDecision("APPROVE")}
                                disabled={submitting}
                            >
                                Approve claim
                            </button>
                            <button
                                className="review-action reject"
                                onClick={() => submitDecision("REJECT")}
                                disabled={submitting}
                            >
                                Reject claim
                            </button>
                            {selected.claim.status !== "ESCALATED" && (
                                <button
                                    className="review-action escalate"
                                    onClick={() => submitDecision("ESCALATE")}
                                    disabled={submitting}
                                >
                                    Escalate
                                </button>
                            )}
                        </div>

                        <div className="review-history">
                            <div className="review-history-heading">
                                <span>Audit history</span>
                                <strong>{history.length}</strong>
                            </div>
                            {history.length === 0 ? (
                                <p>No prior reviewer decisions.</p>
                            ) : (
                                history.map((decision) => (
                                    <div className="review-history-item" key={decision.id}>
                                        <div>
                                            <strong>{decision.action}</strong>
                                            <span>{formatDate(decision.created_at)}</span>
                                        </div>
                                        <p>{decision.note}</p>
                                        <small>
                                            {decision.reviewer.full_name} · {decision.previous_status} → {decision.resulting_status}
                                        </small>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </section>
                </>
            )}

            {reviewClaims.length === 0 ? (
                <div className="review-empty-card">
                    <div className="review-empty-icon"><CheckCircle weight="duotone" /></div>
                    <h3>Review queue is clear</h3>
                    <p>No completed verification runs or escalated claims currently require manual review.</p>
                </div>
            ) : (
                <section className="review-list-card">
                    <div className="review-list-header">
                        <div>
                            <div className="admin-section-label">Open cases</div>
                            <h3>Claims requiring attention</h3>
                        </div>
                        <span className="overview-count warning-count">{reviewClaims.length}</span>
                    </div>

                    <div className="review-table-wrapper">
                        <table className="review-table">
                            <thead>
                                <tr>
                                    <th>Claim</th>
                                    <th>Run</th>
                                    <th>Status</th>
                                    <th>Priority</th>
                                    <th>Reason</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {reviewClaims.map((item) => {
                                    const priority = getPriority(item);
                                    return (
                                        <tr key={item.claim.id}>
                                            <td>
                                                <strong>{item.claim.claim_number}</strong>
                                                <span>{item.claim.claimant}</span>
                                                <small>{item.claim.claimant_email || "No account email"}</small>
                                            </td>
                                            <td>
                                                <strong>#{item.run.id}</strong>
                                                <span>{formatDate(item.run.started_at)}</span>
                                            </td>
                                            <td>
                                                <span className="review-evidence-count">
                                                    {item.claim.status.replaceAll("_", " ")}
                                                </span>
                                            </td>
                                            <td>
                                                <span className={priority === "HIGH" ? "priority-pill priority-high" : "priority-pill priority-medium"}>
                                                    {priority}
                                                </span>
                                            </td>
                                            <td><span className="review-reason">{getReason(item)}</span></td>
                                            <td>
                                                <button className="review-open-button" onClick={() => openReview(item)}>
                                                    Review case
                                                </button>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}
        </div>
    );
}


function ContextValue({label, value}) {
    return (
        <div className="review-context-value">
            <span>{label}</span>
            <strong>{value}</strong>
        </div>
    );
}


export default ReviewQueue;

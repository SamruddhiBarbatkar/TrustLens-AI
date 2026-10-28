import { useEffect, useMemo, useState } from "react";
import {
    CheckCircle,
    Clock,
    Files,
    GitBranch,
    Pulse,
} from "@phosphor-icons/react";

import { getAllClaims } from "../services/api";
import { getSystemSettings } from "../services/adminService";

function AdminOverview({onNavigate, onOpenClaim}) {
    const [claims, setClaims] = useState([]);
    const [system, setSystem] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        loadDashboard();
    }, []);

    async function loadDashboard() {
        try {
            setLoading(true);
            setError("");

            const [data, systemData] = await Promise.all([
                getAllClaims(),
                getSystemSettings(),
            ]);
            setClaims(data.claims || []);
            setSystem(systemData);
        } catch (err) {
            setError(
                err.message || "Failed to load admin dashboard."
            );
        } finally {
            setLoading(false);
        }
    }

    const metrics = useMemo(() => {
        const total = claims.length;

        const pending = claims.filter(
            (claim) => claim.status === "PENDING"
        ).length;

        const verificationStarted = claims.filter(
            (claim) => claim.status === "VERIFICATION_STARTED"
        ).length;

        const completed = claims.filter(
            (claim) =>
                claim.status === "COMPLETED" ||
                claim.verification_runs?.some(
                    (run) => run.status === "COMPLETED"
                )
        ).length;

        const reviewNeeded = claims.filter((claim) => {
            const latestRun = claim.verification_runs?.[0];

            return (
                claim.status !== "APPROVED" &&
                claim.status !== "REJECTED" &&
                latestRun?.trust_assessment?.assessment ===
                "REVIEW_NEEDED"
            );
        }).length;

        const totalRuns = claims.reduce(
            (total, claim) =>
                total + (claim.verification_runs?.length || 0),
            0
        );

        return {
            total,
            pending,
            verificationStarted,
            completed,
            reviewNeeded,
            totalRuns,
        };
    }, [claims]);

    const readyClaims = claims.filter((claim) =>
        ["SUBMITTED", "VERIFICATION_FAILED"].includes(claim.status)
    ).slice(0, 5);

    const reviewClaims = claims.filter((claim) => {
        const latestRun = claim.verification_runs?.[0];

        return (
            claim.status !== "APPROVED" &&
            claim.status !== "REJECTED" &&
            latestRun?.trust_assessment?.assessment ===
            "REVIEW_NEEDED"
        );
    }).slice(0, 5);

    function getStatusClass(status) {
        switch (status) {
            case "COMPLETED":
                return "status-success";

            case "VERIFICATION_STARTED":
            case "SUBMITTED":
            case "AWAITING_DECISION":
                return "status-warning";

            case "PENDING":
                return "status-neutral";

            default:
                return "status-neutral";
        }
    }

    function formatStatus(status) {
        if (!status) {
            return "Unknown";
        }

        return status
            .replaceAll("_", " ")
            .toLowerCase()
            .replace(/\b\w/g, (letter) =>
                letter.toUpperCase()
            );
    }

    function formatDate(value) {
        if (!value) {
            return "—";
        }

        return new Date(value).toLocaleDateString(
            "en-IN",
            {
                day: "2-digit",
                month: "short",
                year: "numeric",
            }
        );
    }

    if (loading) {
        return (
            <div className="admin-overview">
                <div className="loading-card">
                    Loading admin dashboard...
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="admin-overview">
                <div className="admin-error">
                    <strong>Unable to load dashboard</strong>
                    <span>{error}</span>

                    <button
                        className="primary-button"
                        onClick={loadDashboard}
                    >
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="admin-overview">
            <section className="overview-command">
                <div className="overview-command-copy">
                    <div className="admin-section-label">
                        Today in operations
                    </div>

                    <h2>Verification command centre</h2>

                    <p>
                        Start checks for submitted claims, then decide the cases that need a human review.
                    </p>

                    <div className="overview-header-actions">
                        <button className="secondary-button" onClick={loadDashboard}>
                            Refresh data
                        </button>
                        <button className="primary-button" onClick={() => onNavigate("runs")}>
                            Run verification
                        </button>
                        <button className="secondary-button" onClick={() => onNavigate("review")}>
                            Open review queue
                        </button>
                    </div>
                </div>

                <aside className={`overview-attention ${metrics.reviewNeeded === 0 ? "is-clear" : ""}`}>
                    <span>Decision pressure</span>
                    <strong>{metrics.reviewNeeded}</strong>
                    <p>
                        {metrics.reviewNeeded === 0
                            ? "No claim is waiting for manual review."
                            : `${metrics.reviewNeeded} ${metrics.reviewNeeded === 1 ? "claim requires" : "claims require"} reviewer attention.`}
                    </p>
                    <button onClick={() => onNavigate("review")}>
                        {metrics.reviewNeeded === 0 ? "Inspect review desk" : "Start reviewing"}
                    </button>
                </aside>
            </section>

            <section className="overview-pulse" aria-label="Current operational totals">
                <div className="overview-pulse-primary">
                    <div className="metric-icon"><Files weight="duotone" /></div>
                    <span>Claim portfolio</span>
                    <strong>{metrics.total}</strong>
                    <small>Total registered claims</small>
                </div>

                <div className="overview-pulse-stats">
                    <div>
                        <Clock weight="duotone" />
                        <span>Pending</span>
                        <strong>{metrics.pending}</strong>
                    </div>

                    <div>
                        <Pulse weight="duotone" />
                        <span>Verification active</span>
                        <strong>{metrics.verificationStarted}</strong>
                    </div>

                    <div>
                        <CheckCircle weight="duotone" />
                        <span>Completed</span>
                        <strong>{metrics.completed}</strong>
                    </div>

                    <div>
                        <GitBranch weight="duotone" />
                        <span>Verification runs</span>
                        <strong>{metrics.totalRuns}</strong>
                    </div>
                </div>
            </section>

            <section className="overview-grid">
                <div className="overview-panel">
                    <div className="overview-panel-header">
                        <div>
                            <div className="admin-section-label">
                                Ready to verify
                            </div>

                            <h3>Submitted evidence</h3>
                        </div>

                        <span className="overview-count">
                            {readyClaims.length}
                        </span>
                    </div>

                    {readyClaims.length === 0 ? (
                        <div className="overview-empty">
                            No submitted claims are waiting for verification.
                        </div>
                    ) : (
                        <div className="overview-claim-list">
                            {readyClaims.map((claim) => (
                                <button
                                    className="overview-claim-row"
                                    key={claim.id}
                                    onClick={() => onOpenClaim(claim.id)}
                                >
                                    <div>
                                        <strong>
                                            {claim.claim_number}
                                        </strong>

                                        <span>
                                            Claim #{claim.id} •{" "}
                                            {formatDate(
                                                claim.created_at
                                            )}
                                        </span>
                                    </div>

                                    <div className="overview-claim-meta">
                                        <span>
                                            {claim.evidence_count || 0}{" "}
                                            evidence
                                        </span>

                                        <span
                                            className={`status-pill ${getStatusClass(
                                                claim.status
                                            )}`}
                                        >
                                            {formatStatus(
                                                claim.status
                                            )}
                                        </span>
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                <div className="overview-panel">
                    <div className="overview-panel-header">
                        <div>
                            <div className="admin-section-label">
                                Needs attention
                            </div>

                            <h3>Review queue</h3>
                        </div>

                        <span className="overview-count warning-count">
                            {metrics.reviewNeeded}
                        </span>
                    </div>

                    {reviewClaims.length === 0 ? (
                        <div className="overview-empty success-empty">
                            <div className="overview-empty-icon">
                                <CheckCircle aria-hidden="true" />
                            </div>

                            <strong>
                                No claims currently require review
                            </strong>

                            <span>
                                The verification queue is clear.
                            </span>
                        </div>
                    ) : (
                        <div className="overview-claim-list">
                            {reviewClaims.map((claim) => (
                                <button
                                    className="overview-claim-row"
                                    key={claim.id}
                                    onClick={() => onNavigate("review")}
                                >
                                    <div>
                                        <strong>
                                            {claim.claim_number}
                                        </strong>

                                        <span>
                                            Claim #{claim.id}
                                        </span>
                                    </div>

                                    <span className="status-pill status-warning">
                                        Review needed
                                    </span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </section>

            <section className="overview-system-card">
                <div className="system-status-large">
                    <span className="system-status-dot"></span>

                    <div>
                        <strong>
                            TrustLens verification engine
                        </strong>

                        <span>
                            Configuration loaded. Open a submitted claim to start a verification run.
                        </span>
                    </div>
                </div>

                <div className="system-stat">
                    <span>Pipeline</span>
                    <strong>{system?.pipeline_version || "Unavailable"}</strong>
                </div>

                <div className="system-stat">
                    <span>Detector policy</span>
                    <strong>{system?.detector_policy_mode?.replaceAll("_", " ") || "Unavailable"}</strong>
                </div>

                <div className="system-stat">
                    <span>Fusion policy</span>
                    <strong>{system?.fusion_policy_validated ? "Validated" : "Provisional"}</strong>
                </div>
            </section>
        </div>
    );
}

export default AdminOverview;

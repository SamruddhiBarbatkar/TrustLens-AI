import { useEffect, useMemo, useState } from "react";
import ClaimReport from "../components/ClaimReport";
import { getAllClaims, getClaim } from "../services/api";


const TERMINAL_STATUSES = new Set(["APPROVED", "REJECTED"]);

function formatStatus(value) {
    if (!value) return "Not available";
    return value.replaceAll("_", " ").toLowerCase()
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value) {
    if (!value) return "—";
    return new Date(value).toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
    });
}

function MyClaims({onCreateClaim, onResumeDraft}) {
    const [claims, setClaims] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [details, setDetails] = useState(null);
    const [loading, setLoading] = useState(true);
    const [loadingDetails, setLoadingDetails] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        let active = true;
        getAllClaims()
            .then(async (response) => {
                if (!active) return;
                const ownClaims = response.claims || [];
                setClaims(ownClaims);
                if (ownClaims.length > 0) {
                    setSelectedId(ownClaims[0].id);
                    const claimDetails = await getClaim(ownClaims[0].id);
                    if (active) setDetails(claimDetails);
                }
            })
            .catch((requestError) => active && setError(requestError.message))
            .finally(() => active && setLoading(false));
        return () => { active = false; };
    }, []);

    const metrics = useMemo(() => ({
        total: claims.length,
        active: claims.filter((claim) => !TERMINAL_STATUSES.has(claim.status)).length,
        approved: claims.filter((claim) => claim.status === "APPROVED").length,
        review: claims.filter((claim) => claim.status === "ESCALATED").length,
    }), [claims]);

    async function openClaim(claimId) {
        setSelectedId(claimId);
        setLoadingDetails(true);
        setError("");
        try {
            setDetails(await getClaim(claimId));
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setLoadingDetails(false);
        }
    }

    async function refreshClaims() {
        setLoading(true);
        setError("");
        try {
            const response = await getAllClaims();
            const ownClaims = response.claims || [];
            setClaims(ownClaims);
            if (selectedId && ownClaims.some((claim) => claim.id === selectedId)) {
                setDetails(await getClaim(selectedId));
            }
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setLoading(false);
        }
    }

    if (loading && claims.length === 0) {
        return <div className="claimant-loading-card">Loading your claims...</div>;
    }

    return (
        <div className="my-claims-page">
            <section className="my-claims-header">
                <div>
                    <span className="eyebrow">Your claim history</span>
                    <h1>My Claims</h1>
                    <p>Open any claim to see its evidence, analysis, trust indicator, and shared outcome.</p>
                </div>
                <div className="my-claims-actions">
                    <button className="secondary-btn" onClick={refreshClaims}>Refresh</button>
                    <button className="primary-btn" onClick={onCreateClaim}>New claim</button>
                </div>
            </section>

            {error && <div className="toast error">! {error}</div>}

            <section className="claimant-metrics">
                <ClaimMetric label="Total claims" value={metrics.total} />
                <ClaimMetric label="In progress" value={metrics.active} />
                <ClaimMetric label="Approved" value={metrics.approved} tone="success" />
                <ClaimMetric label="Escalated" value={metrics.review} tone="attention" />
            </section>

            {claims.length === 0 ? (
                <section className="claimant-empty clay-card">
                    <div className="claimant-empty-mark">TL</div>
                    <h2>No claims yet</h2>
                    <p>Create your first claim and upload supporting evidence to begin verification.</p>
                    <button className="primary-btn" onClick={onCreateClaim}>Create first claim</button>
                </section>
            ) : (
                <section className="claim-history-layout">
                    <div className="claim-history-list">
                        <div className="claim-history-list-heading">
                            <span>Submissions</span><strong>{claims.length}</strong>
                        </div>
                        {claims.map((claim) => (
                            <button
                                key={claim.id}
                                className={selectedId === claim.id ? "claim-history-item active" : "claim-history-item"}
                                onClick={() => openClaim(claim.id)}
                            >
                                <div><strong>{claim.claim_number}</strong><span>{claim.item_name || formatDate(claim.created_at)}</span></div>
                                <div>
                                    <span className={`claimant-status ${claim.status.toLowerCase()}`}>{formatStatus(claim.status)}</span>
                                    <small>{claim.evidence_count} evidence</small>
                                </div>
                            </button>
                        ))}
                    </div>
                    <div className="claim-history-detail">
                        {loadingDetails || !details
                            ? <div className="claim-detail-loading">Loading claim report...</div>
                            : <>
                                {details.status === "PENDING" && (
                                    <section className="claimant-draft-resume">
                                        <span className="eyebrow">Saved draft</span>
                                        <h2>{details.item_name || "Finish this claim"}</h2>
                                        <p>{details.incident_summary || "Add the claim story and supporting images before submitting."}</p>
                                        <dl>
                                            <div><dt>Claim details</dt><dd>{details.claim_type ? "Saved" : "Needed"}</dd></div>
                                            <div><dt>Evidence images</dt><dd>{details.evidence?.length || 0} added</dd></div>
                                        </dl>
                                        <button className="primary-btn" onClick={() => onResumeDraft(details.id)}>Continue draft</button>
                                    </section>
                                )}
                                {details.status === "SUBMITTED" && (
                                    <div className="claim-submission-notice">
                                        <span>Submitted</span>
                                        <div>
                                            <strong>Awaiting administrator verification</strong>
                                            <p>Your evidence is locked while the operations team processes this claim.</p>
                                        </div>
                                    </div>
                                )}
                                {details.status !== "PENDING" && <ClaimReport
                                    key={`${details.id}-${details.verification_runs?.[0]?.id || 0}`}
                                    claimId={details.id}
                                    initialClaim={details}
                                />}
                            </>}
                    </div>
                </section>
            )}
        </div>
    );
}

function ClaimMetric({label, value, tone = "default"}) {
    return <div className={`claimant-metric ${tone}`}><span>{label}</span><strong>{value}</strong></div>;
}

export default MyClaims;

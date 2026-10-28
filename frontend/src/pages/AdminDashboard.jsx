import { useEffect, useRef, useState } from "react";
import { Scan } from "@phosphor-icons/react";

import { getAllClaims, getClaim } from "../services/api";
import ClaimReport from "../components/ClaimReport";
import {
    canRunVerification,
    getClaimVerificationRuns,
    getVerificationRun,
    startVerification,
} from "../services/verificationService";


function AdminDashboard({
    claimId,
    setClaimId,
    requestedRunId,
}) {
    const [claims, setClaims] = useState([]);
    const [selectedClaim, setSelectedClaim] = useState(null);
    const [verificationRuns, setVerificationRuns] = useState([]);
    const [selectedRun, setSelectedRun] = useState(null);

    const [loadingClaims, setLoadingClaims] = useState(true);
    const [loadingClaim, setLoadingClaim] = useState(false);
    const [loadingRuns, setLoadingRuns] = useState(false);
    const [loadingRun, setLoadingRun] = useState(false);
    const [startingVerification, setStartingVerification] = useState(false);
    const [runningClaimId, setRunningClaimId] = useState(null);
    const [showAdvancedRuns, setShowAdvancedRuns] = useState(Boolean(requestedRunId));

    const [error, setError] = useState("");
    const [runError, setRunError] = useState("");

    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState("ALL");
    const openedClaimIdRef = useRef(null);


    // ==================================================
    // LOAD ALL CLAIMS
    // ==================================================

    async function loadClaims() {
        setLoadingClaims(true);
        setError("");

        try {
            const data = await getAllClaims();

            setClaims(data.claims || []);
        } catch (err) {
            setError(
                err.message || "Failed to load claims."
            );
        } finally {
            setLoadingClaims(false);
        }
    }


    // ==================================================
    // LOAD SELECTED CLAIM
    // ==================================================

    async function openClaim(id, runIdToOpen = null) {
        setLoadingClaim(true);
        setError("");
        setRunError("");

        setSelectedClaim(null);
        setVerificationRuns([]);
        setSelectedRun(null);

        try {
            const data = await getClaim(id);

            setSelectedClaim(data);
            openedClaimIdRef.current = Number(id);
            setClaimId(String(id));

            await loadVerificationRuns(
                id,
                runIdToOpen
            );
        } catch (err) {
            setError(
                err.message || "Failed to load claim."
            );
        } finally {
            setLoadingClaim(false);
        }
    }


    // ==================================================
    // LOAD VERIFICATION RUNS
    // ==================================================

    async function loadVerificationRuns(
        id,
        runIdToOpen = null
    ) {
        setLoadingRuns(true);
        setRunError("");

        try {
            const data =
                await getClaimVerificationRuns(id);

            const runs =
                data.verification_runs || [];

            setVerificationRuns(runs);

            /*
             * If a specific run was requested from the
             * Verification Runs page, open that exact run.
             *
             * Otherwise open the latest run.
             */
            if (runs.length > 0) {
                const requestedRun =
                    runIdToOpen !== null
                        ? runs.find(
                              (run) =>
                                  Number(run.id) ===
                                  Number(runIdToOpen)
                          )
                        : null;

                if (requestedRun) {
                    await loadVerificationRun(
                        requestedRun.id,
                        id
                    );
                } else {
                    await loadVerificationRun(
                        runs[0].id,
                        id
                    );
                }
            }
        } catch (err) {
            setRunError(
                err.message ||
                    "Failed to load verification runs."
            );
        } finally {
            setLoadingRuns(false);
        }
    }


    // ==================================================
    // LOAD SINGLE VERIFICATION RUN
    // ==================================================

    async function loadVerificationRun(
        runId,
        expectedClaimId = selectedClaim?.id
    ) {
        setLoadingRun(true);
        setRunError("");

        try {
            const data =
                await getVerificationRun(runId);

            /*
             * Important:
             *
             * runId = Verification Run ID
             * expectedClaimId = Claim ID
             *
             * They must never be confused.
             */
            if (
                expectedClaimId &&
                Number(data.claim_id) !==
                    Number(expectedClaimId)
            ) {
                throw new Error(
                    "This verification run does not belong to the selected claim."
                );
            }

            setSelectedRun(data);
        } catch (err) {
            setSelectedRun(null);

            setRunError(
                err.message ||
                    "Failed to load verification run."
            );
        } finally {
            setLoadingRun(false);
        }
    }

    async function runVerificationForClaim(selectedClaimId) {
        if (!selectedClaimId || startingVerification) return;

        setStartingVerification(true);
        setRunningClaimId(selectedClaimId);
        setError("");
        setRunError("");

        try {
            const result = await startVerification(selectedClaimId);
            await loadClaims();
            await openClaim(selectedClaimId, result.verification_run_id);
        } catch (err) {
            await loadClaims();
            await openClaim(selectedClaimId);
            setRunError(err.message || "Verification failed. The attempt is in the run history; check the service and try again.");
        } finally {
            setStartingVerification(false);
            setRunningClaimId(null);
        }
    }

    const openClaimRef = useRef(openClaim);
    useEffect(() => {
        openClaimRef.current = openClaim;
    });


    // ==================================================
    // INITIAL LOAD
    // ==================================================

    useEffect(() => {
        let active = true;

        async function initializeClaims() {
            try {
                const data = await getAllClaims();
                if (active) setClaims(data.claims || []);
            } catch (err) {
                if (active) setError(err.message || "Failed to load claims.");
            } finally {
                if (active) setLoadingClaims(false);
            }
        }

        initializeClaims();
        return () => {
            active = false;
        };
    }, []);


    // ==================================================
    // OPEN CLAIM / RUN REQUESTED FROM APP
    // ==================================================
    /*
     * App.jsx receives the custom event from
     * VerificationRuns.jsx.
     *
     * App.jsx then changes:
     *
     * adminSection = "claims"
     * adminClaimId = selected claim
     * adminRunId = requested verification run
     *
     * This effect reacts to those values.
     */

    useEffect(() => {
        if (!claimId) {
            return;
        }

        if (openedClaimIdRef.current === Number(claimId) && !requestedRunId) {
            return;
        }

        const timer = window.setTimeout(() => {
            openClaimRef.current(
                Number(claimId),
                requestedRunId ? Number(requestedRunId) : null
            );
        }, 0);

        return () => window.clearTimeout(timer);
    }, [claimId, requestedRunId]);


    // ==================================================
    // FILTER CLAIMS
    // ==================================================

    const filteredClaims = claims.filter((claim) => {
        const query =
            search.trim().toLowerCase();

        const matchesSearch =
            !query ||
            String(claim.id)
                .toLowerCase()
                .includes(query) ||
            String(claim.claim_number || "")
                .toLowerCase()
                .includes(query) ||
            String(claim.claimant?.full_name || "")
                .toLowerCase()
                .includes(query) ||
            String(claim.claimant?.email || "")
                .toLowerCase()
                .includes(query);

        const matchesStatus =
            statusFilter === "ALL" ||
            String(claim.status || "")
                .toUpperCase() === statusFilter;

        return (
            matchesSearch &&
            matchesStatus
        );
    });


    // ==================================================
    // HELPERS
    // ==================================================

    function getStatusClass(status) {
        if (!status) {
            return "status-neutral";
        }

        const normalized =
            String(status).toUpperCase();

        if (
            normalized.includes("COMPLETED") ||
            normalized.includes("AUTHENTIC") ||
            normalized.includes("LOW")
        ) {
            return "status-success";
        }

        if (
            normalized.includes("REVIEW") ||
            normalized.includes("WARNING") ||
            normalized.includes("PENDING") ||
            normalized.includes("SUBMITTED") ||
            normalized.includes("AWAITING") ||
            normalized.includes("STARTED")
        ) {
            return "status-warning";
        }

        if (
            normalized.includes("FAILED") ||
            normalized.includes("ERROR") ||
            normalized.includes("TAMPERED")
        ) {
            return "status-danger";
        }

        return "status-neutral";
    }


    function formatDate(value) {
        if (!value) {
            return "—";
        }

        try {
            return new Date(value).toLocaleString();
        } catch {
            return value;
        }
    }


    function getRunCount(claim) {
        return (
            claim.verification_runs?.length || 0
        );
    }


    function getLatestRun(claim) {
        return (
            claim.verification_runs?.[0] ||
            null
        );
    }


    function findAnalysis(type) {
        if (!selectedRun?.analysis_results) {
            return [];
        }

        return selectedRun.analysis_results.filter(
            (item) =>
                item.analysis_type === type
        );
    }


    // ==================================================
    // DASHBOARD
    // ==================================================

    return (
        <div className="admin-dashboard page-container">

            {/* ======================================== */}
            {/* HEADER */}
            {/* ======================================== */}

            <section className="claim-registry-intro">

                <div>
                    <div className="eyebrow">
                        Searchable claim register
                    </div>

                    <h1>
                        Find a claim. Inspect every run.
                    </h1>

                    <p>
                        The registry is the source record for claim evidence,
                        verification history, and model findings.
                    </p>
                </div>

                <div className="claim-registry-index">
                    <span>Registered claims</span>
                    <strong>{claims.length}</strong>
                    <small>{filteredClaims.length} visible with current filters</small>
                </div>

            </section>


            {/* ======================================== */}
            {/* DASHBOARD METRICS */}
            {/* ======================================== */}

            <dl className="claim-registry-strip">
                <div>
                    <dt>Verification runs</dt>
                    <dd>{claims.reduce(
                        (total, claim) =>
                            total +
                            getRunCount(claim),
                        0
                    )}</dd>
                </div>

                <div>
                    <dt>Pending intake</dt>
                    <dd>{claims.filter(
                        (claim) =>
                            String(
                                claim.status || ""
                            )
                                .toUpperCase()
                                .includes("PENDING")
                    ).length}</dd>
                </div>

                <div>
                    <dt>Under review</dt>
                    <dd>{claims.filter(
                        (claim) =>
                            String(
                                claim.status || ""
                            )
                                .toUpperCase()
                                .includes("REVIEW")
                    ).length}</dd>
                </div>

                <div>
                    <dt>Current view</dt>
                    <dd>{statusFilter === "ALL" ? "All statuses" : formatStatus(statusFilter)}</dd>
                </div>
            </dl>


            {/* ======================================== */}
            {/* ALL CLAIMS */}
            {/* ======================================== */}

            <section className="clay-card claims-list-card">

                <div className="section-heading">

                    <div>
                        <div className="eyebrow">
                            Claim index
                        </div>

                        <h2>
                            Claim registry
                        </h2>

                        <p>
                            Select a claim to inspect its
                            verification history.
                        </p>
                    </div>

                    <button
                        className="secondary-button"
                        onClick={loadClaims}
                        disabled={loadingClaims}
                    >
                        {loadingClaims
                            ? "Refreshing..."
                            : "Refresh"}
                    </button>

                </div>


                {/* SEARCH + FILTER */}

                <div className="claims-toolbar">

                    <input
                        className="admin-input"
                        type="text"
                        value={search}
                        onChange={(event) =>
                            setSearch(
                                event.target.value
                            )
                        }
                        placeholder="Search claim, claimant, or email"
                    />

                    <select
                        className="admin-input"
                        value={statusFilter}
                        onChange={(event) =>
                            setStatusFilter(
                                event.target.value
                            )
                        }
                    >
                        <option value="ALL">
                            All Statuses
                        </option>

                        <option value="PENDING">
                            Pending
                        </option>

                        <option value="SUBMITTED">
                            Submitted
                        </option>

                        <option value="VERIFICATION_STARTED">
                            Verification Started
                        </option>

                        <option value="COMPLETED">
                            Completed
                        </option>

                        <option value="AWAITING_DECISION">
                            Awaiting Decision
                        </option>

                        <option value="REVIEW_NEEDED">
                            Review Needed
                        </option>
                    </select>

                </div>


                {error && (
                    <div className="admin-error">
                        {error}
                    </div>
                )}

                {runError && <div className="admin-inline-error" role="alert">{runError}</div>}


                {loadingClaims ? (
                    <div className="empty-state">
                        Loading claims...
                    </div>
                ) : filteredClaims.length === 0 ? (
                    <div className="empty-state">

                        <strong>
                            No claims found.
                        </strong>

                        <span>
                            Try changing your search
                            or status filter.
                        </span>

                    </div>
                ) : (
                    <div className="claims-table-wrapper">

                        <table className="claims-table">

                            <thead>
                                <tr>
                                    <th>
                                        Claim
                                    </th>

                                    <th>
                                        Claimant
                                    </th>

                                    <th>
                                        Status
                                    </th>

                                    <th>
                                        Evidence
                                    </th>

                                    <th>
                                        Verification Runs
                                    </th>

                                    <th>
                                        Latest Run
                                    </th>

                                    <th>
                                        Action
                                    </th>
                                </tr>
                            </thead>

                            <tbody>

                                {filteredClaims.map(
                                    (claim) => {

                                        const latestRun =
                                            getLatestRun(
                                                claim
                                            );

                                        const isSelected =
                                            selectedClaim?.id ===
                                            claim.id;

                                        return (
                                            <tr
                                                key={claim.id}
                                                className={
                                                    isSelected
                                                        ? "selected-row"
                                                        : ""
                                                }
                                            >

                                                <td>
                                                    <div className="claim-table-main">

                                                        <strong>
                                                            Claim #
                                                            {claim.id}
                                                        </strong>

                                                        <span>
                                                            {claim.claim_number ||
                                                                "No claim number"}
                                                        </span>
                                                        {claim.item_name && <small>{claim.item_name}</small>}

                                                    </div>
                                                </td>


                                                <td>
                                                    <div className="claimant-table-identity">
                                                        <strong>{claim.claimant?.full_name || "Legacy / unassigned"}</strong>
                                                        <span>{claim.claimant?.email || "No account email"}</span>
                                                    </div>
                                                </td>


                                                <td>

                                                    <span
                                                        className={`status-pill ${getStatusClass(
                                                            claim.status
                                                        )}`}
                                                    >
                                                        {claim.status ||
                                                            "UNKNOWN"}
                                                    </span>

                                                </td>


                                                <td>
                                                    {claim.evidence_count ??
                                                        0}
                                                </td>


                                                <td>
                                                    {getRunCount(
                                                        claim
                                                    )}
                                                </td>


                                                <td>

                                                    {latestRun ? (
                                                        <div className="latest-run-cell">

                                                            <strong>
                                                                Run #
                                                                {latestRun.id}
                                                            </strong>

                                                            <span
                                                                className={`status-pill ${getStatusClass(
                                                                    latestRun.status
                                                                )}`}
                                                            >
                                                                {latestRun.status ||
                                                                    "UNKNOWN"}
                                                            </span>

                                                        </div>
                                                    ) : (
                                                        "No run"
                                                    )}

                                                </td>


                                                <td>
                                                    <div className="claim-row-actions">
                                                    <button
                                                        className={
                                                            isSelected
                                                                ? "primary-button small-button"
                                                                : "secondary-button small-button"
                                                        }
                                                        onClick={() =>
                                                            openClaim(
                                                                claim.id
                                                            )
                                                        }
                                                    >
                                                        {isSelected
                                                            ? "Opened"
                                                            : "Open claim"}
                                                    </button>

                                                    {canRunVerification(claim) ? (
                                                        <button
                                                            className="primary-button small-button"
                                                            onClick={() => runVerificationForClaim(claim.id)}
                                                            disabled={startingVerification}
                                                        >
                                                            {runningClaimId === claim.id ? "Running..." : "Run verification"}
                                                        </button>
                                                    ) : claim.status === "PENDING" ? (
                                                        <span className="claim-action-disabled">
                                                            <button className="secondary-button small-button" disabled title="The claimant must submit this draft first.">
                                                                Run verification
                                                            </button>
                                                            <small className="claim-action-hint">Awaiting claimant submission</small>
                                                        </span>
                                                    ) : null}
                                                    </div>

                                                </td>

                                            </tr>
                                        );
                                    }
                                )}

                            </tbody>

                        </table>

                    </div>
                )}

            </section>


            {/* ======================================== */}
            {/* SELECTED CLAIM */}
            {/* ======================================== */}

            {loadingClaim && (
                <section className="clay-card loading-card">
                    Loading claim...
                </section>
            )}


            {selectedClaim &&
                !loadingClaim && (
                    <>

                        <section className="clay-card claim-overview-card">

                            <div className="claim-overview-main">

                                <div className="eyebrow">
                                    Selected claim
                                </div>

                                <h2>
                                    Claim #{selectedClaim.id}
                                </h2>

                                <p>
                                    Claim Number:{" "}
                                    <strong>
                                        {selectedClaim.claim_number ||
                                            "—"}
                                    </strong>
                                </p>

                            </div>

                            <div className="claim-status-block">

                                <span className="small-label">
                                    Claim status
                                </span>

                                <span
                                    className={`status-pill ${getStatusClass(
                                        selectedClaim.status
                                    )}`}
                                >
                                    {selectedClaim.status ||
                                        "UNKNOWN"}
                                </span>

                            </div>

                        </section>

                        {canRunVerification(selectedClaim) && (
                            <section className="claim-run-banner admin-run-banner">
                                <div>
                                    <span>{verificationRuns.length ? "New check available" : "Submitted evidence ready"}</span>
                                    <strong>{verificationRuns.length ? "Run verification again" : "Run image verification"}</strong>
                                    <p>
                                        {verificationRuns.length ? "A new run keeps the previous result in the audit history." : "Check the uploaded images before making a review decision."}
                                    </p>
                                </div>
                                <button
                                    className="primary-button"
                                    onClick={() => runVerificationForClaim(selectedClaim.id)}
                                    disabled={startingVerification}
                                >
                                    <Scan aria-hidden="true" />
                                    {startingVerification ? "Verification running..." : verificationRuns.length ? "Run again" : "Run verification"}
                                </button>
                            </section>
                        )}

                        {selectedClaim.status === "PENDING" && (
                            <div className="admin-inline-notice">
                                This claim is still a claimant draft and cannot be verified until it is submitted.
                            </div>
                        )}

                        <ClaimReport
                            claimId={selectedClaim.id}
                            initialClaim={selectedClaim}
                            initialRun={selectedRun}
                            isAdmin
                            onUpdated={(updatedClaim) => {
                                setSelectedClaim(updatedClaim);
                                setClaims((current) => current.map((item) => (
                                    item.id === updatedClaim.id
                                        ? {...item, status: updatedClaim.status, review_decision: updatedClaim.review_decision}
                                        : item
                                )));
                            }}
                        />


                        <details className="admin-advanced-runs" open={showAdvancedRuns} onToggle={(event) => setShowAdvancedRuns(event.currentTarget.open)}>
                            <summary>Run history and technical analysis <span>{verificationRuns.length} {verificationRuns.length === 1 ? "run" : "runs"}</span></summary>

                        <section className="clay-card verification-history-card">

                            <div className="section-heading">

                                <div>
                                    <div className="eyebrow">
                                        Verification history
                                    </div>

                                    <h2>
                                        Verification Runs
                                    </h2>

                                    <p>
                                        Verification runs associated
                                        with Claim #
                                        {selectedClaim.id}.
                                    </p>
                                </div>

                                <div className="run-count-badge">
                                    {verificationRuns.length}{" "}
                                    {verificationRuns.length === 1
                                        ? "Run"
                                        : "Runs"}
                                </div>

                            </div>


                            {loadingRuns ? (
                                <div className="empty-state">
                                    Loading verification history...
                                </div>
                            ) : verificationRuns.length === 0 ? (
                                <div className="empty-state">

                                    <strong>
                                        No verification runs found.
                                    </strong>

                                    <span>
                                        This claim has not been
                                        verified yet.
                                    </span>

                                </div>
                            ) : (
                                <div className="verification-run-list">

                                    {verificationRuns.map(
                                        (run) => {

                                            const isSelected =
                                                selectedRun?.id ===
                                                run.id;

                                            return (
                                                <button
                                                    key={run.id}
                                                    className={
                                                        isSelected
                                                            ? "verification-run-item selected"
                                                            : "verification-run-item"
                                                    }
                                                    onClick={() =>
                                                        loadVerificationRun(
                                                            run.id,
                                                            selectedClaim.id
                                                        )
                                                    }
                                                >

                                                    <div className="run-main">

                                                        <div className="run-title">
                                                            Verification Run #
                                                            {run.id}
                                                        </div>

                                                        <div className="run-subtitle">
                                                            Belongs to Claim #
                                                            {selectedClaim.id}
                                                        </div>

                                                    </div>


                                                    <div className="run-meta">

                                                        <span
                                                            className={`status-pill ${getStatusClass(
                                                                run.status
                                                            )}`}
                                                        >
                                                            {run.status ||
                                                                "UNKNOWN"}
                                                        </span>

                                                        <span className="run-analysis-count">
                                                            {run.analysis_count ??
                                                                0}{" "}
                                                            analyses
                                                        </span>

                                                        <span className="run-date">
                                                            {formatDate(
                                                                run.completed_at ||
                                                                run.started_at
                                                            )}
                                                        </span>

                                                    </div>

                                                </button>
                                            );
                                        }
                                    )}

                                </div>
                            )}


                        </section>


                        {/* ================================= */}
                        {/* SELECTED RUN DETAILS */}
                        {/* ================================= */}

                        {loadingRun && (
                            <section className="clay-card loading-card">
                                Loading verification run...
                            </section>
                        )}

                        {selectedRun &&
                            !loadingRun && (
                                <AdminVerificationDetails
                                    run={selectedRun}
                                    findAnalysis={findAnalysis}
                                    getStatusClass={
                                        getStatusClass
                                    }
                                    formatDate={formatDate}
                                />
                            )}

                        </details>

                    </>
                )}

        </div>
    );
}


/* ================================================== */
/* VERIFICATION DETAILS                               */
/* ================================================== */

function AdminVerificationDetails({
    run,
    findAnalysis,
    getStatusClass,
    formatDate,
}) {
    const tamperingResults =
        findAnalysis(
            "TAMPERING_DETECTION"
        );

    const aiGenerationResults =
        findAnalysis(
            "AI_GENERATION"
        );

    const trustResults =
        findAnalysis(
            "TRUST_ASSESSMENT"
        );

    const uncertaintyResults =
        findAnalysis(
            "UNCERTAINTY"
        );

    const fusionResults =
        findAnalysis(
            "FUSION"
        );

    const crossEvidenceResults =
        findAnalysis(
            "CROSS_EVIDENCE"
        );


    return (
        <div className="admin-verification-details">

            <section className="clay-card run-header-card">

                <div>

                    <div className="eyebrow">
                        Selected verification
                    </div>

                    <h2>
                        Verification Run #{run.id}
                    </h2>

                    <p>
                        Verification Run #{run.id}
                        belongs to Claim #
                        {run.claim_id}.
                    </p>

                </div>

                <div className="run-header-status">

                    <span className="small-label">
                        Run status
                    </span>

                    <span
                        className={`status-pill ${getStatusClass(
                            run.status
                        )}`}
                    >
                        {run.status || "UNKNOWN"}
                    </span>

                </div>

            </section>


            <section className="admin-stats-grid">

                <AdminMetric
                    label="Verification Run ID"
                    value={`#${run.id}`}
                />

                <AdminMetric
                    label="Claim ID"
                    value={`#${run.claim_id}`}
                />

                <AdminMetric
                    label="Pipeline Version"
                    value={
                        run.pipeline_version || "—"
                    }
                />

                <AdminMetric
                    label="Analysis Results"
                    value={
                        run.analysis_results?.length ||
                        0
                    }
                />

            </section>


            <section className="clay-card run-timeline-card">

                <div className="section-heading">

                    <div>
                        <div className="eyebrow">
                            Execution
                        </div>

                        <h2>
                            Verification Timeline
                        </h2>
                    </div>

                </div>

                <div className="timeline-grid">

                    <TimelineItem
                        label="Started"
                        value={formatDate(
                            run.started_at
                        )}
                    />

                    <TimelineItem
                        label="Completed"
                        value={formatDate(
                            run.completed_at
                        )}
                    />

                    <TimelineItem
                        label="Pipeline"
                        value={
                            run.pipeline_version ||
                            "—"
                        }
                    />

                </div>

            </section>


            <section className="clay-card analysis-section">

                <div className="section-heading">

                    <div>
                        <div className="eyebrow">
                            Forensic analysis
                        </div>

                        <h2>
                            Model Signals
                        </h2>

                        <p>
                            Detailed forensic outputs
                            available to insurance
                            administrators.
                        </p>
                    </div>

                </div>

                <div className="analysis-grid">

                    <TamperingPanel
                        results={tamperingResults}
                    />

                    <AIGenerationPanel
                        results={
                            aiGenerationResults
                        }
                    />

                </div>

            </section>


            <section className="clay-card analysis-section">

                <div className="section-heading">

                    <div>
                        <div className="eyebrow">
                            Claim-level analysis
                        </div>

                        <h2>
                            Evidence Fusion & Trust
                        </h2>
                    </div>

                </div>

                <div className="analysis-grid">

                    <GenericAnalysisPanel
                        title="Trust Assessment"
                        type="TRUST_ASSESSMENT"
                        results={trustResults}
                    />

                    <GenericAnalysisPanel
                        title="Uncertainty"
                        type="UNCERTAINTY"
                        results={
                            uncertaintyResults
                        }
                    />

                    <GenericAnalysisPanel
                        title="Evidence Fusion"
                        type="FUSION"
                        results={fusionResults}
                    />

                    <GenericAnalysisPanel
                        title="Cross-Evidence"
                        type="CROSS_EVIDENCE"
                        results={
                            crossEvidenceResults
                        }
                    />

                </div>

            </section>


            <section className="clay-card analysis-log-card">

                <div className="section-heading">

                    <div>
                        <div className="eyebrow">
                            Analysis log
                        </div>

                        <h2>
                            Complete Verification Results
                        </h2>
                    </div>

                </div>

                <div className="analysis-table-wrapper">

                    <table className="analysis-table">

                        <thead>
                            <tr>
                                <th>
                                    Analysis
                                </th>

                                <th>
                                    Evidence
                                </th>

                                <th>
                                    Status
                                </th>

                                <th>
                                    Message
                                </th>
                            </tr>
                        </thead>

                        <tbody>

                            {(run.analysis_results || [])
                                .map(
                                    (analysis) => (
                                        <tr
                                            key={
                                                analysis.id
                                            }
                                        >

                                            <td>
                                                <strong>
                                                    {
                                                        analysis.analysis_type
                                                    }
                                                </strong>
                                            </td>

                                            <td>
                                                {analysis.evidence_id
                                                    ? `#${analysis.evidence_id}`
                                                    : "Claim-level"}
                                            </td>

                                            <td>

                                                <span
                                                    className={`status-pill ${getStatusClass(
                                                        analysis.status
                                                    )}`}
                                                >
                                                    {
                                                        analysis.status
                                                    }
                                                </span>

                                            </td>

                                            <td>
                                                {
                                                    analysis.message ||
                                                    "—"
                                                }
                                            </td>

                                        </tr>
                                    )
                                )}

                        </tbody>

                    </table>

                </div>

            </section>

        </div>
    );
}


/* ================================================== */
/* TAMPERING PANEL                                    */
/* ================================================== */

function TamperingPanel({ results }) {
    return (
        <div className="analysis-panel">

            <div className="analysis-panel-header">

                <span className="analysis-icon">
                    T
                </span>

                <div>
                    <h3>
                        Tampering Detection
                    </h3>

                    <span>
                        Image manipulation signal
                    </span>
                </div>

            </div>


            {results.length === 0 ? (
                <EmptyAnalysis />
            ) : (
                <div className="analysis-result-list">

                    {results.map((item) => {

                        const result =
                            item.result || {};

                        return (
                            <div
                                className="analysis-result-row"
                                key={item.id}
                            >

                                <div>
                                    <span className="small-label">
                                        Evidence
                                    </span>

                                    <strong>
                                        #
                                        {item.evidence_id ||
                                            "—"}
                                    </strong>
                                </div>

                                <div>
                                    <span className="small-label">
                                        Prediction
                                    </span>

                                    <strong>
                                        {result.prediction ||
                                            "—"}
                                    </strong>
                                </div>

                                <div>
                                    <span className="small-label">
                                        Confidence
                                    </span>

                                    <strong>
                                        {formatProbability(
                                            result.confidence
                                        )}
                                    </strong>
                                </div>

                            </div>
                        );
                    })}

                </div>
            )}

        </div>
    );
}


/* ================================================== */
/* AI GENERATION PANEL                                */
/* ================================================== */

function AIGenerationPanel({
    results,
}) {
    return (
        <div className="analysis-panel">

            <div className="analysis-panel-header">

                <span className="analysis-icon">
                    AI
                </span>

                <div>
                    <h3>
                        AI Generation Detection
                    </h3>

                    <span>
                        Synthetic-image signal
                    </span>
                </div>

            </div>


            {results.length === 0 ? (
                <EmptyAnalysis />
            ) : (
                <div className="analysis-result-list">

                    {results.map((item) => {

                        const result =
                            item.result || {};

                        return (
                            <div
                                className="analysis-result-row"
                                key={item.id}
                            >

                                <div>
                                    <span className="small-label">
                                        Evidence
                                    </span>

                                    <strong>
                                        #
                                        {item.evidence_id ||
                                            "—"}
                                    </strong>
                                </div>

                                <div>
                                    <span className="small-label">
                                        Prediction
                                    </span>

                                    <strong>
                                        {result.prediction ||
                                            "—"}
                                    </strong>
                                </div>

                                <div>
                                    <span className="small-label">
                                        Confidence
                                    </span>

                                    <strong>
                                        {formatProbability(
                                            result.confidence
                                        )}
                                    </strong>
                                </div>

                            </div>
                        );
                    })}

                </div>
            )}

        </div>
    );
}


/* ================================================== */
/* GENERIC ANALYSIS PANEL                             */
/* ================================================== */

const HIDDEN_ANALYSIS_FIELDS = new Set([
    "debug",
    "features",
    "fusion_inputs",
    "logits",
    "model_outputs",
    "raw_logits",
    "technical_details",
]);

function analysisFieldLabel(value) {
    return String(value)
        .replaceAll("_", " ")
        .replace(/\b\w/g, (character) => character.toUpperCase());
}

function analysisFieldValue(key, value) {
    if (value === null || value === undefined || value === "") return "Not available";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (typeof value === "number") {
        const normalizedKey = String(key).toLowerCase();
        if (
            value >= 0 && value <= 1 &&
            /(confidence|probability|ratio|rate|uncertainty|conflict)/.test(normalizedKey)
        ) {
            return `${Math.round(value * 100)}%`;
        }
        return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
    }
    if (Array.isArray(value)) {
        if (value.length === 0) return "None reported";
        if (value.every((entry) => ["string", "number", "boolean"].includes(typeof entry))) {
            return value.map((entry) => analysisFieldValue(key, entry)).join(", ");
        }
        return `${value.length} supporting ${value.length === 1 ? "record" : "records"}`;
    }
    if (typeof value === "string") {
        return value.includes("_") && !value.includes(" ") ? analysisFieldLabel(value).toLowerCase() : value;
    }
    return "Supporting details recorded";
}

function analysisNarrative(value) {
    if (typeof value !== "string") return "";
    const cleanValue = value.trim();
    if (cleanValue.startsWith("{") || cleanValue.startsWith("[")) return "";
    return cleanValue;
}

function readableAnalysisFields(result, prefix = "", depth = 0) {
    if (!result || typeof result !== "object" || Array.isArray(result)) return [];

    return Object.entries(result).flatMap(([key, value]) => {
        if (HIDDEN_ANALYSIS_FIELDS.has(key.toLowerCase())) return [];
        const fieldLabel = prefix
            ? `${prefix} · ${analysisFieldLabel(key)}`
            : analysisFieldLabel(key);

        if (value && typeof value === "object" && !Array.isArray(value) && depth < 1) {
            return readableAnalysisFields(value, fieldLabel, depth + 1);
        }

        return [{key: `${prefix}-${key}`, label: fieldLabel, value: analysisFieldValue(key, value)}];
    });
}

function ReadableAnalysisResult({result, resultId}) {
    const fields = readableAnalysisFields(result).slice(0, 12);

    if (fields.length === 0) {
        return (
            <p className="generic-result-message">
                No additional human-readable findings were reported.
            </p>
        );
    }

    return (
        <dl className="analysis-result-details">
            {fields.map((field, index) => (
                <div key={`${resultId}-${field.key}-${index}`}>
                    <dt>{field.label}</dt>
                    <dd>{field.value}</dd>
                </div>
            ))}
        </dl>
    );
}

function GenericAnalysisPanel({
    title,
    type,
    results,
}) {
    return (
        <div className="analysis-panel">

            <div className="analysis-panel-header">

                <span className="analysis-icon">
                    {type.substring(0, 2)}
                </span>

                <div>
                    <h3>
                        {title}
                    </h3>

                    <span>
                        {type}
                    </span>
                </div>

            </div>


            {results.length === 0 ? (
                <EmptyAnalysis />
            ) : (
                <div className="generic-result-list">

                    {results.map((item) => (

                        <div
                            className="generic-result-item"
                            key={item.id}
                        >

                            <div className="generic-result-status">

                                <span className="small-label">
                                    Status
                                </span>

                                <strong>
                                    {item.status ||
                                        "—"}
                                </strong>

                            </div>

                            {analysisNarrative(item.message) && (
                                <p className="generic-result-message">{analysisNarrative(item.message)}</p>
                            )}

                            <ReadableAnalysisResult result={item.result} resultId={item.id} />

                        </div>

                    ))}

                </div>
            )}

        </div>
    );
}


/* ================================================== */
/* METRIC                                             */
/* ================================================== */

function AdminMetric({
    label,
    value,
}) {
    return (
        <div className="clay-card admin-metric">

            <span className="small-label">
                {label}
            </span>

            <strong className="metric-value">
                {value}
            </strong>

        </div>
    );
}


/* ================================================== */
/* TIMELINE                                           */
/* ================================================== */

function TimelineItem({
    label,
    value,
}) {
    return (
        <div className="timeline-item">

            <span className="small-label">
                {label}
            </span>

            <strong>
                {value}
            </strong>

        </div>
    );
}


/* ================================================== */
/* EMPTY STATE                                        */
/* ================================================== */

function EmptyAnalysis() {
    return (
        <div className="empty-analysis">
            No result available for this analysis stage.
        </div>
    );
}


/* ================================================== */
/* PROBABILITY FORMATTER                              */
/* ================================================== */

function formatProbability(value) {
    if (
        value === null ||
        value === undefined
    ) {
        return "—";
    }

    const number = Number(value);

    if (Number.isNaN(number)) {
        return String(value);
    }

    if (number <= 1) {
        return `${(
            number * 100
        ).toFixed(1)}%`;
    }

    return `${number.toFixed(1)}%`;
}


export default AdminDashboard;

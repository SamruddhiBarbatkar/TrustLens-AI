import { useEffect, useMemo, useState } from "react";

import {
    downloadClaimsReport,
    getReportSummary,
} from "../services/adminService";


function labelFor(value) {
    return value.replaceAll("_", " ").toLowerCase().replace(
        /\b\w/g,
        (letter) => letter.toUpperCase()
    );
}


function Reports() {
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(true);
    const [exporting, setExporting] = useState(false);
    const [error, setError] = useState("");

    async function loadReport() {
        setLoading(true);
        setError("");
        try {
            setReport(await getReportSummary());
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        let active = true;

        getReportSummary()
            .then((data) => {
                if (active) {
                    setReport(data);
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

    const maximumActivity = useMemo(
        () => Math.max(
            1,
            ...(report?.seven_day_activity || []).map((day) => day.claims)
        ),
        [report]
    );

    async function exportReport() {
        setExporting(true);
        setError("");
        try {
            await downloadClaimsReport();
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setExporting(false);
        }
    }

    if (loading) {
        return <div className="loading-card">Building operational report...</div>;
    }

    if (error && !report) {
        return (
            <div className="admin-error">
                <strong>Unable to build report</strong>
                <span>{error}</span>
                <button className="primary-button" onClick={loadReport}>Retry</button>
            </div>
        );
    }

    const metrics = report.metrics;
    const trustEntries = Object.entries(report.trust_distribution);

    return (
        <div className="reports-page">
            <section className="reports-editorial-header">
                <div className="reports-editorial-copy">
                    <div className="admin-section-label">Portfolio report</div>
                    <h2>What happened across claims</h2>
                    <p>
                        A quick view of new claims, verification outcomes, and the cases that still need attention.
                    </p>
                    <div className="reports-actions">
                        <button className="secondary-button" onClick={loadReport}>Refresh report</button>
                        <button
                            className="primary-button"
                            onClick={exportReport}
                            disabled={exporting}
                        >
                            {exporting ? "Preparing CSV..." : "Export claims CSV"}
                        </button>
                    </div>
                </div>
                <div className="reports-headline-stat">
                    <span>Claims this period</span>
                    <strong>{metrics.total_claims}</strong>
                    <small>{metrics.total_evidence} supporting images</small>
                </div>
            </section>

            {error && <div className="admin-inline-error">{error}</div>}

            <section className="report-insights" aria-label="Report highlights">
                <ReportMetric label="Waiting for a reviewer" value={metrics.review_needed} tone="attention" />
                <ReportMetric label="Completed claims" value={metrics.completed_claims} tone="success" />
                <ReportMetric label="Checks run" value={metrics.verification_runs} />
            </section>

            <section className="reports-grid">
                <div className="report-panel">
                    <div className="report-panel-heading">
                        <div>
                            <span>Claim volume</span>
                            <h3>New claim activity</h3>
                        </div>
                    </div>
                    <div className="activity-chart">
                        {report.seven_day_activity.map((day) => (
                            <div className="activity-column" key={day.date}>
                                <strong>{day.claims}</strong>
                                <div className="activity-track">
                                    <div
                                        className="activity-bar"
                                        style={{height: `${Math.max(5, day.claims / maximumActivity * 100)}%`}}
                                    />
                                </div>
                                <span>
                                    {new Date(`${day.date}T00:00:00`).toLocaleDateString(
                                        "en-IN",
                                        {weekday: "short"}
                                    )}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="report-panel">
                    <div className="report-panel-heading">
                        <div>
                            <span>Verification outcomes</span>
                            <h3>How cases were classified</h3>
                        </div>
                    </div>
                    <div className="distribution-list">
                        {trustEntries.map(([name, count]) => (
                            <div className="distribution-row" key={name}>
                                <div>
                                    <span className={`distribution-dot ${name.toLowerCase()}`} />
                                    <strong>{labelFor(name)}</strong>
                                </div>
                                <span>{count}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            <p className="report-generated">Updated {new Date(report.generated_at).toLocaleString("en-IN")}. Open All claims for individual records and Review queue for decisions.</p>
        </div>
    );
}


function ReportMetric({label, value, tone = "default"}) {
    return (
        <div className={`report-metric ${tone}`}>
            <span>{label}</span>
            <strong>{value}</strong>
        </div>
    );
}


export default Reports;

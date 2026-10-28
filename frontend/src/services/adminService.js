import { authenticatedFetch } from "./authService";


export async function getReportSummary() {
    const response = await authenticatedFetch("/admin/reports/summary");
    return await response.json();
}


export async function downloadClaimsReport() {
    const response = await authenticatedFetch("/admin/reports/claims.csv");
    const report = await response.blob();
    const downloadUrl = URL.createObjectURL(report);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = "trustlens-claims-report.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(downloadUrl);
}


export async function getSystemSettings() {
    const response = await authenticatedFetch("/admin/system");
    return await response.json();
}


export async function getReviewQueue() {
    const response = await authenticatedFetch("/admin/reviews/queue");
    return await response.json();
}


export async function getClaimDecisions(claimId) {
    const response = await authenticatedFetch(
        `/admin/claims/${claimId}/decisions`
    );
    return await response.json();
}


export async function createClaimDecision(
    claimId,
    verificationRunId,
    action,
    note
) {
    const response = await authenticatedFetch(
        `/admin/claims/${claimId}/decisions`,
        {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                action,
                note,
                verification_run_id: verificationRunId,
            }),
        }
    );
    return await response.json();
}

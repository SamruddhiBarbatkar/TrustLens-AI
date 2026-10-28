import { authenticatedFetch } from "./authService";

export function canRunVerification(claim) {
    if (!claim) return false;
    const evidenceCount = Array.isArray(claim.evidence)
        ? claim.evidence.length
        : Number(claim.evidence_count || 0);
    return evidenceCount > 0 && ![
        "PENDING", "APPROVED", "REJECTED", "VERIFICATION_STARTED",
    ].includes(String(claim.status || "").toUpperCase());
}

export function verificationUnavailableReason(claim) {
    if (!claim) return "Select a claim to start verification.";
    if (claim.status === "PENDING") {
        return "The claimant must submit this draft before verification can run.";
    }
    if (["APPROVED", "REJECTED"].includes(claim.status)) {
        return "This claim already has a final decision.";
    }
    if (claim.status === "VERIFICATION_STARTED") {
        return "A verification is already in progress for this claim.";
    }
    return "This claim has no uploaded evidence to verify.";
}


// ============================================================
// START VERIFICATION
// ============================================================

export async function startVerification(
    claimId
) {

    const response =
        await authenticatedFetch(
            `/claims/${claimId}/verify`,
            {
                method: "POST"
            }
        );


    return await response.json();
}


// ============================================================
// GET SINGLE VERIFICATION RUN
// ============================================================

export async function getVerificationRun(
    runId
) {

    const response =
        await authenticatedFetch(
            `/claims/verification/${runId}`
        );


    return await response.json();
}


// ============================================================
// GET ALL VERIFICATION RUNS FOR A CLAIM
// ============================================================

export async function getClaimVerificationRuns(
    claimId
) {

    const response =
        await authenticatedFetch(
            `/claims/${claimId}/verification-runs`
        );


    return await response.json();
}

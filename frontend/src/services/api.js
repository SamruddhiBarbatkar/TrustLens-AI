import { authenticatedFetch } from "./authService";


export async function createClaim(details) {

    const response = await authenticatedFetch(
        "/claims/",
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            ...(details ? {body: JSON.stringify(details)} : {})
        }
    );

    return await response.json();
}

export async function updateClaimDetails(claimId, details) {
    const response = await authenticatedFetch(`/claims/${claimId}/details`, {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(details),
    });
    return await response.json();
}


export async function getClaim(claimId) {

    const response = await authenticatedFetch(
        `/claims/${claimId}`
    );

    return await response.json();
}

export async function getAllClaims() {
    const response = await authenticatedFetch(
        "/claims/"
    );

    return await response.json();
}

export async function submitClaim(claimId) {
    const response = await authenticatedFetch(
        `/claims/${claimId}/submit`,
        {method: "POST"}
    );

    return await response.json();
}

export async function getEvidenceImage(claimId, evidenceId) {
    const response = await authenticatedFetch(
        `/claims/${claimId}/evidence/${evidenceId}/file`
    );
    return await response.blob();
}

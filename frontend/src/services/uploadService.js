import { authenticatedFetch } from "./authService";


export async function uploadEvidence(
    claimId,
    evidenceType,
    file,
    context,
    replace = false
) {

    const formData = new FormData();

    formData.append("file", file);
    formData.append("description", context.description.trim());
    formData.append("source_type", context.sourceType);
    formData.append("captured_at", context.capturedAt || "");
    formData.append("location_label", context.location.trim());
    if (replace) formData.append("replace", "true");


    const response = await authenticatedFetch(
        `/claims/${claimId}/upload/${evidenceType}`,
        {
            method: "POST",
            body: formData
        }
    );


    return await response.json();
}

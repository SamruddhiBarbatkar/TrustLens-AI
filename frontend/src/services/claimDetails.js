export const EMPTY_CLAIM_DETAILS = {
    claim_type: "",
    item_name: "",
    reference_number: "",
    incident_date: "",
    incident_summary: "",
};

export function localToday() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function claimDetailsFromRecord(record) {
    return {
        claim_type: record?.claim_type || "",
        item_name: record?.item_name || "",
        reference_number: record?.reference_number || "",
        incident_date: record?.incident_date || "",
        incident_summary: record?.incident_summary || "",
    };
}

export function validateClaimDetails(details) {
    if (!details.claim_type) return "Choose the kind of claim you are making.";
    if (details.item_name.trim().length < 3) return "Enter the item or product name.";
    if (!details.incident_date) return "Enter the date the issue occurred.";
    if (details.incident_date > localToday()) return "The issue date cannot be in the future.";
    if (details.incident_summary.trim().length < 20) return "Describe what happened in at least 20 characters.";
    return "";
}

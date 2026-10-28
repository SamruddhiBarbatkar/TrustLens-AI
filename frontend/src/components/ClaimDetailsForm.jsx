import {localToday} from "../services/claimDetails";

export default function ClaimDetailsForm({details, onChange, disabled = false}) {
    const update = (field) => (event) => onChange({...details, [field]: event.target.value});
    return (
        <div className="claim-details-fields">
            <label>
                <span>Claim type <b>Required</b></span>
                <select value={details.claim_type} onChange={update("claim_type")} disabled={disabled}>
                    <option value="">Choose a claim type</option>
                    <option value="WARRANTY">Warranty or product issue</option>
                    <option value="INSURANCE">Insurance claim</option>
                    <option value="OTHER">Other evidence claim</option>
                </select>
            </label>
            <label>
                <span>Item or product <b>Required</b></span>
                <input value={details.item_name} onChange={update("item_name")} maxLength="120" placeholder="Example: Laptop display" disabled={disabled} />
            </label>
            <label>
                <span>Policy, order or receipt number</span>
                <input value={details.reference_number} onChange={update("reference_number")} maxLength="80" placeholder="Optional reference" disabled={disabled} />
            </label>
            <label>
                <span>Date of issue <b>Required</b></span>
                <input type="date" value={details.incident_date} onChange={update("incident_date")} max={localToday()} disabled={disabled} />
            </label>
            <label className="claim-details-summary-field">
                <span>What happened? <b>Required</b></span>
                <textarea value={details.incident_summary} onChange={update("incident_summary")} maxLength="1000" placeholder="Tell the reviewer what happened, what was affected, and why you are submitting this claim." disabled={disabled} />
                <small>{details.incident_summary.length}/1000 characters</small>
            </label>
        </div>
    );
}

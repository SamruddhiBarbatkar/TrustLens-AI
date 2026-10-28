import { useEffect, useMemo, useState } from "react";
import {
    ArrowRight,
    Camera,
    CheckCircle,
    FileText,
    Package,
    PaperPlaneTilt,
    UploadSimple,
} from "@phosphor-icons/react";

import { createClaim, getClaim, getEvidenceImage, submitClaim, updateClaimDetails } from "../services/api";
import { uploadEvidence } from "../services/uploadService";
import BrandMark from "../components/BrandMark";
import ClaimDetailsForm from "../components/ClaimDetailsForm";
import {EMPTY_CLAIM_DETAILS, claimDetailsFromRecord, validateClaimDetails} from "../services/claimDetails";


const EMPTY_EVIDENCE_CONTEXT = {
    description: "",
    sourceType: "",
    capturedAt: "",
    location: "",
};

const EVIDENCE_TYPES = [
    {id: "product", title: "Product photo", description: "Show the whole item and its identifying details.", icon: Package},
    {id: "damage", title: "Damage photo", description: "Show the affected area clearly and in focus.", icon: Camera},
    {id: "invoice", title: "Purchase document", description: "Show the bill or receipt with the date and seller visible.", icon: FileText},
];


function NewClaim({resumeClaimId, onSubmitted, onViewClaims}) {

    const [claim, setClaim] = useState(null);
    const [selectedType, setSelectedType] = useState(null);
    const [details, setDetails] = useState({...EMPTY_CLAIM_DETAILS});
    const [editingDetails, setEditingDetails] = useState(false);
    const [savingDetails, setSavingDetails] = useState(false);
    const [loadingDraft, setLoadingDraft] = useState(Boolean(resumeClaimId));
    const [replaceType, setReplaceType] = useState(null);
    const [previewRevision, setPreviewRevision] = useState(0);

    const [invoiceFile, setInvoiceFile] =
        useState(null);

    const [productFile, setProductFile] =
        useState(null);

    const [damageFile, setDamageFile] =
        useState(null);

    const [uploadedEvidence, setUploadedEvidence] =
        useState({
            invoice: false,
            product: false,
            damage: false,
        });

    const [evidenceContexts, setEvidenceContexts] = useState({
        invoice: {...EMPTY_EVIDENCE_CONTEXT},
        product: {...EMPTY_EVIDENCE_CONTEXT},
        damage: {...EMPTY_EVIDENCE_CONTEXT},
    });


    const [uploading, setUploading] =
        useState(false);

    const [submitting, setSubmitting] =
        useState(false);

    const [message, setMessage] =
        useState("");

    const [error, setError] =
        useState("");

    useEffect(() => {
        if (!resumeClaimId) return;
        let active = true;
        getClaim(resumeClaimId).then((data) => {
            if (!active) return;
            if (data.status !== "PENDING") {
                localStorage.removeItem("trustlens_last_claim_id");
                setError("That claim has already been submitted. Open My claims to view it.");
                return;
            }
            setClaim(data);
            setDetails(claimDetailsFromRecord(data));
            setEditingDetails(!data.claim_type);
            const stored = Object.fromEntries((data.evidence || []).map((item) => [item.type, true]));
            setUploadedEvidence({invoice: false, product: false, damage: false, ...stored});
            setEvidenceContexts(Object.fromEntries(["invoice", "product", "damage"].map((type) => {
                const evidence = data.evidence?.find((item) => item.type === type);
                return [type, evidence ? {
                    description: evidence.description || "",
                    sourceType: evidence.source_type || "",
                    capturedAt: evidence.captured_at?.slice(0, 16) || "",
                    location: evidence.location_label || "",
                } : {...EMPTY_EVIDENCE_CONTEXT}];
            })));
            setMessage(`Draft ${data.claim_number} ready to continue.`);
        }).catch((requestError) => {
            if (active) setError(requestError.message || "Could not reopen this draft.");
        }).finally(() => {
            if (active) setLoadingDraft(false);
        });
        return () => {active = false;};
    }, [resumeClaimId]);


    // --------------------------------
    // CREATE CLAIM
    // --------------------------------

    async function handleCreateClaim() {

        const validationError = validateClaimDetails(details);
        if (validationError) {setError(validationError); return;}

        try {

            setSavingDetails(true);
            setError("");
            setMessage("");

            const data = await createClaim(details);

            setClaim(data);

            localStorage.setItem(
                "trustlens_last_claim_id",
                String(data.id)
            );

            setMessage(
                `Claim created successfully: ${data.claim_number}`
            );

        } catch (error) {

            console.error(error);

            setError(error.message);
        } finally {
            setSavingDetails(false);
        }
    }

    async function handleSaveDetails() {
        const validationError = validateClaimDetails(details);
        if (validationError) {setError(validationError); return false;}
        setSavingDetails(true);
        setError("");
        try {
            const saved = await updateClaimDetails(claim.id, details);
            setClaim((current) => ({...current, ...saved}));
            setEditingDetails(false);
            setMessage("Claim details saved.");
            return true;
        } catch (requestError) {
            setError(requestError.message || "Could not save claim details.");
            return false;
        } finally {
            setSavingDetails(false);
        }
    }

    async function handleSaveAndLeave() {
        if (editingDetails && !(await handleSaveDetails())) return;
        onViewClaims?.();
    }


    // --------------------------------
    // UPLOAD EVIDENCE
    // --------------------------------

    async function handleUpload(
        evidenceType,
        file,
        replace = false
    ) {

        if (!claim) {

            setError(
                "Please create a claim first."
            );

            return;
        }


        if (!file) {

            setError(
                `Please select a ${evidenceType} file.`
            );

            return;
        }

        const context = evidenceContexts[evidenceType];

        if (context.description.trim().length < 12) {
            setError(
                "Describe what this evidence shows using at least 12 characters."
            );
            return;
        }

        if (!context.sourceType) {
            setError(
                "Select where this evidence came from before uploading."
            );
            return;
        }


        try {

            setUploading(true);

            setError("");
            setMessage("");


            await uploadEvidence(
                claim.id,
                evidenceType,
                file,
                context,
                replace
            );

            const refreshed = await getClaim(claim.id);
            setClaim(refreshed);
            setReplaceType(null);
            setPreviewRevision((current) => current + 1);
            setters[evidenceType](null);

            setUploadedEvidence((current) => ({
                ...current,
                [evidenceType]: true,
            }));


            setMessage(
                `${evidenceType} ${replace ? "replaced" : "uploaded"} successfully.`
            );


        } catch (error) {

            console.error(error);

            setError(error.message);


        } finally {

            setUploading(false);
        }
    }

    function selectFile(evidenceType, file) {
        setError("");
        if (!file) {
            setters[evidenceType](null);
            return;
        }
        const extension = file.name.split(".").pop()?.toLowerCase();
        if (!["jpg", "jpeg", "png", "webp"].includes(extension)) {
            setters[evidenceType](null);
            setError("Choose a JPG, PNG, or WebP image.");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            setters[evidenceType](null);
            setError("This image is over 10 MB. Choose a smaller file.");
            return;
        }
        setters[evidenceType](file);
    }


    // --------------------------------
    // SUBMIT CLAIM FOR ADMINISTRATOR VERIFICATION
    // --------------------------------

    async function handleSubmitClaim() {

        if (!claim) {

            setError(
                "No claim available."
            );

            return;
        }


        try {

            setSubmitting(true);
            setError("");

            setMessage(
                "Submitting claim for administrator verification..."
            );

            const result = await submitClaim(claim.id);
            setClaim((current) => ({...current, status: result.status}));
            setMessage(result.message);
            localStorage.removeItem("trustlens_last_claim_id");
            onSubmitted?.(claim.id);


        } catch (error) {

            console.error(error);

            setError(error.message);
        } finally {
            setSubmitting(false);
        }
    }


    // --------------------------------
    // MAIN CLAIM PAGE
    // --------------------------------

    const uploadedCount = Object.values(uploadedEvidence).filter(Boolean).length;
    const canSubmitClaim = uploadedCount > 0 && !uploading && !submitting && !editingDetails;
    const selectedEvidence = EVIDENCE_TYPES.find((item) => item.id === selectedType);
    const files = {invoice: invoiceFile, product: productFile, damage: damageFile};
    const setters = {invoice: setInvoiceFile, product: setProductFile, damage: setDamageFile};

    return (

        <div className="page-container">

            {/* HERO */}

            <section className="hero-card clay-card">

                <div className="hero-copy">

                    <span className="eyebrow">
                        New claim
                    </span>


                    <h1>
                        Submit your claim.
                        <br />
                        Let the evidence speak.
                    </h1>


                    <p>
                        Add a photo and explain what it shows. A reviewer will check the evidence after you submit.
                    </p>


                    <span className="claim-intake-step">01 / Tell us what happened &nbsp; 02 / Add evidence &nbsp; 03 / Submit for review</span>

                </div>


                <div className="hero-orb">

                    <div className="orb-inner">
                        <BrandMark className="hero-logo" />
                    </div>

                </div>

            </section>

            {loadingDraft && <section className="claim-intake-card clay-card" role="status">Opening your saved draft...</section>}

            {!loadingDraft && (!claim || editingDetails) && (
                <section className="claim-intake-card clay-card" aria-labelledby="claim-details-title">
                    <div className="claim-intake-heading">
                        <div>
                            <span className="eyebrow">{claim ? "Edit draft" : "Step 1 · Claim details"}</span>
                            <h2 id="claim-details-title">Tell us about the claim</h2>
                            <p>Give the reviewer the essential context. You can edit these details until you submit.</p>
                        </div>
                        {claim && <span className="claim-intake-reference">{claim.claim_number}</span>}
                    </div>
                    <ClaimDetailsForm details={details} onChange={setDetails} disabled={savingDetails} />
                    <div className="claim-intake-actions">
                        <button className="primary-btn" onClick={claim ? handleSaveDetails : handleCreateClaim} disabled={savingDetails}>
                            {claim ? "Save details" : "Save draft and continue"}
                            <ArrowRight aria-hidden="true" />
                        </button>
                        {claim?.claim_type && <button className="secondary-btn" onClick={() => {setDetails(claimDetailsFromRecord(claim)); setEditingDetails(false); setError("");}} disabled={savingDetails}>Cancel</button>}
                    </div>
                </section>
            )}

            {claim && !editingDetails && (
                <section className="claim-intake-summary clay-card" aria-label="Claim details">
                    <div><span className="eyebrow">Saved draft</span><h2>{claim.item_name || "Claim details"}</h2><p>{claim.incident_summary || "Add the claim details before submitting."}</p></div>
                    <dl>
                        <div><dt>Type</dt><dd>{claim.claim_type === "WARRANTY" ? "Warranty" : claim.claim_type === "INSURANCE" ? "Insurance" : "Other"}</dd></div>
                        <div><dt>Issue date</dt><dd>{claim.incident_date || "Not provided"}</dd></div>
                        {claim.reference_number && <div><dt>Reference</dt><dd>{claim.reference_number}</dd></div>}
                    </dl>
                    <button className="secondary-btn" onClick={() => setEditingDetails(true)}>Edit details</button>
                </section>
            )}


            {/* CLAIM INFORMATION */}

            {claim && (

                <section className="claim-strip clay-card">

                    <div>

                        <span className="muted-label">
                            Claim number
                        </span>

                        <strong>
                            {claim.claim_number}
                        </strong>

                    </div>


                    <div>

                        <span className="muted-label">
                            Status
                        </span>

                        <span className="status-pill pending">
                            {claim.status}
                        </span>

                    </div>

                </section>

            )}


            {/* EVIDENCE */}

            {claim && (

                <>

                    <section className="section-heading">

                        <div>

                            <span className="eyebrow">
                                Evidence files
                            </span>

                            <h2>
                                What would you like to upload?
                            </h2>

                            <p>
                                Choose one image type, then add its photo and context. You can add other types before submitting.
                            </p>

                        </div>

                    </section>


                    <aside className="evidence-guidance" aria-label="Evidence upload guidance">
                        <div>
                            <strong>Use the clearest available image</strong>
                            <span>Keep the complete product or document visible and avoid screenshots when the original is available.</span>
                        </div>
                        <div>
                            <strong>Describe the visible evidence</strong>
                            <span>State what the image shows, where it came from, and when it was captured or issued.</span>
                        </div>
                        <div>
                            <strong>Do not add sensitive secrets</strong>
                            <span>Never include passwords, PINs, or unrelated personal documents in the description.</span>
                        </div>
                    </aside>


                    <div className="evidence-type-picker" role="group" aria-label="Choose evidence type">
                        {EVIDENCE_TYPES.map(({id, title, description, icon: Icon}) => (
                            <button
                                key={id}
                                type="button"
                                className={`evidence-type-option ${selectedType === id ? "selected" : ""}`}
                                onClick={() => { setSelectedType(id); setError(""); }}
                                aria-pressed={selectedType === id}
                                disabled={uploading || submitting}
                            >
                                <Icon aria-hidden="true" weight="duotone" />
                                <span><strong>{title}</strong><small>{description}</small></span>
                                {uploadedEvidence[id] && <CheckCircle className="evidence-type-check" aria-label="Uploaded" weight="fill" />}
                            </button>
                        ))}
                    </div>

                    {selectedEvidence ? (
                        uploadedEvidence[selectedEvidence.id] && replaceType !== selectedEvidence.id ? (
                            <SavedEvidenceCard
                                key={`${selectedEvidence.id}-${previewRevision}`}
                                claimId={claim.id}
                                evidence={claim.evidence?.find((item) => item.type === selectedEvidence.id)}
                                title={selectedEvidence.title}
                                onReplace={() => {setReplaceType(selectedEvidence.id); setters[selectedEvidence.id](null); setError("");}}
                            />
                        ) : <UploadCard
                            key={selectedEvidence.id}
                            evidenceType={selectedEvidence.id}
                            title={selectedEvidence.title}
                            description={selectedEvidence.description}
                            file={files[selectedEvidence.id]}
                            setFile={(file) => selectFile(selectedEvidence.id, file)}
                            onUpload={() => handleUpload(selectedEvidence.id, files[selectedEvidence.id], replaceType === selectedEvidence.id)}
                            uploading={uploading}
                            uploaded={false}
                            replacing={replaceType === selectedEvidence.id}
                            onCancel={() => setReplaceType(null)}
                            context={evidenceContexts[selectedEvidence.id]}
                            setContext={(field, value) => setEvidenceContexts((current) => ({
                                ...current,
                                [selectedEvidence.id]: {...current[selectedEvidence.id], [field]: value},
                            }))}
                            icon={<selectedEvidence.icon aria-hidden="true" />}
                            accept=".jpg,.jpeg,.png,.webp"
                        />
                    ) : (
                        <div className="evidence-selection-prompt">Choose the kind of image you want to add. We’ll ask only for details relevant to that image.</div>
                    )}


                    {/* NEXT STEP */}

                    <section className="action-panel clay-card">

                        <div>

                            <span className="eyebrow">
                                Ready for review?
                            </span>

                            <h3>Submit claim for verification</h3>

                            <p>
                                {uploadedCount} {uploadedCount === 1 ? "image" : "images"} added. You can return to this draft from My claims until you submit it.
                            </p>

                        </div>


                        <div className="claim-verification-actions">
                            <button
                                className="primary-btn run-verification-btn"
                                onClick={handleSubmitClaim}
                                disabled={!canSubmitClaim}
                            >
                                <PaperPlaneTilt aria-hidden="true" />
                                {submitting
                                    ? "Submitting claim..."
                                    : uploadedCount > 0
                                        ? "Submit claim"
                                        : "Upload evidence to continue"}
                            </button>
                            <button
                                className="secondary-btn"
                                onClick={handleSaveAndLeave}
                                disabled={submitting || savingDetails}
                            >
                                Save and leave
                                <ArrowRight aria-hidden="true" />
                            </button>
                        </div>

                    </section>

                </>

            )}


            {/* MESSAGES */}

            {uploading && (

                <div className="toast info">
                    Uploading evidence...
                </div>

            )}


            {message && (

                <div className="toast success">
                    <CheckCircle aria-hidden="true" /> {message}
                </div>

            )}


            {error && (

                <div className="toast error">
                    ! {error}
                </div>

            )}

        </div>
    );
}


// ========================================
// UPLOAD CARD
// ========================================

function UploadCard({
    evidenceType,
    title,
    description,
    file,
    setFile,
    onUpload,
    uploading,
    uploaded,
    replacing,
    onCancel,
    context,
    setContext,
    icon,
    accept
}) {

    return (

        <article className="upload-card contextual-upload-card">

            <div className="upload-card-top">

                <span className="step-number">Selected evidence</span>

                <span className="upload-icon">
                    {icon}
                </span>

            </div>


            <h3>
                {title}
            </h3>


            <p>
                {description}
            </p>


            <SelectedImagePreview file={file} title={title} />


            <label className="file-drop">

                <input
                    type="file"
                    accept={accept}
                    disabled={uploaded}
                    onChange={(event) =>
                        setFile(
                            event.target.files[0]
                        )
                    }
                />


                <span className="upload-arrow">
                    <UploadSimple aria-hidden="true" />
                </span>


                <strong>
                    {file
                        ? file.name
                        : uploaded
                            ? "Upload complete"
                            : "Choose a file"}
                </strong>


                <small>
                    {file
                        ? uploaded
                            ? "Evidence registered"
                            : "Ready to upload"
                        : uploaded
                            ? "One file allowed per evidence type"
                            : "JPG, PNG or WebP • Maximum 10 MB"}
                </small>

            </label>


            <fieldset className="evidence-context-fields" disabled={uploaded}>
                <legend>Evidence context</legend>

                <label className="evidence-context-field context-description">
                    <span>{evidenceType === "invoice" ? "What purchase does this document show?" : evidenceType === "damage" ? "What damage is visible?" : "What item does this photo show?"} <b>Required</b></span>
                    <textarea
                        value={context.description}
                        onChange={(event) => setContext("description", event.target.value)}
                        maxLength="500"
                        placeholder={`Example: ${title === "Damage photo" ? "Cracked screen and impact mark on the upper-right corner." : title === "Purchase document" ? "Purchase invoice showing the product, seller, and transaction date." : "Front and rear view of the insured product before assessment."}`}
                    />
                    <small>{context.description.length}/500 characters</small>
                </label>

                <label className="evidence-context-field">
                    <span>Evidence origin <b>Required</b></span>
                    <select
                        value={context.sourceType}
                        onChange={(event) => setContext("sourceType", event.target.value)}
                    >
                        <option value="">Select origin</option>
                        <option value="ORIGINAL_CAMERA">Original camera photo</option>
                        <option value="DEVICE_GALLERY">Existing photo from this device</option>
                        {evidenceType === "invoice" && <option value="DOCUMENT_SCAN">Scanned document</option>}
                        <option value="RECEIVED_FROM_OTHER">Received from another person</option>
                    </select>
                </label>

                <label className="evidence-context-field">
                    <span>{evidenceType === "invoice" ? "Document issue date" : "Photo capture date"}</span>
                    <input
                        type="datetime-local"
                        value={context.capturedAt}
                        onChange={(event) => setContext("capturedAt", event.target.value)}
                    />
                </label>

                <label className="evidence-context-field context-location">
                    <span>{evidenceType === "invoice" ? "Seller or store" : "Where was this photo taken?"}</span>
                    <input
                        value={context.location}
                        onChange={(event) => setContext("location", event.target.value)}
                        maxLength="160"
                        placeholder={evidenceType === "invoice" ? "Example: Store name on the receipt" : "Example: Home, Pune"}
                    />
                </label>
            </fieldset>


            <button
                className="small-btn"
                onClick={onUpload}
                disabled={
                    uploading ||
                    uploaded ||
                    !file ||
                    context.description.trim().length < 12 ||
                    !context.sourceType
                }
            >
                {uploaded
                    ? `${title} Uploaded`
                    : replacing ? `Replace ${title}` : `Upload ${title}`}
            </button>
            {replacing && <button className="secondary-btn upload-cancel-btn" onClick={onCancel} disabled={uploading}>Keep current photo</button>}

        </article>
    );
}


function SavedEvidenceCard({claimId, evidence, title, onReplace}) {
    const [imageUrl, setImageUrl] = useState("");
    useEffect(() => {
        if (!evidence?.id) return;
        let active = true;
        let url = "";
        getEvidenceImage(claimId, evidence.id).then((blob) => {
            url = URL.createObjectURL(blob);
            if (active) setImageUrl(url);
            else URL.revokeObjectURL(url);
        }).catch(() => {});
        return () => {active = false; if (url) URL.revokeObjectURL(url);};
    }, [claimId, evidence?.id]);

    return (
        <article className="saved-evidence-card">
            <div className="saved-evidence-image">{imageUrl ? <img src={imageUrl} alt={`${title} saved to this claim`} /> : <Camera aria-hidden="true" />}</div>
            <div className="saved-evidence-body">
                <span className="saved-evidence-status"><CheckCircle weight="fill" aria-hidden="true" /> Saved to draft</span>
                <h3>{title}</h3>
                <strong>{evidence?.original_filename || "Uploaded image"}</strong>
                <p>{evidence?.description || "No description provided."}</p>
                <button type="button" className="secondary-btn" onClick={onReplace}>Replace photo or details</button>
            </div>
        </article>
    );
}


function SelectedImagePreview({file, title}) {
    const previewUrl = useMemo(
        () => file ? URL.createObjectURL(file) : "",
        [file]
    );

    useEffect(() => {
        return () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
        };
    }, [previewUrl]);

    if (!previewUrl) {
        return (
            <div className="evidence-preview-placeholder">
                <Camera aria-hidden="true" />
                <span>Image preview</span>
            </div>
        );
    }

    return (
        <div className="evidence-preview">
            <img src={previewUrl} alt={`Selected ${title.toLowerCase()} evidence preview`} />
        </div>
    );
}


export default NewClaim;

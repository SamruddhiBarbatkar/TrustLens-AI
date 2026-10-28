import { useEffect, useState } from "react";

import { getSystemSettings } from "../services/adminService";
import {
    changePassword,
    updateProfile,
} from "../services/authService";


function Settings({user, onUserUpdated}) {
    const [fullName, setFullName] = useState(user.full_name);
    const [currentPassword, setCurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [system, setSystem] = useState(null);
    const [savingProfile, setSavingProfile] = useState(false);
    const [savingPassword, setSavingPassword] = useState(false);
    const [profileMessage, setProfileMessage] = useState("");
    const [passwordMessage, setPasswordMessage] = useState("");
    const [error, setError] = useState("");

    useEffect(() => {
        getSystemSettings()
            .then(setSystem)
            .catch((requestError) => setError(requestError.message));
    }, []);

    async function submitProfile(event) {
        event.preventDefault();
        setSavingProfile(true);
        setError("");
        setProfileMessage("");
        try {
            const updatedUser = await updateProfile(fullName);
            onUserUpdated(updatedUser);
            setProfileMessage("Profile updated successfully.");
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSavingProfile(false);
        }
    }

    async function submitPassword(event) {
        event.preventDefault();
        setError("");
        setPasswordMessage("");

        if (newPassword !== confirmPassword) {
            setError("New password confirmation does not match.");
            return;
        }

        setSavingPassword(true);
        try {
            const result = await changePassword(currentPassword, newPassword);
            setPasswordMessage(result.message);
            setCurrentPassword("");
            setNewPassword("");
            setConfirmPassword("");
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSavingPassword(false);
        }
    }

    return (
        <div className="settings-page">
            <section className="settings-console-header">
                <div>
                    <div className="admin-section-label">Account and system</div>
                    <h2>Identity, access, and runtime</h2>
                    <p>
                        Maintain your administrator identity, secure your account,
                        and inspect the configuration currently serving decisions.
                    </p>
                </div>
                <div className="settings-identity-card">
                    <span>Signed in administrator</span>
                    <strong>{user.full_name}</strong>
                    <small>{user.email}</small>
                </div>
            </section>

            {error && <div className="admin-inline-error">{error}</div>}

            <section className="settings-grid">
                <form className="settings-card" onSubmit={submitProfile}>
                    <div className="settings-card-heading">
                        <span>Profile</span>
                        <h3>Administrator details</h3>
                    </div>

                    <label className="settings-field">
                        <span>Full name</span>
                        <input
                            value={fullName}
                            onChange={(event) => setFullName(event.target.value)}
                            minLength="2"
                            required
                        />
                    </label>

                    <label className="settings-field">
                        <span>Email address</span>
                        <input value={user.email} disabled />
                        <small>Email changes require system-owner approval.</small>
                    </label>

                    <label className="settings-field">
                        <span>Access role</span>
                        <input value={user.role} disabled />
                    </label>

                    {profileMessage && <div className="settings-success">{profileMessage}</div>}

                    <button className="primary-button" disabled={savingProfile}>
                        {savingProfile ? "Saving..." : "Save profile"}
                    </button>
                </form>

                <form className="settings-card" onSubmit={submitPassword}>
                    <div className="settings-card-heading">
                        <span>Security</span>
                        <h3>Change password</h3>
                    </div>

                    <label className="settings-field">
                        <span>Current password</span>
                        <input
                            type="password"
                            value={currentPassword}
                            onChange={(event) => setCurrentPassword(event.target.value)}
                            autoComplete="current-password"
                            required
                        />
                    </label>

                    <label className="settings-field">
                        <span>New password</span>
                        <input
                            type="password"
                            value={newPassword}
                            onChange={(event) => setNewPassword(event.target.value)}
                            autoComplete="new-password"
                            minLength="8"
                            required
                        />
                    </label>

                    <label className="settings-field">
                        <span>Confirm new password</span>
                        <input
                            type="password"
                            value={confirmPassword}
                            onChange={(event) => setConfirmPassword(event.target.value)}
                            autoComplete="new-password"
                            minLength="8"
                            required
                        />
                    </label>

                    {passwordMessage && <div className="settings-success">{passwordMessage}</div>}

                    <button className="primary-button" disabled={savingPassword}>
                        {savingPassword ? "Updating..." : "Update password"}
                    </button>
                </form>
            </section>

            <section className="settings-card system-card">
                <div className="settings-card-heading">
                    <span>Runtime</span>
                    <h3>System configuration</h3>
                </div>

                {!system ? (
                    <p className="settings-muted">Loading system information...</p>
                ) : (
                    <div className="system-settings-grid">
                        <SystemValue label="API version" value={system.api_version} />
                        <SystemValue label="Pipeline version" value={system.pipeline_version} />
                        <SystemValue
                            label="Detector policy"
                            value={labelRuntimeValue(system.detector_policy_mode)}
                        />
                        <SystemValue
                            label="ResNet shadow"
                            value={system.resnet_shadow_enabled ? "Enabled" : "Disabled"}
                        />
                        <SystemValue label="Fusion policy" value={system.fusion_policy_version} />
                        <SystemValue
                            label="Calibration"
                            value={system.fusion_policy_validated ? "Validated" : "Provisional"}
                        />
                        <SystemValue
                            label="AI detector"
                            value={readiness(system.model_status?.ai_generation_efficientnet)}
                        />
                        <SystemValue
                            label="Authenticity detector"
                            value={readiness(system.model_status?.authenticity_efficientnet)}
                        />
                        <SystemValue
                            label="ResNet shadow model"
                            value={readiness(system.model_status?.tampering_resnet_shadow)}
                        />
                        <SystemValue
                            label="Primary model readiness"
                            value={readiness(system.model_status?.primary_models_ready)}
                        />
                        <SystemValue label="Database" value={system.database_engine.toUpperCase()} />
                        <SystemValue label="Upload limit" value={`${system.maximum_upload_mb} MB`} />
                        <SystemValue label="Session lifetime" value={`${system.access_token_minutes} minutes`} />
                        <SystemValue label="OCR" value={system.ocr_configured ? "Configured" : "Auto-detected"} />
                    </div>
                )}

                {system && (
                    <p className="settings-runtime-note">
                        Accepted evidence images: {system.accepted_upload_types.join(", ")}.
                        Runtime values are managed through backend environment variables.
                    </p>
                )}
            </section>
        </div>
    );
}


function SystemValue({label, value}) {
    return (
        <div className="system-value">
            <span>{label}</span>
            <strong>{value}</strong>
        </div>
    );
}


function labelRuntimeValue(value) {
    return String(value || "Unknown")
        .toLowerCase()
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function readiness(value) {
    if (value === true) return "Ready";
    if (value === false) return "Missing";
    return "Unavailable";
}


export default Settings;

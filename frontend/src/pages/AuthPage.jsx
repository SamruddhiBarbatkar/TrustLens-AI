import { useState } from "react";
import { ArrowLeft, ArrowRight } from "@phosphor-icons/react";
import BrandMark from "../components/BrandMark";

import {
    loginAccount,
    registerAccount,
} from "../services/authService";


function AuthPage({onAuthenticated, onBack}) {
    const [mode, setMode] = useState("login");
    const [fullName, setFullName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    const isRegistration = mode === "register";

    async function handleSubmit(event) {
        event.preventDefault();
        setSubmitting(true);
        setError("");

        try {
            const user = isRegistration
                ? await registerAccount({
                      email,
                      full_name: fullName,
                      password,
                  })
                : await loginAccount(email, password);

            onAuthenticated(user);
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSubmitting(false);
        }
    }

    function changeMode(nextMode) {
        setMode(nextMode);
        setError("");
        setPassword("");
    }

    return (
        <main className="auth-page">
            <section className="auth-story">
                <button className="auth-back-button" type="button" onClick={onBack}>
                    <ArrowLeft weight="bold" /> Back to overview
                </button>
                <div className="auth-brand">
                    <BrandMark />
                    <div>
                        <div className="brand-name">TrustLens AI</div>
                        <div className="brand-subtitle">
                            Evidence intelligence for insurance
                        </div>
                    </div>
                </div>

                <div className="auth-story-content">
                    <span className="eyebrow">Secure claim verification</span>
                    <h1>Every claim deserves an evidence-led decision.</h1>
                    <p>
                        Submit evidence, follow verification progress, and give
                        authorized reviewers one reliable operational view.
                    </p>

                    <div className="auth-signal-list">
                        <span>Image forensics</span>
                        <span>Document intelligence</span>
                        <span>Cross-evidence review</span>
                    </div>
                </div>

                <small>TrustLens AI · Protected claimant and reviewer access</small>
            </section>

            <section className="auth-panel">
                <div className="auth-card">
                    <div className="auth-heading">
                        <span className="eyebrow">
                            {isRegistration ? "Create claimant account" : "Welcome back"}
                        </span>
                        <h2>
                            {isRegistration ? "Start a secure claim" : "Sign in to TrustLens"}
                        </h2>
                        <p>
                            {isRegistration
                                ? "Create your account to submit and track your own claims."
                                : "Use your claimant or insurance administrator account."}
                        </p>
                    </div>

                    <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
                        <button
                            type="button"
                            className={mode === "login" ? "active" : ""}
                            onClick={() => changeMode("login")}
                        >
                            Sign in
                        </button>
                        <button
                            type="button"
                            className={mode === "register" ? "active" : ""}
                            onClick={() => changeMode("register")}
                        >
                            Create account
                        </button>
                    </div>

                    <form className="auth-form" onSubmit={handleSubmit}>
                        {isRegistration && (
                            <label>
                                <span>Full name</span>
                                <input
                                    value={fullName}
                                    onChange={(event) => setFullName(event.target.value)}
                                    autoComplete="name"
                                    minLength="2"
                                    required
                                    placeholder="Your full name"
                                />
                            </label>
                        )}

                        <label>
                            <span>Email address</span>
                            <input
                                type="email"
                                value={email}
                                onChange={(event) => setEmail(event.target.value)}
                                autoComplete="email"
                                required
                                placeholder="you@example.com"
                            />
                        </label>

                        <label>
                            <span>Password</span>
                            <input
                                type="password"
                                value={password}
                                onChange={(event) => setPassword(event.target.value)}
                                autoComplete={isRegistration ? "new-password" : "current-password"}
                                minLength="8"
                                required
                                placeholder="At least 8 characters"
                            />
                        </label>

                        {error && <div className="auth-error" role="alert">{error}</div>}

                        <button className="auth-submit" type="submit" disabled={submitting}>
                            {submitting
                                ? "Please wait..."
                                : isRegistration
                                    ? "Create claimant account"
                                    : "Sign in securely"}
                            {!submitting && <ArrowRight weight="bold" />}
                        </button>
                    </form>

                    <p className="auth-admin-note">
                        Administrators must enter their complete email address,
                        not a username or numeric ID. Accounts are provisioned
                        securely by the system owner.
                    </p>
                </div>
            </section>
        </main>
    );
}


export default AuthPage;

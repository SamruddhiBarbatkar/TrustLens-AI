import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
    ChartDonut,
    ClockCounterClockwise,
    Files,
    Plus,
    Pulse,
    SignOut,
    SlidersHorizontal,
    SquaresFour,
    WarningCircle,
} from "@phosphor-icons/react";

import {
    clearAuthentication,
    getCurrentUser,
    getStoredUser,
} from "./services/authService";
import BrandMark from "./components/BrandMark";

import "./styles/trustlens.css";
import "./styles/premium.css";


const AdminDashboard = lazy(() => import("./pages/AdminDashboard"));
const AdminOverview = lazy(() => import("./pages/AdminOverview"));
const AuthPage = lazy(() => import("./pages/AuthPage"));
const LandingPage = lazy(() => import("./pages/LandingPage"));
const MyClaims = lazy(() => import("./pages/MyClaims"));
const NewClaim = lazy(() => import("./pages/NewClaim"));
const Reports = lazy(() => import("./pages/Reports"));
const ReviewQueue = lazy(() => import("./pages/ReviewQueue"));
const Settings = lazy(() => import("./pages/Settings"));
const VerificationRuns = lazy(() => import("./pages/VerificationRuns"));


const ADMIN_NAVIGATION = [
    {id: "dashboard", label: "Dashboard", icon: SquaresFour},
    {id: "claims", label: "All claims", icon: Files},
    {id: "review", label: "Review queue", icon: WarningCircle},
    {id: "runs", label: "Verification runs", icon: Pulse},
    {id: "reports", label: "Reports", icon: ChartDonut},
    {id: "settings", label: "Settings", icon: SlidersHorizontal},
];


function App() {
    const [user, setUser] = useState(() => getStoredUser());
    const [authChecking, setAuthChecking] = useState(true);
    const [publicView, setPublicView] = useState("landing");
    const [adminSection, setAdminSection] = useState("dashboard");
    const [claimantSection, setClaimantSection] = useState("new");
    const [resumeClaimId, setResumeClaimId] = useState(() => localStorage.getItem("trustlens_last_claim_id"));
    const [adminClaimId, setAdminClaimId] = useState("");
    const [adminRunId, setAdminRunId] = useState(null);

    const isAdmin = user?.role === "ADMIN";
    const activeAdminLabel = useMemo(
        () => ADMIN_NAVIGATION.find((item) => item.id === adminSection)?.label || "Dashboard",
        [adminSection]
    );

    useEffect(() => {
        let active = true;

        async function validateSession() {
            if (!getStoredUser()) {
                setAuthChecking(false);
                return;
            }
            try {
                const currentUser = await getCurrentUser();
                if (active) setUser(currentUser);
            } catch {
                clearAuthentication();
                if (active) setUser(null);
            } finally {
                if (active) setAuthChecking(false);
            }
        }

        function handleExpiredSession() {
            setUser(null);
            setAuthChecking(false);
            setPublicView("auth");
        }

        validateSession();
        window.addEventListener("trustlens:auth-expired", handleExpiredSession);
        return () => {
            active = false;
            window.removeEventListener("trustlens:auth-expired", handleExpiredSession);
        };
    }, []);

    useEffect(() => {
        function handleOpenVerificationRun(event) {
            const claimId = event.detail?.claimId;
            const runId = event.detail?.runId;
            if (!claimId || !runId || user?.role !== "ADMIN") return;
            setAdminClaimId(String(claimId));
            setAdminRunId(Number(runId));
            setAdminSection("claims");
        }

        window.addEventListener("trustlens:open-verification-run", handleOpenVerificationRun);
        return () => {
            window.removeEventListener("trustlens:open-verification-run", handleOpenVerificationRun);
        };
    }, [user]);

    function handleLogout() {
        clearAuthentication();
        setUser(null);
        setAdminSection("dashboard");
        setAdminClaimId("");
        setAdminRunId(null);
        setClaimantSection("new");
        setResumeClaimId(null);
        setPublicView("landing");
    }

    function navigateAdmin(section) {
        setAdminSection(section);
        if (section !== "claims") setAdminRunId(null);
    }

    function renderAdminContent() {
        if (adminSection === "dashboard") {
            return (
                <AdminOverview
                    onNavigate={navigateAdmin}
                    onOpenClaim={(claimId) => {
                        setAdminClaimId(String(claimId));
                        setAdminRunId(null);
                        setAdminSection("claims");
                    }}
                />
            );
        }
        if (adminSection === "claims") {
            return (
                <AdminDashboard
                    claimId={adminClaimId}
                    setClaimId={setAdminClaimId}
                    requestedRunId={adminRunId}
                />
            );
        }
        if (adminSection === "review") return <ReviewQueue />;
        if (adminSection === "runs") return <VerificationRuns />;
        if (adminSection === "reports") return <Reports />;
        if (adminSection === "settings") {
            return <Settings user={user} onUserUpdated={setUser} />;
        }
        return null;
    }

    if (authChecking) {
        return (
            <div className="auth-loading" role="status">
                <BrandMark />
                <div className="loading-line" />
                <p>Checking your secure session</p>
            </div>
        );
    }

    if (!user) {
        if (publicView === "landing") {
            return (
                <Suspense fallback={<PageFallback label="Opening TrustLens" />}>
                    <LandingPage
                        onSignIn={() => setPublicView("auth")}
                        onStartClaim={() => setPublicView("auth")}
                    />
                </Suspense>
            );
        }
        return (
            <Suspense fallback={<PageFallback label="Opening secure sign in" />}>
                <AuthPage
                    onAuthenticated={setUser}
                    onBack={() => setPublicView("landing")}
                />
            </Suspense>
        );
    }

    return (
        <div className={isAdmin ? "app-shell admin-shell" : "app-shell claimant-shell"}>
            <a className="skip-link" href="#app-main-content">Skip to main content</a>

            {isAdmin ? (
                <>
                    <aside className="admin-sidebar">
                        <div className="admin-sidebar-brand">
                            <BrandMark />
                            <div>
                                <div className="brand-name">TrustLens AI</div>
                                <div className="brand-subtitle">Operations console</div>
                            </div>
                        </div>

                        <div className="admin-sidebar-label">Workspace</div>
                        <nav className="admin-nav" aria-label="Administrator navigation">
                            {ADMIN_NAVIGATION.map((item) => {
                                const Icon = item.icon;
                                const active = adminSection === item.id;
                                return (
                                    <button
                                        key={item.id}
                                        className={active ? "admin-nav-item active" : "admin-nav-item"}
                                        onClick={() => navigateAdmin(item.id)}
                                    >
                                        <span className="admin-nav-icon">
                                            <Icon weight={active ? "fill" : "regular"} />
                                        </span>
                                        <span>{item.label}</span>
                                    </button>
                                );
                            })}
                        </nav>

                        <div className="admin-sidebar-bottom">
                            <div className="admin-system-status">
                                <span className="status-dot" />
                                <div><strong>Reviewer workspace</strong><small>Signed in securely</small></div>
                            </div>
                            <button className="claimant-switch-button" onClick={handleLogout}>
                                <SignOut weight="bold" /> Sign out
                            </button>
                        </div>
                    </aside>

                    <div className="admin-main-shell">
                        <header className="admin-topbar">
                            <div>
                                <div className="admin-breadcrumb">Insurance operations</div>
                                <h1>{activeAdminLabel}</h1>
                            </div>
                            <div className="admin-topbar-right">
                                <span className="topbar-system-chip"><i /> REVIEW CONSOLE</span>
                                <div className="admin-user-info">
                                    <div className="admin-avatar">{initialsFor(user.full_name)}</div>
                                    <div><strong>{user.full_name}</strong><span>Administrator</span></div>
                                </div>
                            </div>
                        </header>
                        <main className="admin-main-content" id="app-main-content">
                            <Suspense fallback={<PageFallback label="Loading workspace" compact />}>
                                {renderAdminContent()}
                            </Suspense>
                        </main>
                        <footer className="admin-footer">
                            TrustLens AI · Insurance operations console
                        </footer>
                    </div>
                </>
            ) : (
                <>
                    <header className="topbar">
                        <div className="brand">
                            <BrandMark />
                            <div><div className="brand-name">TrustLens AI</div><div className="brand-subtitle">Claimant portal</div></div>
                        </div>
                        <nav className="claimant-nav" aria-label="Claimant navigation">
                            <button
                                className={claimantSection === "new" ? "active" : ""}
                                onClick={() => {localStorage.removeItem("trustlens_last_claim_id"); setResumeClaimId(null); setClaimantSection("new");}}
                            ><Plus weight="bold" /> New claim</button>
                            <button
                                className={claimantSection === "history" ? "active" : ""}
                                onClick={() => setClaimantSection("history")}
                            ><ClockCounterClockwise weight="bold" /> My claims</button>
                        </nav>
                        <div className="claimant-session">
                            <span>{user.full_name}</span>
                            <button className="mode-btn" onClick={handleLogout}>
                                <SignOut weight="bold" /> Sign out
                            </button>
                        </div>
                    </header>
                    <main className="main-content" id="app-main-content">
                        <Suspense fallback={<PageFallback label="Loading claim workspace" compact />}>
                            {claimantSection === "new" ? (
                                <NewClaim
                                    key={resumeClaimId || "new"}
                                    resumeClaimId={resumeClaimId}
                                    onViewClaims={() => setClaimantSection("history")}
                                    onSubmitted={() => {setResumeClaimId(null); setClaimantSection("history");}}
                                />
                            ) : (
                                <MyClaims
                                    onCreateClaim={() => {localStorage.removeItem("trustlens_last_claim_id"); setResumeClaimId(null); setClaimantSection("new");}}
                                    onResumeDraft={(id) => {localStorage.setItem("trustlens_last_claim_id", String(id)); setResumeClaimId(String(id)); setClaimantSection("new");}}
                                />
                            )}
                        </Suspense>
                    </main>
                    <footer className="footer">
                        TrustLens AI · Multimodal insurance claim verification
                    </footer>
                </>
            )}
        </div>
    );
}


function PageFallback({label, compact = false}) {
    return (
        <div className={compact ? "route-loading compact" : "route-loading"} role="status">
            <div className="loading-line" />
            <span>{label}</span>
        </div>
    );
}


function initialsFor(name = "") {
    return name.split(" ").filter(Boolean).map((part) => part[0]).slice(0, 2).join("").toUpperCase();
}


export default App;

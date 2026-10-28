import { useEffect, useRef, useState } from "react";
import BrandMark from "../components/BrandMark";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import {
    ArrowRight,
    ArrowUpRight,
    CaretLeft,
    CaretRight,
    ChartLineUp,
    Fingerprint,
    Gauge,
    Scan,
    Stack,
} from "@phosphor-icons/react";


gsap.registerPlugin(ScrollTrigger, useGSAP);


const principles = [
    {
        quote: "A high score is useful only when every contributing signal can be inspected.",
        label: "Explainable by design",
        detail: "Evidence-level outputs remain visible beside the fused decision-support score.",
    },
    {
        quote: "Model disagreement is not hidden. It becomes a reason for human review.",
        label: "Uncertainty stays visible",
        detail: "Conflict, calibration, and reliability travel with the result instead of disappearing behind it.",
    },
    {
        quote: "Administrative decisions remain separate from machine-generated findings.",
        label: "People retain authority",
        detail: "Reviewers approve, reject, or escalate with a permanent rationale and audit trail.",
    },
];


function LandingPage({onSignIn, onStartClaim}) {
    const root = useRef(null);
    const [principleIndex, setPrincipleIndex] = useState(0);

    useEffect(() => {
        const timer = window.setInterval(() => {
            setPrincipleIndex((current) => (current + 1) % principles.length);
        }, 6500);
        return () => window.clearInterval(timer);
    }, []);

    useGSAP(() => {
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            return;
        }

        gsap.from(".landing-hero-copy > *", {
            y: 34,
            opacity: 0,
            duration: 1,
            stagger: 0.09,
            ease: "power3.out",
        });
        gsap.from(".landing-hero-media", {
            x: 70,
            scale: 0.92,
            opacity: 0,
            duration: 1.2,
            ease: "power3.out",
        });

        const words = gsap.utils.toArray(".landing-manifesto-word");
        gsap.fromTo(
            words,
            {opacity: 0.12},
            {
                opacity: 1,
                stagger: 0.035,
                ease: "none",
                scrollTrigger: {
                    trigger: ".landing-manifesto",
                    start: "top 72%",
                    end: "bottom 44%",
                    scrub: 1,
                },
            }
        );

        gsap.utils.toArray(".landing-method-card").forEach((card) => {
            gsap.fromTo(card, {y: 46, opacity: 0.2}, {
                y: 0,
                opacity: 1,
                duration: 0.85,
                ease: "power2.out",
                scrollTrigger: {trigger: card, start: "top 84%"},
            });
        });

    }, {scope: root});

    function movePrinciple(direction) {
        setPrincipleIndex((current) => (
            (current + direction + principles.length) % principles.length
        ));
    }

    const principle = principles[principleIndex];

    return (
        <main className="landing-page" ref={root} id="main-content">
            <nav className="landing-nav" aria-label="Public navigation">
                <a className="landing-brand" href="#top" aria-label="TrustLens AI home">
                    <BrandMark className="brand-symbol" />
                    <span>
                        <strong>TrustLens AI</strong>
                        <small>Evidence intelligence</small>
                    </span>
                </a>

                <div className="landing-nav-links">
                    <a href="#capabilities">Capabilities</a>
                    <a href="#methodology">Methodology</a>
                    <a href="#governance">Governance</a>
                </div>

                <button className="landing-nav-action" onClick={onSignIn}>
                    Sign in <ArrowUpRight weight="bold" />
                </button>
            </nav>

            <section className="landing-hero" id="top">
                <div className="landing-hero-copy">
                    <p className="landing-kicker">For insurance and warranty evidence</p>
                    <h1 className="landing-hero-title">
                        Inspect evidence.<br />Defend decisions.
                    </h1>
                    <p className="landing-hero-lede">
                        TrustLens examines claim images, documents, and model disagreement,
                        then gives reviewers a calibrated decision-support record instead of
                        an unexplained verdict.
                    </p>
                    <div className="landing-hero-actions">
                        <button className="landing-primary-action" onClick={onStartClaim}>
                            Start a claim <ArrowRight weight="bold" />
                        </button>
                        <a className="landing-text-action" href="#methodology">
                            See how evidence is assessed
                        </a>
                    </div>
                    <div className="landing-assurance">
                        <span><i /> Validated hybrid policy</span>
                        <span>Human review remains authoritative</span>
                    </div>
                </div>

                <figure className="landing-hero-media">
                    <img
                        src="/images/trustlens-forensics-hero.png"
                        alt="Precision imaging equipment inspecting damaged device and document evidence"
                    />
                    <figcaption>
                        <span>Evidence workspace</span>
                        <strong>Image, document, and model signals remain traceable.</strong>
                    </figcaption>
                </figure>
            </section>

            <section className="landing-signal-marquee" aria-label="Verification capabilities">
                <div className="landing-marquee-track">
                    {[0, 1].map((copy) => (
                        <div className="landing-marquee-set" key={copy} aria-hidden={copy === 1}>
                            <span>Image quality</span><i />
                            <span>Tampering detection</span><i />
                            <span>AI-generation analysis</span><i />
                            <span>OCR and metadata</span><i />
                            <span>Reliability calibration</span><i />
                            <span>Human review</span><i />
                        </div>
                    ))}
                </div>
            </section>

            <section className="landing-capabilities" id="capabilities">
                <header className="landing-section-heading">
                    <p>One evidence record, multiple forensic views</p>
                    <h2>
                        Built to show the work
                        <span
                            className="landing-inline-image"
                            role="img"
                            aria-label="Forensic evidence inspection"
                        />
                        behind every score.
                    </h2>
                </header>

                <div className="landing-bento">
                    <article className="landing-bento-card landing-bento-primary">
                        <Scan weight="duotone" />
                        <div>
                            <span>Multimodal analysis</span>
                            <h3>Inspect pixels, documents, and context together.</h3>
                            <p>
                                Quality gates, image forensics, OCR, metadata, and trained
                                detectors are attached to the evidence that produced them.
                            </p>
                        </div>
                        <div className="landing-scan-visual" aria-hidden="true">
                            <div className="landing-scan-frame"><i /></div>
                            <span>Evidence quality</span><strong>GOOD</strong>
                        </div>
                    </article>

                    <article className="landing-bento-card landing-bento-calibration">
                        <Gauge weight="duotone" />
                        <span>Reliability-aware</span>
                        <h3>Confidence is calibrated before it is trusted.</h3>
                        <div className="landing-calibration-line" aria-hidden="true"><i /></div>
                    </article>

                    <article className="landing-bento-card landing-bento-audit">
                        <Fingerprint weight="duotone" />
                        <span>Accountable review</span>
                        <h3>Every decision keeps its reviewer rationale.</h3>
                    </article>

                    <article className="landing-bento-card landing-bento-score">
                        <ChartLineUp weight="duotone" />
                        <span>Decision support</span>
                        <strong>79.4</strong>
                        <small>illustrative trust indicator</small>
                    </article>
                </div>
            </section>

            <section className="landing-manifesto" aria-label="TrustLens design principle">
                <p>
                    {"TrustLens does not claim to prove truth. It measures evidence, exposes uncertainty, and routes difficult cases to people who can justify the final decision."
                        .split(" ")
                        .map((word, index) => (
                            <span className="landing-manifesto-word" key={`${word}-${index}`}>{word} </span>
                        ))}
                </p>
            </section>

            <section className="landing-methodology" id="methodology">
                <div className="landing-methodology-intro">
                    <p>From upload to accountable outcome</p>
                    <h2>A forensic pipeline designed for scrutiny.</h2>
                    <span>
                        Each stage preserves its own status, model identity, and explanation,
                        so missing evidence never masquerades as certainty.
                    </span>
                </div>

                <div className="landing-methodology-list">
                    <MethodCard
                        icon={Stack}
                        index="01"
                        title="Collect and preserve"
                        copy="Claimants create a structured record and attach invoice, product, and damage evidence through validated uploads."
                    />
                    <MethodCard
                        icon={Scan}
                        index="02"
                        title="Administrator starts verification"
                        copy="After submission, an authorized reviewer starts the pipeline that measures quality, forensics, tampering, synthetic generation, metadata, and text signals per evidence item."
                    />
                    <MethodCard
                        icon={Gauge}
                        index="03"
                        title="Calibrate and fuse"
                        copy="Detector probabilities are temperature-scaled, weighted by observed reliability, and fused with uncertainty preserved."
                    />
                    <MethodCard
                        icon={Fingerprint}
                        index="04"
                        title="Review and communicate"
                        copy="Administrators inspect the complete report, record an outcome, and share that decision with the claim owner."
                    />
                </div>
            </section>

            <section className="landing-principles" id="governance">
                <div className="landing-principle-counter">
                    <span>{String(principleIndex + 1).padStart(2, "0")}</span>
                    <small>/ {String(principles.length).padStart(2, "0")}</small>
                </div>
                <div className="landing-principle-copy" key={principle.label}>
                    <p>{principle.label}</p>
                    <blockquote>{principle.quote}</blockquote>
                    <span>{principle.detail}</span>
                </div>
                <div className="landing-principle-controls">
                    <button onClick={() => movePrinciple(-1)} aria-label="Previous principle">
                        <CaretLeft weight="bold" />
                    </button>
                    <button onClick={() => movePrinciple(1)} aria-label="Next principle">
                        <CaretRight weight="bold" />
                    </button>
                </div>
            </section>

            <section className="landing-final-cta">
                <p>Ready to create an evidence-led claim?</p>
                <h2>Move from uploaded files to a reviewable decision record.</h2>
                <div>
                    <button className="landing-primary-action" onClick={onStartClaim}>
                        Open claimant portal <ArrowRight weight="bold" />
                    </button>
                    <button className="landing-secondary-action" onClick={onSignIn}>
                        Administrator sign in
                    </button>
                </div>
            </section>

            <footer className="landing-footer">
                <a className="landing-brand" href="#top">
                    <BrandMark className="brand-symbol" />
                    <span><strong>TrustLens AI</strong><small>Engineering evidence intelligence</small></span>
                </a>
                <p>Decision support for insurance and warranty evidence.</p>
                <div><a href="#methodology">Methodology</a><a href="#governance">Governance</a></div>
                <small>Research system · Human review required</small>
            </footer>
        </main>
    );
}


function MethodCard({icon: Icon, index, title, copy}) {
    return (
        <article className="landing-method-card">
            <div><Icon weight="duotone" /><span>{index}</span></div>
            <h3>{title}</h3>
            <p>{copy}</p>
        </article>
    );
}


export default LandingPage;

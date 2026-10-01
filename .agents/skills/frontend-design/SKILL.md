---
name: frontend-design
description: Design, refactor, audit, or style TrustLens AI React frontend pages and components. Use for public, authentication, dashboard, analysis, results, history, reports, profile, settings, responsive, accessibility, interaction, and visual-system work while preserving TrustLens API contracts and evidence integrity.
---

# TrustLens AI frontend design

## Scope and non-negotiables

Use this skill whenever creating, modifying, refactoring, or styling TrustLens frontend pages or components. Preserve the React/Vite architecture, React Router route boundaries, existing authentication flow, and backend API contracts unless a separately scoped backend task establishes a safe extension.

- Render analysis, score, model, OCR, report, user, and history values only from real API data.
- Never fabricate scores, confidence, accuracy, trends, filenames, thumbnails, user fields, report metadata, health, processing time, or system status.
- Use explicit loading, empty, error, unauthorized, unavailable, and partial-data states when data is absent.
- TrustLens is decision support, not proof of authenticity, fraud, provenance, ownership, or intent. Preserve this language on result-oriented surfaces.
- Do not expose tokens, credentials, model paths, model weights, or internal backend failures.

## Product direction

TrustLens AI is a multimodal AI-assisted image verification and forensic analysis platform. The interface should feel like a polished engineering, cybersecurity, and forensic-intelligence product suitable for a final-year demonstration and technical portfolio: precise, calm, modern, and credible. Avoid generic CRUD/admin-template, gaming, cartoon, neon-cyberpunk, fake-hacker, excessive-glass, and decorative-only treatments.

## Aura Fluid and GPT Taste adaptation

Before a meaningful UI change, inspect the active route, existing components, returned schema, and applicable screen width. State a short design read: page purpose, audience, hierarchy, and the one or two visual principles being applied.

Use the compatible parts of Aura Fluid and GPT Taste selectively:

- Favor Auraâ€™s modular panels, compact operational hierarchy, deliberate rhythm, clear focal object, and dense-but-legible information grouping.
- Favor intentional, non-templated composition, strong hierarchy, wide readable headings, and varied section rhythm. Do not make every page a uniform card wall or repeat the same left/right split.
- Keep display headings wide enough to avoid cramped six-line walls on desktop; use deliberate max widths and responsive type scales. Allow natural shorter wrapping on phones.
- Use bento or asymmetric grids only when their spans form a complete responsive layout with no dead cells. Prefer a simple grid when data does not justify a more expressive one.
- Use atmospheric gradients, texture, or ambient effects only as lightweight supporting layers with sufficient contrast and no impact on legibility or interaction.

Do not import Auraâ€™s purple/red palette, large default radii, free-form drag treatment, WebGL, or external imagery. Do not force GPT Tasteâ€™s randomization, GSAP, stock assets, AIDA structure, or typography choices. The established TrustLens design system, real-data rule, accessibility, and performance constraints always win.

Do not make forensic evidence, uploaded files, scores, reports, or layout-critical controls freely draggable. A future separately scoped rearrangement feature must preserve keyboard access, a deterministic reset, responsive fallback, and no mutation of analysis data.

## Visual system

The midnight forensic palette is authoritative. Treat the token file, not old page CSS, as the source of truth:

- canvas: deep ink; surfaces: layered blue-black; structure and focus: aqua; primary action: luminous violet
- use violet only for primary action, selected/high-priority actions, and deliberate emphasis; aqua communicates structure, navigation, and information
- use green, amber, and rose only with an icon and text label for Likely Authentic, Needs Review, and Potentially Suspicious respectively
- use fluid radial glows and layered panel depth as supporting atmosphere, never as a contrast substitute or decorative noise

Use Plus Jakarta Sans (with a compatible system fallback) for interface copy. Use JetBrains Mono only for technical values such as analysis IDs, hashes, filenames, and confirmed model/version identifiers. Use a 4px/8px spacing rhythm, controlled type hierarchy, 10px/14px/18px radii, and layered dark elevation. Avoid arbitrary spacing and nested-card overload.

## Components and interaction standards

Extend shared components rather than creating one-off page patterns. Prefer semantic HTML, labelled controls, visible `:focus-visible`, keyboard support, useful Lucide icons, sufficient contrast, and text-plus-icon status communication.

- Buttons: primary eggplant, secondary blue-outline, ghost, and semantic danger variants; every interactive state needs hover, active, focus-visible, disabled, and loading behavior.
- Cards: choose an intentional hierarchy (hero, KPI, evidence, information, technical) rather than identical boxes everywhere.
- Compose a clear first-viewport focal point around a real task, returned result, or clearly labelled conceptual explanation. Do not put invented metrics or system-status claims in it.
- Use a small number of differentiated surfacesâ€”hero, KPI, evidence, technical, information, or actionâ€”instead of nested cards without a grouping purpose.
- Avoid filler labels such as â€œSection 01.â€ Short technical labels are appropriate only when they clarify real workflow state or returned evidence.
- Async UI: use reusable loading, empty, error, success, unauthorized, unavailable, and retry patterns with correct live-region semantics.
- Motion: use short transitions for hover, press, elevation, reveal, and real progress only. Honor `prefers-reduced-motion`; never delay feedback or use constant/distracting animation.
- Do not simulate module progress, analysis completion, or live metrics. Motion must not obscure a state change.
- Tooltips and icon-only controls require accessible names. Modals/drawers require focus management, close controls, and Escape-key handling.

## Layout and responsiveness

Use mobile-first layouts. Keep desktop content balanced within roughly 1200–1400px, collapse grids deliberately at tablet widths, and stack to a single usable column at narrow widths. No unintended horizontal scrolling.

Authenticated pages use the shared application shell: a desktop sidebar of about 264px (about 72px when collapsed) with active-route indication, keyboard-safe collapse/expand, and labels/tooltips when collapsed. On mobile it becomes an accessible slide-out drawer with an overlay, close control, and Escape support. The top header shows only real page context and real data; do not claim system health or notifications without a supported API.

## TrustLens-specific content patterns

- Dashboard metrics and charts must be calculated from the owner-scoped history response, otherwise show an attractive honest empty/unavailable state. Label bounded/paginated data accurately.
- Analyze flow may show real selected-file metadata and preview. When the API only returns a final response, show a single honest “Analyzing image…” state rather than simulated module percentages.
- Results are a forensic report: show the server-derived Trust Score, category, evidence modules actually returned, XAI explanation/weights only when returned, explicit unavailable/failed modules, and visible limitations. The score visualization must represent the returned numeric score.
- History and Reports use only owner-scoped returned records and existing download endpoints. Do not add search, filtering, deletion, rename, pagination controls, thumbnails, or report actions unless supported or safely implemented as a separate backend task.
- Profile and Settings display or edit only supported persisted fields. Never create settings that look functional but are not persisted.
- Landing illustrations and conceptual pipelines must be clearly labelled illustrative/conceptual whenever they do not depict a live analysis.
- Public pages may use wider editorial composition, credible hero/CTA/workflow/footer structure, and clearly labelled conceptual diagrams, but never imply a live analysis, unsupported certification, or model accuracy claim.

## Delivery and verification

Before implementation, inspect the active route, reusable components, real response schema, authenticated state, and all affected error/empty/loading paths. After each meaningful phase run the frontend test suite, lint, and production build; then verify impacted routes, forms, route guards, API calls, keyboard behavior, and desktop/narrow layouts. Use browser review when available and explicitly report when it is not. Fix regressions before updating task tracking.

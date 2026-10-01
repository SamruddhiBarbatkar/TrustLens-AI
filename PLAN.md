# TrustLens Project Plan

## Status

Planning system completed through T35. The Explainable AI extension is staged in `TASKS.md`; XAI-01 through XAI-10 are complete, including schema, evidence/fusion explanations, authenticated API persistence, Results UI, PDF reporting, legacy-record compatibility, regression coverage, and real-image end-to-end verification (2026-09-30). The frontend transformation audit, permanent frontend design specification, shared light-theme/token phase (TF-02), shared-component phase (TF-03), authenticated-shell phase (TF-04), real-data Dashboard phase (TF-05), Analyze Image workspace phase (TF-06), Results forensic-report phase (TF-07), owner-scoped History phase (TF-08), owner-scoped Reports phase (TF-09), honest Profile/Settings phase (TF-10), accessible auth-form phase (TF-11), factual public-site phase (TF-12), and global frontend QA phase (TF-13) are complete. Automated verification passed; browser visual/console and live-auth smoke remain explicitly unverified because no browser connection is available and local backend health is offline. Setup, model-contract, API, security, limitations, and verification documentation are available in `README.md`.

## Objective

Build TrustLens, a responsive, authenticated full-stack application that helps users assess image trust signals. It will analyze a user-owned uploaded image through validated backend-only services and present transparent, non-conclusive findings, a 0–100 Trust Score, history, and downloadable reports.

## Problem and scope

Manipulated and AI-generated images can be difficult to assess quickly. TrustLens will surface multiple technical signals—visual tampering, AI-generation likelihood, OCR, image quality, and Error Level Analysis (ELA)—without presenting them as proof of fraud or scientifically validated truth.

## Architecture

React/Vite browser client → FastAPI API → services/inference pipeline → MongoDB. Uploaded files and model weights remain server-side. The API generates PDF reports after persisted, user-owned analyses.

## Technology stack

- Frontend: React, Vite, JavaScript, React Router, CSS, Lucide React
- Backend: Python, FastAPI, Uvicorn, PyTorch, torchvision, Pillow, OpenCV, NumPy, EasyOCR, ReportLab, python-dotenv
- Database: MongoDB
- Authentication: JWT and secure password hashing

## Intended folder structure

```
frontend/                 # React/Vite client (future)
backend/                  # FastAPI application (future)
  app/
    api/ core/ db/ models/ schemas/ services/ utils/
    tests/
  model_weights/          # local, ignored; never publicly served
  uploads/ reports/       # generated server artifacts, ignored
.agents/                  # project rules, skills, and workflows
PLAN.md TASKS.md
```

## AI models and integration requirements

- `best_model.pth`: trained ResNet18 visual-tampering detector.
- `ai_detector_best.pth`: trained EfficientNet-B0 AI-generated-image detector.
- EasyOCR: pretrained OCR only; do not train it.

Before integration, inspect the supplied checkpoint(s), training/inference source, class mapping, and preprocessing. Do not retrain, modify weights, replace models, assume architecture details, invent label mappings/preprocessing, produce fake predictions, or claim unverified accuracy. Models load and execute only in the FastAPI backend, in inference mode, with clear unavailable-model errors.

## Image-analysis pipeline

1. Validate content type, decoded image, dimensions, and upload size.
2. Generate a safe server-side filename and preprocess using verified model-specific requirements.
3. Run ResNet18 tampering inference and EfficientNet-B0 AI-generation inference.
4. Extract text with EasyOCR.
5. Calculate image-quality signals and ELA visual/statistical signals.
6. Combine available signals through transparent adaptive multimodal fusion.
7. Return and persist evidence, limitations, Trust Score/category, and report-ready output.

## OCR, ELA, and quality

OCR output is evidence only, including confidence where provided. ELA and quality measures must explain their method and limitations; compression, resizing, editing history, and source format can affect results. No signal alone is proof of manipulation or authenticity.

## Adaptive fusion and Trust Score

Fusion is application logic, not a third trained model. It must document signal availability, normalized inputs, weights/rules, and confidence limitations. Scores use: 80–100 Likely Authentic; 50–79 Needs Review; 0–49 Potentially Suspicious. These labels are non-conclusive and not scientifically validated unless later validated.

## Frontend architecture

Public routes: Home, Features, How It Works, About, Login, Signup. Protected routes: Dashboard, Analyze Image, Results, History, Reports, Profile, Settings. Use reusable layout/components, route guards, accessible controls, responsive CSS, and explicit loading, error, empty, and unavailable-model states. Never embed inference or expose model assets in the browser.

## Backend and API architecture

Use versioned FastAPI routers, Pydantic schemas, service boundaries, dependency injection, centralized exception handling, and health checks. Separate auth, users, analyses, reports, and upload/inference concerns. API responses must avoid stack traces and must distinguish validated findings from unavailable/failed signals.

## Database architecture

MongoDB collections will include users, analyses, and report metadata. Store password hashes only. Every analysis/report query must filter by authenticated owner. Create indexes for unique normalized email, owner/time history retrieval, and report lookup.

## Authentication and security

Implement JWT authentication, secure password hashing, protected routes/endpoints, ownership checks, CORS allow-list configuration, environment-based secrets, request/file validation, maximum upload size, safe generated filenames, path-traversal protection, server-only uploads/reports/models, and user-safe errors. Never commit secrets, weights, uploads, reports, or temporary artifacts.

## Reports

Generate a user-owned PDF report only from completed persisted analysis data. Include inputs, available signals, score/category, methodology caveats, timestamp, and no fraudulent-certainty claims.

## Testing and documentation

Use unit tests for services, schemas, scoring, and validation; integration/API tests for auth, ownership, uploads, analysis states, persistence, and reports; model contract tests based only on supplied verified artifacts; and frontend route/state tests. Document setup, environment variables, model-placement steps, operational limitations, and API behavior.

## Limitations

TrustLens is decision support, not proof of fraud, authenticity, provenance, copyright ownership, or intent. Output quality depends on images, model contracts, OCR, compression, and unvalidated fusion choices. Models may be unavailable until their verified artifacts are supplied.

## Development phases

1. Foundation: repository, frontend/backend scaffolds, configuration, database connectivity.
2. Security and identity: schemas, auth, protected access, validation.
3. Analysis services: validated model integration, OCR, quality, ELA, fusion.
4. Product UI: public site, authenticated analysis/results/history/report flows.
5. Quality: testing, security review, integration verification, documentation.

## Acceptance criteria

- All public/protected routes and stated workflows work responsively.
- Uploaded images are validated and never execute inference in the client.
- Both supplied models are integrated only after their contracts are verified.
- Results clearly show unavailable or failed signals; no fabricated output exists.
- Scores, categories, methodology, and limitations are transparent.
- Auth, ownership, uploads, paths, secrets, CORS, and errors meet the security requirements.
- Analyses and reports are private to their owners, test-covered, and documented.

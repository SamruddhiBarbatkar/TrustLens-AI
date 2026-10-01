# TrustLens

TrustLens is a decision-support application for reviewing several server-side image signals. It does not prove authenticity, fraud, provenance, copyright ownership, or intent.

## Setup

1. Copy `backend/.env.example` to `backend/.env`; supply a MongoDB URI and a strong JWT secret for production. Never commit this file.
2. Install backend dependencies and start the API:

   ```powershell
   cd backend
   ..\.tools\python-embed\python.exe -m pip install -r requirements.txt
   ..\.tools\python-embed\python.exe -m uvicorn app.main:app --reload
   ```

3. Copy `frontend/.env.example` to `frontend/.env`, then start the client:

   ```powershell
   cd frontend
   npm.cmd install
   npm.cmd run dev
   ```

## Model and OCR contract

`models/best_model.pth` is loaded strictly as the verified ResNet18 tampering state dict. `models/ai_detector_best.pth` is loaded strictly as the verified EfficientNet-B0 AI-image state dict. Neither checkpoint is modified or sent to the browser. EasyOCR is backend-only; downloads are disabled by default and an unavailable reader returns an explicit unavailable signal.

## API

- `POST /api/v1/auth/login` returns a bearer token for valid credentials.
- `POST /api/v1/analyses` accepts an authenticated `image` multipart field and returns persisted signal availability/results.
- `GET /api/v1/analyses?limit=20&offset=0` returns only the authenticated owner's newest analyses.
- `GET /api/v1/analyses/{analysis_id}/report` returns a PDF only when that analysis belongs to the authenticated owner.

Uploads must be image content and are bounded to 10 MiB. API errors are intentionally user-safe.

## Security

Secrets belong in `backend/.env`; `.env` files, model checkpoints, generated reports, uploads, and OCR weights are ignored. CORS uses `TRUSTLENS_CORS_ORIGINS` rather than a wildcard. Private queries derive ownership from the validated JWT, never from a client-supplied owner identifier.

## Limitations

OCR, ELA, image-quality, tampering, and AI-generation outputs are signals only. ELA is affected by compression, resizing, editing history, and source format. Model scores are not calibrated evidence. Unavailable signals must not be treated as negative or positive findings.

## Verification

Backend: `..\.tools\python-embed\python.exe -m pytest -q` and `..\.tools\python-embed\python.exe -m compileall -q app` from `backend`.

Frontend: `npm.cmd test`, `npm.cmd run lint`, and `npm.cmd run build` from `frontend`.

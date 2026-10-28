# TrustLens AI

TrustLens AI is a final-year research prototype for reviewing warranty and
insurance claim evidence. Claimants submit a claim with image context; an
administrator runs image verification, reviews the results, and records the
final claim decision. Model findings support human review and are not proof of
fraud or authenticity.

## Project structure

- `frontend/` — React and Vite claimant portal and administrator console.
- `backend/` — FastAPI, MongoDB or SQLite persistence, analysis pipeline, and
  model inference.
- `backend/calibration/` — calibrated fusion policy, research notes, and
  validation reports.
- `backend/training/` and `backend/scripts/` — reproducible research workflows.

## Run locally

Use Python 3.11 and Node.js. From `backend`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Set a unique `JWT_SECRET_KEY` and `BOOTSTRAP_ADMIN_PASSWORD` in `backend/.env`.
For MongoDB, set `DATABASE_BACKEND=mongodb` and provide either a local MongoDB
connection string or an Atlas `MONGODB_URI`. Set `MONGODB_DATABASE=trustlens_ai`.
The backend checks the connection and creates indexes when it starts. MongoDB
must be running or reachable before starting the API. No Alembic command is
needed for MongoDB.

For Atlas, [create a cluster and database user](https://www.mongodb.com/docs/atlas/tutorial/deploy-free-tier-cluster/),
[allow your current IP address](https://www.mongodb.com/docs/atlas/security/ip-access-list/),
then choose **Connect → Drivers → Python** and copy its URI into the untracked
`backend/.env` file. Replace the username and password placeholders there;
[percent-encode special characters](https://www.mongodb.com/docs/atlas/troubleshoot-connection/)
in URI credentials. Keep `MONGODB_DATABASE=trustlens_ai`; the application creates
its collections on first use. Test the connection from `backend` with:

```powershell
.\.venv\Scripts\python.exe scripts/check_mongodb.py
```

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The API health check is at <http://127.0.0.1:8000/health> and interactive API
documentation is at <http://127.0.0.1:8000/docs>.

In another terminal, from `frontend`:

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

Open <http://127.0.0.1:5173>. On Windows PowerShell systems that block
`npm.ps1`, use `npm.cmd` in place of `npm`.

### Existing SQLite data

The existing `backend/.env` on a machine is not replaced automatically. To
switch it, add `DATABASE_BACKEND=mongodb`, set the MongoDB URI and database,
and restart the API. Existing SQLite claims do not appear in a new MongoDB
database until they are copied. From `backend`, first preview the record
counts, then copy into a new MongoDB database. If a copy is interrupted, the
same command resumes after checking that existing records match the source:

```powershell
.\.venv\Scripts\python.exe scripts/migrate_sqlite_to_mongodb.py --sqlite sql_app.db
.\.venv\Scripts\python.exe scripts/migrate_sqlite_to_mongodb.py --sqlite sql_app.db --apply
```

Keep `sql_app.db` and `uploads/` as backups. MongoDB stores claim and evidence
metadata; uploaded image files remain in `UPLOAD_DIR`. If you prefer SQLite,
set `DATABASE_BACKEND=sqlite`, retain `DATABASE_URL`, and run
`alembic upgrade head` before starting the API.

## Verification workflow

1. A claimant creates a claim, uploads an image with its context, and selects
   **Submit claim**. An uploaded image in a `PENDING` draft cannot be verified.
2. An administrator chooses **Verification runs**, selects an eligible claim,
   and selects **Run verification**.
3. The administrator inspects the report and records an approval, rejection,
   or escalation with a review note. The claimant sees the released outcome.

## Research status

The active fusion policy is in `backend/calibration/artifacts/active.json`.
The current external-domain and document-domain pilots did not pass their
predeclared model readiness gates. Their test partitions remain reserved. See
[calibration notes](backend/calibration/README.md),
[external-domain validation](backend/calibration/SOFAKE_EXTERNAL_VALIDATION.md),
and [document-domain pilot](backend/calibration/DOCUMENT_DOMAIN_PILOT.md).
New source-matched, labeled claim images are needed before a model update can
be promoted or an accuracy claim can be made for real-world use.

## Data and secrets

Local `.env` files, the SQLite database, claimant uploads, downloaded research
images, and generated output are excluded from Git. The repository includes
only the checkpoints required by the current application; source dataset
licenses must be followed when training or publishing research results.

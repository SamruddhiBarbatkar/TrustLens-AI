"""Verify the configured MongoDB connection without starting model inference."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db.mongo_database import initialize_mongodb, mongo_database


if settings.database_backend != "mongodb":
    raise SystemExit("Set DATABASE_BACKEND=mongodb in backend/.env first.")

initialize_mongodb()
db = mongo_database()
print(f"MongoDB connection OK. Database: {db.name}")
for collection in ("users", "claims", "evidence", "verification_runs", "analysis_results", "review_decisions"):
    print(f"{collection}: {db[collection].count_documents({})}")

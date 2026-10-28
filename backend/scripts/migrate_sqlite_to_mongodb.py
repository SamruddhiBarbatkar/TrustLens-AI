"""Copy an existing TrustLens SQLite database into an empty MongoDB database.

Run from the backend directory with DATABASE_BACKEND=mongodb configured.
The default invocation only prints counts; --apply performs the copy.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.db.models import AnalysisResult, Claim, Evidence, ReviewDecision, User, VerificationRun
from app.db.mongo_database import _fields, initialize_mongodb, mongo_database


MODELS = (User, Claim, Evidence, VerificationRun, AnalysisResult, ReviewDecision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, default=Path("sql_app.db"))
    parser.add_argument("--apply", action="store_true", help="copy records into an empty MongoDB database")
    args = parser.parse_args()

    source = args.sqlite.resolve()
    if not source.is_file():
        parser.error(f"SQLite database does not exist: {source}")
    engine = create_engine(f"sqlite:///{source.as_posix()}")
    tables = set(inspect(engine).get_table_names())
    missing = [model.__tablename__ for model in MODELS if model.__tablename__ not in tables]
    if missing:
        parser.error(f"SQLite database is missing tables: {', '.join(missing)}")

    session = sessionmaker(bind=engine)()
    try:
        rows = {
            model: session.query(model).order_by(model.id).all()
            for model in MODELS
        }
        for model, records in rows.items():
            print(f"{model.__tablename__}: {len(records)}")
        if not args.apply:
            print("Dry run only. Add --apply to copy these records.")
            return

        if settings.database_backend != "mongodb":
            parser.error("Set DATABASE_BACKEND=mongodb and MONGODB_URI before --apply.")
        initialize_mongodb()
        target = mongo_database()
        occupied = [
            model.__tablename__ for model in MODELS
            if target[model.__tablename__].count_documents({}, limit=1)
        ]
        if occupied:
            parser.error(
                "MongoDB target must be empty. Existing data found in: "
                + ", ".join(occupied)
            )

        for model, records in rows.items():
            if not records:
                continue
            collection = target[model.__tablename__]
            collection.insert_many([{"_id": record.id, **_fields(record)} for record in records])
            target.counters.replace_one(
                {"_id": model.__tablename__},
                {"_id": model.__tablename__, "value": max(record.id for record in records)},
                upsert=True,
            )
        print("Copy complete. Keep the SQLite file as a backup.")
        print("Image files remain in UPLOAD_DIR; keep that directory with the backend.")
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()

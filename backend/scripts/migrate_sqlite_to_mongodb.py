"""Copy an existing TrustLens SQLite database into MongoDB.

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
    parser.add_argument("--apply", action="store_true", help="copy records; reruns resume an interrupted copy")
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
        # Check every existing ID before writing anything. This permits a safe
        # retry after an interrupted copy while rejecting a different dataset.
        fingerprints = {
            User: ("email",),
            Claim: ("claim_number",),
            Evidence: ("claim_id", "evidence_type", "stored_filename"),
            VerificationRun: ("claim_id", "pipeline_version"),
            AnalysisResult: ("verification_run_id", "analysis_type", "evidence_id"),
            ReviewDecision: ("claim_id", "verification_run_id", "reviewer_id", "action"),
        }
        copied_ids = {}
        for model, records in rows.items():
            expected = {record.id: record for record in records}
            existing = list(target[model.__tablename__].find({}))
            for document in existing:
                source_record = expected.get(document["_id"])
                if source_record is None or any(
                    document.get(field) != getattr(source_record, field)
                    for field in fingerprints[model]
                ):
                    parser.error(
                        f"MongoDB {model.__tablename__} contains data that does not "
                        "match this SQLite source; choose a different database."
                    )
            copied_ids[model] = {document["_id"] for document in existing}

        for model, records in rows.items():
            if not records:
                continue
            collection = target[model.__tablename__]
            missing = [record for record in records if record.id not in copied_ids[model]]
            if missing:
                collection.insert_many([{"_id": record.id, **_fields(record)} for record in missing])
            print(f"{model.__tablename__}: copied {len(missing)} remaining records")
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

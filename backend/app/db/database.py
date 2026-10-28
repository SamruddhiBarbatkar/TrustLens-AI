from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings


engine = create_engine(settings.database_url) if settings.database_backend == "sqlite" else None

if settings.database_backend == "mongodb":
    from app.db.mongo_database import mongo_session_factory

    SessionLocal = mongo_session_factory
else:
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()

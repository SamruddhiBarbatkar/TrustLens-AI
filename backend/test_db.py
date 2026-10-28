"""Check the configured database connection from the backend directory."""

from sqlalchemy import text

from app.core.config import settings


if settings.database_backend == "mongodb":
    from app.db.mongo_database import initialize_mongodb, mongo_database

    initialize_mongodb()
    print(f"Connected to MongoDB database: {mongo_database().name}")
else:
    from app.db.database import engine

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    print("Connected to SQLite database.")

from sqlalchemy import create_engine, text
from app.core.config import settings


engine = create_engine(settings.database_url)


with engine.connect() as connection:
    result = connection.execute(text("SELECT current_database()"))

    print("Connected to database:")
    print(result.scalar())
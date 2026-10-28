# Database migrations

Alembic migrations apply to the SQLite backend only. New MongoDB installations
use `DATABASE_BACKEND=mongodb`, `MONGODB_URI`, and `MONGODB_DATABASE`; the API
creates MongoDB indexes on startup. See the root README for copying existing
SQLite records to an empty MongoDB database.

For SQLite, set `DATABASE_BACKEND=sqlite` and use these commands.

Install the development tools from the backend directory:

```powershell
python -m pip install -r requirements-dev.txt
```

For a new database:

```powershell
alembic upgrade head
```

For an existing `sql_app.db` that already contains the initial tables, mark it
as current without recreating them:

```powershell
alembic stamp head
```

Create later schema revisions with:

```powershell
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

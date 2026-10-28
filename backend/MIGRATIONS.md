# Database migrations

TrustLens uses SQLite by default for local and final-year-project demos.

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

# Shared database

The customer and manager applications share one SQLite database. The schema
preserves source-specific job status events so conflicting workshop, quality
control, and CRM records remain visible to the decision and review workflow.

All included records are synthetic C01 exercise data.

## Create and seed the local database

From the project root:

```powershell
python -m backend.db.seed
```

The command creates `backend/data/dail.db`. It is safe to run repeatedly.

## Inspect review cases

```powershell
python -m backend.db.inspect_database
```

## Run the focused database test

```powershell
python -m unittest backend.tests.test_database
```

# Shared database

The customer and manager applications share one SQLite database. The schema
preserves source-specific job status events so conflicting workshop, quality
control, and CRM records remain visible to the decision and review workflow.

All included records are synthetic C01 exercise data.

## Run the API

Create a virtual environment and install the backend dependencies:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
```

Start the API from the project root:

```powershell
.venv\Scripts\python -m uvicorn backend.api.main:app --reload --port 8000
```

The Vite development server proxies `/api` requests to this service.

## Gmail delivery configuration

Outbound delivery is controlled by `backend/config/gmail.json`.

The committed default is safe simulation mode:

```json
{
  "mode": "simulation",
  "sender_name": "SAGE Service Desk",
  "credentials_file": "backend/secrets/gmail-credentials.json",
  "token_file": "backend/secrets/gmail-token.json"
}
```

To enable real Gmail delivery:

1. Create a Google Cloud desktop OAuth client with the Gmail API enabled.
2. Save its downloaded JSON as `backend/secrets/gmail-credentials.json`.
3. Run `.venv\Scripts\python -m backend.integrations.gmail_auth` and authorize the dedicated demonstration Gmail account.
4. Change `mode` in `backend/config/gmail.json` to `gmail_api`.
5. Restart the API.

The `backend/secrets` directory is ignored by Git. Never commit OAuth client
credentials or Gmail tokens.

## Local agent configuration

`backend/config/agent.json` controls the Ollama endpoint and model. SAGE uses
`qwen3:8b` by default and falls back to deterministic classification if Ollama
is unavailable.

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

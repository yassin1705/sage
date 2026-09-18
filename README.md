# SAGE

**Secretary Agent for Guidance and Engagement**

SAGE is an evidence-backed customer-service assistant for dealerships. It brings
customer enquiries from multiple communication channels into one review
workflow, prepares a response from the available operational evidence, and
keeps a human manager in control of uncertain or high-impact answers.

> AI prepares the answer. Evidence explains it. A human stays in control.

## Project status

SAGE is a hackathon prototype intended for local demonstrations and portfolio
use. It is not production-ready and does not include authentication, production
deployment configuration, or live dealership-system integrations.

## The problem

Customers contact dealerships through WhatsApp, email, web chat, and phone
calls. They may speak different languages, and they often need a quick answer
to a simple question such as:

> When can I collect my car?

Answering safely can require someone to check messages, workshop progress,
quality-control records, bookings, and CRM data. When those systems disagree,
staff may repeat work or make a promise the dealership cannot keep.

## The SAGE workflow

1. A customer asks a question through the customer portal.
2. SAGE identifies the request and the relevant vehicle case.
3. It gathers evidence from the available synthetic records.
4. Deterministic rules detect missing or conflicting information.
5. A role-controlled service workflow assigns the current stage and next owner.
6. SAGE prepares a response and explains its recommendation.
7. A manager approves, edits, or rejects the proposed response.
8. The approved response is returned to the customer through a simulated
   delivery channel.

## Current features

### Customer portal

- Conversational customer interface.
- English and French language selection.
- Suggested customer questions.
- Visible case and review status.
- Responsive desktop and mobile design.
- Voice controls displayed as a planned capability.

### Manager workspace

- Unified customer-inquiry queue.
- Search and review-status filters.
- Predefined request classifications with manual correction.
- Agent confidence, justification, and triggered business rules.
- Evidence snapshots from workshop, CRM, and quality-control records.
- Authoritative service stage, assigned role, and owned next action.
- Role-authorized quality-control transition with an immutable event history.
- Optimistic version checks that prevent simultaneous stage changes.
- Editable proposed responses.
- Simulated approval, rejection, and delivery workflow.
- Simulated WhatsApp and Gmail configuration area.
- Separate vehicle-workflow workspace with registration, job, and customer search.
- Authoritative stage, assigned role, allowed actions, and immutable handoff history.

### Shared database

- SQLite schema shared by both applications.
- Customers, vehicles, service jobs, and source-specific status events.
- Allowed workflow transitions and append-only stage-change events.
- Conversations, messages, classifications, and decisions.
- Evidence snapshots, human reviews, channel configuration, and audit events.
- Repeatable synthetic C01 seed data.

## Architecture

```text
Customer portal ──┐
                  ├── Shared API ── Decision workflow ── SQLite
Manager workspace ┘                       │
                                         ├── Business rules
                                         ├── Local language model
                                         └── Channel adapters
                                              ├── Simulator
                                              ├── Gmail       (optional)
                                              ├── WhatsApp    (planned)
                                              └── Voice       (planned)
```

The shared API connects both frontends to the SQLite workflow. Qwen performs
classification and drafting through Ollama, with a deterministic fallback.
Manager-approved responses are delivered through the configurable outbound
Gmail adapter, which defaults to safe simulation mode.

## Technology

- React
- TypeScript
- Vite
- Python
- SQLite
- Ollama with Qwen3 8B for optional local agent inference
- Faster Whisper planned for local speech transcription

## Run the applications

Requirements:

- Node.js 20 or later
- Python 3.11 or later

Install the frontend dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

In a second terminal, start the backend API:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
.venv/Scripts/python -m uvicorn backend.api.main:app --reload --port 8000
```

Open:

- Customer portal: `http://127.0.0.1:5173/`
- Manager workspace: `http://127.0.0.1:5173/manager`

Build the frontend:

```bash
npm run build
```

## Initialize the database

Create and seed the synthetic local database:

```bash
python -m backend.db.seed
```

Inspect the available review cases:

```bash
python -m backend.db.inspect_database
```

Run the focused database and workflow tests:

```bash
python -m unittest backend.tests.test_database backend.tests.test_workflow
```

See [backend/README.md](backend/README.md) for database details.

## Exercise boundary

SAGE currently uses synthetic exercise data. WhatsApp, booking, and voice
integrations are simulated. Gmail also defaults to safe simulation mode, though
an optional API adapter is available for local demonstrations. No real customer
is contacted or appointment changed unless an operator deliberately configures
that adapter, and no simulated status should be treated as an official
dealership confirmation.

## Roadmap

- Add deeper multilingual evaluation and response drafting.
- Expand deterministic decision rules and risk levels.
- Add local speech-to-text and text-to-speech.
- Add authentication and production deployment configuration.
- Introduce a WhatsApp adapter after the simulated workflow is stable.

## License

SAGE is available under the [MIT License](LICENSE).
